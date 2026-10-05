#!/usr/bin/env python3
"""Evaluate native skill consultation in isolated Pi sessions."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
import selectors
import shutil
import subprocess
import tarfile
import time
from urllib.parse import unquote, urlsplit


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def bind_manifest(path, manifest, keys):
    if path.exists():
        previous = json.loads(path.read_text())
        if any(previous[key] != manifest[key] for key in keys):
            raise ValueError("Eval configuration changed; use a fresh workspace")
    else:
        write_json(path, manifest)


def cached_run(directory, workspace, retry_incomplete, complete):
    result_path = directory / "result.json"
    if result_path.exists():
        result = json.loads(result_path.read_text())
        if not retry_incomplete or complete(result):
            return result
    elif directory.exists() and any(directory.iterdir()) and not retry_incomplete:
        raise ValueError("Interrupted run exists; use --retry-incomplete to archive and restart it")
    if directory.exists() and any(directory.iterdir()):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        archive = workspace / "attempts" / stamp / directory.relative_to(workspace)
        archive.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(directory), archive)
    return None


def snapshot(ref, destination):
    oid = subprocess.check_output(["git", "rev-parse", ref], cwd=REPO, text=True).strip()
    if not destination.exists():
        destination.mkdir(parents=True)
        data = subprocess.check_output(["git", "archive", oid, ".agents/skills"], cwd=REPO)
        with tarfile.open(fileobj=io.BytesIO(data)) as archive:
            archive.extractall(destination, filter="data")
        (destination / ".snapshot-ref").write_text(oid + "\n")
    if (destination / ".snapshot-ref").read_text().strip() != oid:
        raise ValueError("Snapshot ref changed; use a fresh workspace")
    return oid


def inspect_catalog(skill_root):
    install = subprocess.check_output(["mise", "where", "npm:@earendil-works/pi-coding-agent"], text=True).strip()
    module = Path(install) / "node_modules/@earendil-works/pi-coding-agent/dist/core/skills.js"
    source = ("import {loadSkills} from " + json.dumps(module.as_uri()) + ";"
              "const r=loadSkills({cwd:process.cwd(),skillPaths:[process.argv[1]],includeDefaults:false});"
              "process.stdout.write(JSON.stringify({skills:r.skills.map(s=>({name:s.name,file:s.filePath,"
              "description:s.description})),diagnostics:r.diagnostics}));")
    catalog = json.loads(subprocess.check_output(
        ["node", "--input-type=module", "-e", source, str(skill_root)], text=True))
    expected = {p.parent.name for p in skill_root.glob("*/SKILL.md")}
    if {s["name"] for s in catalog["skills"]} != expected:
        raise ValueError("Catalog contains missing or extra skills")
    if not all(Path(s["file"]).is_relative_to(skill_root) for s in catalog["skills"]):
        raise ValueError("Catalog contains a skill outside the tested snapshot")
    return catalog


def command(skill_root, query, model, tools="read,grep,find,ls"):
    return ["pi", "--model", model, "--thinking", "high", "--mode", "json",
            "--no-session", "--no-context-files", "--no-extensions",
            "--no-prompt-templates", "--no-skills", "--skill", str(skill_root),
            "--tools", tools, "-p", query]


def completed_agent(event):
    """An API error can emit agent_end; only a normal final answer is complete."""
    assistants = [m for m in event.get("messages", []) if m.get("role") == "assistant"]
    return (event.get("type") == "agent_end" and bool(assistants)
            and assistants[-1].get("stopReason") == "stop")


def tool_path(path, cwd):
    path = re.sub(r"[\u00a0\u2000-\u200a\u202f\u205f\u3000]", " ", path)
    if path.startswith("@"):
        path = path[1:]
    if path == "~" or path.startswith("~/"):
        path = str(Path(path).expanduser())
    if path.startswith("file://"):
        path = unquote(urlsplit(path).path)
    return (cwd / path).resolve()


def run_trigger(item, variant, workspace, model, timeout, retry_incomplete=False):
    directory = workspace / "triggers" / item["id"] / variant
    cached = cached_run(directory, workspace, retry_incomplete, lambda row: row["scorable"])
    if cached is not None:
        return cached
    directory.mkdir(parents=True, exist_ok=True)
    result_path = directory / "result.json"
    cwd = directory / "fixture"
    cwd.mkdir(exist_ok=True)
    skills = (workspace / "snapshots" / variant / ".agents/skills").resolve()
    target = skills / item["skill"] / "SKILL.md"
    started = time.monotonic()
    calls, pending, evidence = [], {}, []
    models = set()
    triggered, status, ended = False, "incomplete", False
    # Limit model tools to reads so a trigger query cannot perform the requested
    # publish, install, browser drive, or secret-management operation.
    with (directory / "stderr.txt").open("w") as errors, \
            (directory / "transcript.jsonl").open("wb") as transcript:
        proc = subprocess.Popen(command(skills, item["query"], model), cwd=cwd,
                                stdout=subprocess.PIPE, stderr=errors)
        selector = selectors.DefaultSelector()
        selector.register(proc.stdout, selectors.EVENT_READ)
        buffer = b""
        try:
            while time.monotonic() - started < timeout:
                available = selector.select(timeout=0.5)
                if not available:
                    if proc.poll() is not None:
                        break
                    continue
                chunk = os.read(proc.stdout.fileno(), 65536)
                if not chunk:
                    break
                transcript.write(chunk)
                transcript.flush()
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    try:
                        event = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        continue
                    if event.get("type") == "message_end" and event.get("message", {}).get("role") == "assistant":
                        message = event["message"]
                        models.add((message.get("provider"), message.get("model")))
                    if event.get("type") == "tool_execution_start":
                        pending[event["toolCallId"]] = event
                    if event.get("type") == "tool_execution_end":
                        call = pending.get(event.get("toolCallId"), {})
                        args = call.get("args", {})
                        path = args.get("path", "")
                        entry = {"tool": call.get("toolName"), "args": args,
                                 "is_error": event.get("isError", False)}
                        calls.append(entry)
                        if call.get("toolName") == "read" and not event.get("isError"):
                            resolved = tool_path(path, cwd)
                            if resolved.name == "SKILL.md" and not resolved.is_relative_to(skills):
                                status = "invalid_tree"
                                break
                            if resolved == target.resolve():
                                triggered = True
                                evidence.append({"event": "tool_execution_end", "path": str(target),
                                                 "tool_call_id": event["toolCallId"]})
                    if event.get("type") == "agent_end":
                        ended = completed_agent(event)
                        if not ended:
                            status = "model_error"
                            break
                if triggered:
                    status = "observed_consultation"
                    break
                if ended:
                    status = "completed"
                    break
                if status in ("model_error", "invalid_tree"):
                    break
            if not triggered and not ended:
                if status not in ("model_error", "invalid_tree"):
                    status = "timeout" if proc.poll() is None else "process_error"
        finally:
            selector.close()
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            proc.stdout.close()
    complete = triggered or ended
    result = {"id": item["id"], "skill": item["skill"], "variant": variant,
              "should_trigger": item["should_trigger"], "triggered": triggered,
              "status": status, "scorable": complete,
              "passed": triggered == item["should_trigger"] if complete else None,
              "duration_seconds": round(time.monotonic() - started, 3),
              "observed_models": sorted(models),
              "evidence": evidence, "tool_calls": calls,
              "transcript_sha256": hashlib.sha256((directory / "transcript.jsonl").read_bytes()).hexdigest()}
    write_json(result_path, result)
    return result


def summarize(results):
    summary = {}
    for variant in ("after", "before"):
        rows = [row for row in results if row["variant"] == variant]
        if not rows:
            continue
        valid = [row for row in rows if row["scorable"]]
        tp = sum(row["triggered"] and row["should_trigger"] for row in valid)
        fp = sum(row["triggered"] and not row["should_trigger"] for row in valid)
        fn = sum(not row["triggered"] and row["should_trigger"] for row in valid)
        summary[variant] = {"total": len(rows), "scorable": len(valid),
                            "incomplete": len(rows) - len(valid), "tp": tp, "fp": fp, "fn": fn,
                            "correct": sum(row["passed"] for row in valid),
                            "precision": tp / (tp + fp) if tp + fp else None,
                            "recall": tp / (tp + fn) if tp + fn else None}
    output = {"summary": summary, "results": sorted(results, key=lambda row: (row["id"], row["variant"]))}
    if not {"before", "after"}.issubset(summary):
        return output
    paired = {}
    for row in results:
        paired.setdefault(row["id"], {})[row["variant"]] = row
    changes, matched = [], []
    for key, pair in paired.items():
        if len(pair) == 2 and all(row["scorable"] for row in pair.values()):
            matched.extend(pair.values())
            if pair["before"]["passed"] != pair["after"]["passed"]:
                changes.append({"id": key, "skill": pair["after"]["skill"],
                                "change": "improved" if pair["after"]["passed"] else "regressed"})
    paired_summary = {}
    for variant in ("after", "before"):
        rows = [row for row in matched if row["variant"] == variant]
        tp = sum(row["triggered"] and row["should_trigger"] for row in rows)
        fp = sum(row["triggered"] and not row["should_trigger"] for row in rows)
        fn = sum(not row["triggered"] and row["should_trigger"] for row in rows)
        tn = sum(not row["triggered"] and not row["should_trigger"] for row in rows)
        paired_summary[variant] = {"pairs": len(rows), "tp": tp, "fp": fp, "fn": fn, "tn": tn,
                                   "accuracy": (tp + tn) / len(rows) if rows else None,
                                   "precision": tp / (tp + fp) if tp + fp else None,
                                   "recall": tp / (tp + fn) if tp + fn else None}
    return {**output, "paired_summary": paired_summary, "paired_changes": changes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--ref", "--after", dest="after", default="HEAD", help="Current skill commit to evaluate (default: HEAD)")
    parser.add_argument("--before", help="Optional temporary baseline commit for a comparison")
    parser.add_argument("--model", required=True)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--ids", help="Comma-separated pilot or retry case IDs")
    parser.add_argument("--retry-incomplete", action="store_true", help="Archive incomplete attempts before restarting them")
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    selected_refs = {"after": args.after}
    if args.before:
        selected_refs["before"] = args.before
    refs = {variant: snapshot(ref, workspace / "snapshots" / variant)
            for variant, ref in selected_refs.items()}
    for variant in refs:
        write_json(workspace / "catalogs" / (variant + ".json"),
                   inspect_catalog(workspace / "snapshots" / variant / ".agents/skills"))
    dataset = HERE / "triggers.json"
    items = json.loads(dataset.read_text())
    for item in items:
        for variant in refs:
            if not (workspace / "snapshots" / variant / ".agents/skills" / item["skill"] / "SKILL.md").is_file():
                raise ValueError(f"Target skill {item['skill']} is absent from {variant}")
    if args.ids:
        ids = set(args.ids.split(","))
        items = [item for item in items if item["id"] in ids]
        if len(items) != len(ids):
            raise ValueError("Unknown case ID")
    manifest = {"refs": refs, "model": args.model, "thinking": "high", "harness": "pi",
                "pi_version": subprocess.check_output(["pi", "--version"], text=True).strip(),
                "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                "case_ids": [item["id"] for item in items],
                "timeout_seconds": args.timeout, "jobs": args.jobs,
                "started_at": datetime.now(timezone.utc).isoformat(),
                "method": "Raw user queries, fresh ephemeral sessions, snapshot-only skill catalogs, read-only tools. Target SKILL.md successful read is trigger evidence. Positive reads may end early; completed negative runs are scored, timeouts are excluded."}
    bind_manifest(workspace / "manifest.json", manifest,
                  ("refs", "model", "thinking", "pi_version", "dataset_sha256"))
    with (workspace / "invocations.jsonl").open("a") as log:
        log.write(json.dumps(manifest, ensure_ascii=False) + "\n")
    variants = list(refs)
    work = [(item, variant) for index, item in enumerate(items)
            for variant in (variants if index % 2 else variants[::-1])]
    results = []
    selected_ids = {item["id"] for item in items}
    retained = [json.loads(p.read_text()) for p in workspace.glob("triggers/*/*/result.json")
                if p.parent.parent.name not in selected_ids and p.parent.name in refs]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(run_trigger, item, variant, workspace, args.model, args.timeout, args.retry_incomplete)
                   for item, variant in work]
        for future in as_completed(futures):
            row = future.result()
            results.append(row)
            print(json.dumps({key: row[key] for key in ("id", "variant", "status", "passed")}), flush=True)
            write_json(workspace / "trigger-results.json", summarize(retained + results))
    if len(results) != len(work):
        raise RuntimeError("Missing execution results")


if __name__ == "__main__":
    main()
