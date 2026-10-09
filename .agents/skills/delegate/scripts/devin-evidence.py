#!/usr/bin/env python3
"""Read Devin ATIF metadata and known transport events without printing content."""

import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import re
import sqlite3
import sys


def metadata(value):
    if value is None:
        return None
    if not isinstance(value, str) or not re.fullmatch(r"[\w .:+/-]{1,120}", value):
        raise ValueError("invalid_metadata")
    return value


def timestamp(value):
    if not isinstance(value, str):
        raise ValueError("invalid_timestamp")
    time = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if time.tzinfo is None:
        raise ValueError("timestamp_requires_timezone")
    return time.astimezone(timezone.utc).isoformat()


def transcript_summary(path, after_step):
    data = json.loads(path.read_text())
    if not isinstance(data, dict) or data.get("schema_version") != "ATIF-v1.7":
        raise ValueError("unsupported_transcript_schema")
    agent, steps = data.get("agent"), data.get("steps")
    if not isinstance(agent, dict) or not isinstance(steps, list):
        raise ValueError("invalid_transcript")
    selected, previous = [], 0
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("invalid_step")
        step_id, source = step.get("step_id"), step.get("source")
        if type(step_id) is not int or step_id <= previous or source not in ("system", "user", "agent"):
            raise ValueError("invalid_step")
        previous = step_id
        extra = step.get("extra") or {}
        if not isinstance(extra, dict):
            raise ValueError("invalid_step")
        row = {"step_id": step_id, "timestamp": timestamp(step.get("timestamp")), "source": source}
        row["model_name"] = metadata(step.get("model_name"))
        row["generation_model"] = metadata(extra.get("generation_model"))
        if step_id > after_step:
            selected.append(row)
    turns = []
    for row in selected:
        if row["source"] == "user":
            turns.append({"user_step_id": row["step_id"], "user_timestamp": row["timestamp"],
                          "agent_steps": 0, "first_agent_step_id": None, "last_agent_step_id": None})
        elif row["source"] == "agent" and turns:
            turn = turns[-1]
            turn["agent_steps"] += 1
            if turn["first_agent_step_id"] is None:
                turn["first_agent_step_id"] = row["step_id"]
                turn["first_agent_timestamp"] = row["timestamp"]
            turn["last_agent_step_id"] = row["step_id"]
            turn["last_agent_timestamp"] = row["timestamp"]
    agents = [row for row in selected if row["source"] == "agent"]
    models = Counter((row["model_name"], row["generation_model"]) for row in agents)
    return {"schema_version": data["schema_version"], "session_id": metadata(data.get("session_id")),
            "agent": {key: metadata(agent.get(key)) for key in ("name", "version", "model_name")},
            "last_step_id": previous, "after_step": after_step,
            "sources": dict(Counter(row["source"] for row in selected)),
            "models": [{"model_name": model, "generation_model": generation, "steps": count}
                       for (model, generation), count in models.items()],
            "last_user": next((row for row in reversed(selected) if row["source"] == "user"), None),
            "last_agent": agents[-1] if agents else None,
            "user_turns": len(turns), "latest_turns": turns[-5:]}


def log_summary(path):
    # Only exact logger/message combinations emit evidence; prompts can quote errors.
    header = re.compile(r"^(\S+)\s+(WARN|ERROR)\s+(connect_rpc::stream|inference::retry|affogato::agent::control_loop|run_acp_server: chisel_core::translator): (.*)$")
    events, unrecognized = [], 0
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as stream:
        for number, line in enumerate(stream, 1):
            match = header.match(line)
            if not match:
                continue
            time, level, component, text = match.groups()
            event = {"line": number, "timestamp": timestamp(time), "level": level, "component": component}
            if component == "connect_rpc::stream" and "HTTP body stream error while reading Connect response" in text:
                event["kind"] = "http_body_stream_error"
                event["unexpected_eof"] = "unexpected EOF during chunk size line" in text
                for key in ("is_timeout", "is_body", "is_decode"):
                    value = re.search(rf"\b{key}=(true|false)\b", text)
                    event[key] = value.group(1) == "true" if value else None
            elif component == "inference::retry" and "Backend stream creation failed" in text:
                event["kind"] = "backend_stream_creation_failed"
                status = re.search(r"\bHTTP ([45]\d\d)\b", text)
                event["http_status"] = int(status.group(1)) if status else None
            elif component == "affogato::agent::control_loop" and "Exhausted inference retries; stopping turn" in text:
                event["kind"] = "inference_retries_exhausted"
                attempts = re.search(r"\battempts=(\d+)\b", text)
                event["attempts"] = int(attempts.group(1)) if attempts else None
            elif component == "affogato::agent::control_loop" and "Transient inference error; retrying on next iteration" in text:
                event["kind"] = "transient_inference_retry"
                attempt = re.search(r"\battempt=(\d+)\s+max=(\d+)\b", text)
                if attempt:
                    event.update(attempt=int(attempt.group(1)), max_attempts=int(attempt.group(2)))
            elif component == "run_acp_server: chisel_core::translator" and "ACP: agent error (Unavailable): Connection error, send a message to continue retrying" in text:
                event["kind"] = "acp_unavailable_continue_required"
            else:
                unrecognized += 1
                continue
            events.append(event)
    return {"event_counts": dict(Counter(event["kind"] for event in events)),
            "events": events[-30:], "unrecognized_target_logger_lines": unrecognized,
            "attribution": "explicit_log_input_not_session_verified"}


def database_summary(path, session_id, since_time):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=2)) as db:
        db.execute("BEGIN")
        session = db.execute("SELECT model FROM sessions WHERE id=?", (session_id,)).fetchone()
        if session is None:
            raise ValueError("session_not_found")
        rows = db.execute("SELECT row_id, chat_message FROM message_nodes WHERE session_id=? ORDER BY row_id",
                          (session_id,)).fetchall()
    # Chain rewrites repeat IDs; row_id/DB created_at alone is not a turn watermark.
    messages = {}
    for row_id, raw in rows:
        message = json.loads(raw)
        if not isinstance(message, dict) or not isinstance(message.get("message_id"), str):
            raise ValueError("invalid_database_message")
        messages[message["message_id"]] = (row_id, message)
    agents, users, compactor = [], [], 0
    for row_id, message in messages.values():
        meta = message.get("metadata") or {}
        if not isinstance(meta, dict):
            raise ValueError("invalid_database_message")
        if message.get("role") != "assistant" and not meta.get("is_user_input"):
            continue
        time = timestamp(meta.get("started_generation_at") or meta.get("created_at"))
        if since_time and datetime.fromisoformat(time) <= datetime.fromisoformat(since_time):
            continue
        row = {"row_id": row_id, "timestamp": time}
        if message.get("role") == "assistant":
            row["generation_model"] = metadata(meta.get("generation_model"))
            if row["generation_model"] == "compactor":
                compactor += 1
            else:
                agents.append(row)
        elif meta.get("is_user_input"):
            users.append(row)
    agents.sort(key=lambda row: row["timestamp"])
    users.sort(key=lambda row: row["timestamp"])
    return {"session_id": session_id, "saved_model_not_execution_proof": metadata(session[0] or None),
            "raw_rows": len(rows), "unique_message_ids": len(messages),
            "after_time": since_time, "user_inputs": len(users), "agent_messages": len(agents),
            "compactor_messages": compactor,
            "generation_models": dict(Counter(row["generation_model"] for row in agents)),
            "latest_user_inputs": users[-5:], "last_agent": agents[-1] if agents else None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--session", help="Local session ID, not a resume command")
    inputs.add_argument("--transcript", type=Path, help="Explicit native ATIF-v1.7 JSON file")
    parser.add_argument("--after-step", type=int, default=0, help="Summarize only newer steps")
    parser.add_argument("--database", type=Path, help="Read sessions.db in mode=ro instead; requires --session")
    parser.add_argument("--after-time", help="For database only: ISO timestamp of last known generation/user input")
    parser.add_argument("--log", type=Path, action="append", default=[], help="Explicit CLI log or .gz (repeatable)")
    args = parser.parse_args()
    try:
        if args.after_step < 0:
            raise ValueError("invalid_after_step")
        if (args.database and (not args.session or args.after_step)) or (args.after_time and not args.database):
            raise ValueError("incompatible_arguments")
        path = args.transcript
        if args.session:
            if not re.fullmatch(r"[a-zA-Z0-9_-]{1,120}", args.session):
                raise ValueError("invalid_session_id")
            path = Path.home() / ".local/share/devin/cli/transcripts" / (args.session + ".json")
        evidence = {"database": database_summary(args.database, args.session,
                    timestamp(args.after_time) if args.after_time else None)} if args.database else {
                    "transcript": transcript_summary(path, args.after_step)}
        result = {"ok": True, **evidence,
                  "logs": [log_summary(path) for path in args.log],
                  "limitations": ["No message, reasoning, tool arguments, config or raw log text emitted",
                                  "Transcript progress is not completion or current process/network health",
                                  "Unrecognized log events are not classified; zero events does not prove health"]}
    except (OSError, ValueError, TypeError, KeyError, sqlite3.Error) as error:
        # JSONDecodeError and filesystem errors may quote content or sensitive paths.
        category = "evidence_read_failed"
        if isinstance(error, FileNotFoundError):
            category = "input_not_found"
        elif isinstance(error, json.JSONDecodeError):
            category = "invalid_json"
        elif isinstance(error, sqlite3.Error):
            category = "database_read_failed"
        print(json.dumps({"ok": False, "error": category,
                          "hint": "Check file existence, native schema and argument values locally"}))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
