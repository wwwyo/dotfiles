#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["langfuse==4.15.4", "requests==2.34.2"]
# ///
"""Prepare legacy ID mappings using GETs only; persist IDs/hashes, never payloads.

Run with existing Langfuse environment authentication:
  uv run --script langfuse_reconcile.py --output /review/path/migrations.json
The output is reviewed before placing it in langfuse-export's state directory.
"""
import argparse
import hashlib
import importlib.util
import json
import logging
import os
import re
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

import langfuse_hook as lh


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode()).hexdigest()


def decode(value):
    if isinstance(value, str):
        try:
            return json.loads(value)
        except ValueError:
            pass
    return value


def milliseconds(value):
    if value is None:
        return None
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp() * 1000)


def cloud_signature(row):
    md = row.get("metadata") or {}
    kind = row.get("type", "").upper()
    keys = {"SPAN": ("source", "assistant_message_count", "telemetry_summary"),
            "GENERATION": ("assistant_index", "tool_count"),
            "TOOL": ("tool_id", "tool_name")}.get(kind, ())
    return digest({"type": kind, "start": milliseconds(row.get("startTime")),
                   "end": milliseconds(row.get("endTime")),
                   "input": decode(row.get("input")), "output": decode(row.get("output")),
                   "model": row.get("model") if kind == "GENERATION" else None,
                   "metadata": {k: decode(md.get(k)) for k in keys}})


def span_row(span):
    attrs = span.attributes
    prefix = "langfuse.observation.metadata."
    return {"id": f"{span.context.span_id:016x}",
            "traceId": f"{span.context.trace_id:032x}",
            "parentObservationId": f"{span.parent.span_id:016x}" if span.parent else None,
            "type": attrs.get("langfuse.observation.type", "").upper(),
            "startTime": datetime.fromtimestamp(span.start_time / 1e9, timezone.utc).isoformat(),
            "endTime": datetime.fromtimestamp(span.end_time / 1e9, timezone.utc).isoformat(),
            "input": attrs.get("langfuse.observation.input"),
            "output": attrs.get("langfuse.observation.output"),
            "model": attrs.get("langfuse.observation.model.name"),
            "metadata": {k[len(prefix):]: v for k, v in attrs.items() if k.startswith(prefix)}}


class Projector:
    """Use the real emitter and pinned SDK, exclusively with an in-memory exporter."""
    def __init__(self):
        from langfuse import Langfuse
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
        self.rows = []
        rows = self.rows

        class Capture(SpanExporter):
            def export(self, spans):
                rows.extend(span_row(s) for s in spans)
                return SpanExportResult.SUCCESS
            def shutdown(self):
                pass

        self.provider = TracerProvider(id_generator=lh.SourceIdGenerator())
        self.client = Langfuse(public_key="pk-offline-projection", secret_key="sk-offline-projection",
                               base_url="http://127.0.0.1:1", tracer_provider=self.provider,
                               span_exporter=Capture(), sample_rate=1)

    def expected(self, turns, sid, source_path, cloud=None):
        seeds = {}
        self.rows.clear()
        for number, turn in enumerate(turns, 1):
            # Legacy sessions can contain full history followed by compact turns.
            # Select compact only when its complete summary matches the source;
            # payload, time and topology are still verified by match().
            summary = lh.turn_summary(turn)
            compact = any(row.get("parentObservationId") is None
                          and decode((row.get("metadata") or {}).get("turn_number")) == number
                          and decode((row.get("metadata") or {}).get("telemetry_summary")) == summary
                          for row in (cloud or []))
            uid = lh.get_message_id(turn.user_msg)
            values = [lh.observation_seed("devin", sid, "turn", uid)]
            for assistant in turn.assistant_msgs:
                aid = lh.get_message_id(assistant)
                values.append(lh.observation_seed("devin", sid, "generation", [uid, aid]))
                values.extend(lh.observation_seed("devin", sid, "tool", [uid, aid, call["id"]])
                              for call in lh.iter_tool_uses(lh.get_content(assistant)))
            for seed in values:
                span_id = hashlib.sha256(("span:" + seed).encode()).hexdigest()[:16]
                seeds[span_id] = hashlib.sha256(seed.encode()).hexdigest()
            lh.emit_turn(self.client, sid, number, turn, source_path, source="devin",
                         label="Devin", deterministic_ids=True,
                         detail="turn" if compact else "full")
        self.client.flush()
        if not self.provider.force_flush():
            raise RuntimeError("offline projection flush failed")
        return [{"id": row["id"], "parent": row["parentObservationId"],
                 "signature": cloud_signature(row), "seed": seeds[row["id"]]}
                for row in self.rows]

    def close(self):
        try:
            self.client.shutdown()
        finally:
            self.provider.shutdown()


def match(expected, cloud, sid):
    """Require unique, complete payload/time/topology matches; never use counts as proof."""
    if not expected:
        return None, "empty_source"
    if any(row.get("sessionId") != sid for row in cloud):
        return None, "session_mismatch"
    projects = {row.get("projectId") for row in cloud}
    if len(projects) != 1 or None in projects:
        return None, "project_missing_or_mixed"
    if any(not re.fullmatch(r"[0-9a-f]{16}", row.get("id", "")) or
           not re.fullmatch(r"[0-9a-f]{32}", row.get("traceId", "")) for row in cloud):
        return None, "unsupported_id_format"
    by_parent = defaultdict(list)
    for row in cloud:
        by_parent[row.get("parentObservationId")].append(row)
    local_children = defaultdict(list)
    for row in expected:
        local_children[row["parent"]].append(row)
    mapped, identities = {}, {}
    queue = [(None, None)]
    while queue:
        local_parent, cloud_parent = queue.pop()
        children = local_children[local_parent]
        counts = Counter(row["signature"] for row in children)
        if any(n > 1 for n in counts.values()):
            return None, "ambiguous_source"
        for node in children:
            matches = [row for row in by_parent[cloud_parent]
                       if cloud_signature(row) == node["signature"]]
            if not matches:
                return None, "missing_cloud_match"
            if len(matches) != 1:
                return None, "ambiguous_cloud_match"
            row = matches[0]
            if cloud_parent is not None and row["traceId"] != mapped[local_parent]["traceId"]:
                return None, "trace_parent_mismatch"
            mapped[node["id"]] = row
            identities[node["seed"]] = {"trace_id": row["traceId"], "span_id": row["id"]}
            queue.append((node["id"], row["id"]))
    if len(mapped) != len(expected):
        return None, "incomplete_topology"
    # Extra descendants of matched parents can be already delivered nodes absent
    # from the local snapshot. Do not create replacement IDs for unknown coverage.
    matched_ids = {row["id"] for row in mapped.values()}
    if any(row.get("parentObservationId") in matched_ids and row["id"] not in matched_ids
           for row in cloud):
        return None, "unmapped_cloud_descendant"
    return {"identities": identities, "project_id": projects.pop()}, "verified"


def fetch(session, host, sid):
    rows, cursor = [], None
    for _ in range(100):
        params = {"filter": json.dumps([{"type": "string", "column": "sessionId",
                                         "operator": "=", "value": sid}]),
                  "limit": 1000, "fields": "basic,time,metadata,io,model",
                  "expandMetadata": "telemetry_summary"}
        if cursor:
            params["cursor"] = cursor
        response = session.get(host + "/api/public/v2/observations", params=params, timeout=30)
        if response.status_code != 200:
            raise RuntimeError(f"read status {response.status_code}")
        body = response.json()
        if not isinstance(body.get("data"), list):
            raise RuntimeError("invalid read response")
        rows.extend(body["data"])
        new = body.get("meta", {}).get("cursor")
        time.sleep(3.3)
        if not new:
            return rows
        if new == cursor:
            raise RuntimeError("pagination stalled")
        cursor = new
    raise RuntimeError("pagination bound")


def main():
    import requests
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    public = os.environ.get("CC_LANGFUSE_PUBLIC_KEY") or os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret = os.environ.get("CC_LANGFUSE_SECRET_KEY") or os.environ.get("LANGFUSE_SECRET_KEY")
    host = (os.environ.get("CC_LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_BASE_URL")
            or "https://cloud.langfuse.com").rstrip("/")
    if not public or not secret:
        parser.error("existing Langfuse environment authentication required")
    # This process never sends SDK spans, scores or media to a cloud destination.
    os.environ["LANGFUSE_MEDIA_UPLOAD_ENABLED"] = "false"
    logging.getLogger("langfuse").setLevel(logging.CRITICAL)
    spec = importlib.util.spec_from_file_location("devin_export", Path(__file__).with_name("langfuse-export.py"))
    exporter = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(exporter)
    state = exporter.load_state()
    manifest = {"schema_version": 1, "base_url": host,
                "auth_fingerprint": hashlib.sha256(public.encode()).hexdigest(), "sessions": {}}
    reasons = Counter()
    session = requests.Session()
    session.auth = (public, secret)
    projector = Projector()
    try:
        for key, checkpoint in state.items():
            if not key.startswith("devin::") or checkpoint.get("version") == 2:
                continue
            sid = key[len("devin::"):]
            try:
                source = exporter.devin_messages(sid, earliest=True)
                if source is None:
                    reasons["unavailable_source"] += 1
                    continue
                messages, cwd = source
                turns = lh.build_turns(messages)
                cloud = fetch(session, host, sid)
                expected = projector.expected(turns, sid, cwd, cloud=cloud)
                result, reason = match(expected, cloud, sid)
                # No raw IO is retained in the resulting manifest.
                del cloud
                reasons[reason] += 1
                if result is not None:
                    result.update(legacy_fingerprint=digest(checkpoint),
                                  turns=exporter.turn_fingerprints(turns, sid, "devin", cwd,
                                                                  exporter.repo_metadata(cwd)))
                    manifest["sessions"][sid] = result
            except Exception as error:
                reasons["read_or_projection_error:" + type(error).__name__] += 1
            if sum(reasons.values()) % 5 == 0:
                print(json.dumps({"progress": sum(reasons.values()), "reasons": reasons}), flush=True)
    finally:
        projector.close()
        session.close()
    current = exporter.load_state()
    for sid, entry in list(manifest["sessions"].items()):
        if digest(current.get("devin::" + sid)) != entry["legacy_fingerprint"]:
            del manifest["sessions"][sid]
            reasons["verified"] -= 1
            reasons["checkpoint_changed_during_read"] += 1
    manifest["summary"] = dict(reasons)
    manifest["prepared_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest), encoding="utf-8")
    args.output.chmod(0o600)
    print(json.dumps({"complete": True, "summary": reasons,
                      "verified_sessions": len(manifest["sessions"])}), flush=True)


if __name__ == "__main__":
    main()
