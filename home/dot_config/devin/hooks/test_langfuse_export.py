#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["langfuse==4.15.4", "requests==2.34.2"]
# ///
"""Exporter regressions against the real pinned SDK and a local OTLP collector.

Run: uv run --script home/dot_config/devin/hooks/test_langfuse_export.py
No cloud credentials, transcripts, or external network are used.
"""
import json
import hashlib
import importlib.util
import runpy
from datetime import datetime, timezone
from types import SimpleNamespace
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest, ExportTraceServiceResponse,
)

SCRIPT = Path(__file__).with_name("langfuse-export.py")
SID = "fixture-session"
TS = "2026-10-04T00:00:00Z"


def message(role, mid, text="", *, tools=None, tool_id=None, timestamp=TS):
    row = {"role": role, "content": text, "metadata": {"created_at": timestamp}}
    if mid is not None:
        row["message_id"] = mid
    if tools is not None:
        row["tool_calls"] = tools
    if tool_id is not None:
        row["tool_call_id"] = tool_id
    return row


def call(tid="tool-1", name="exec", arguments="{}"):
    return {"id": tid, "name": name, "arguments": arguments}


def attributes(span):
    result = {}
    for a in span.attributes:
        field = a.value.WhichOneof("value")
        result[a.key] = getattr(a.value, field) if field else None
    return result


class Collector(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        self.spans = {}
        self.attempts = []
        self.ingestion_versions = []
        self.observations = []
        self.read_queries = []
        self.reject_name_once = None
        self.partial_name_once = None
        self.response_format = "json"
        self.mutex = threading.Lock()
        collector = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                query = parse_qs(urlsplit(self.path).query)
                collector.read_queries.append(query)
                rows = collector.observations
                # Emulate servers that ignore the shorthand sessionId parameter.
                if "filter" in query:
                    for condition in json.loads(query["filter"][0]):
                        if condition == {"type": "string", "column": "sessionId",
                                         "operator": "=", "value": SID}:
                            rows = [row for row in rows if row.get("sessionId") == SID]
                start = int(query.get("cursor", ["0"])[0])
                page = rows[start:start + 2]
                cursor = str(start + 2) if start + 2 < len(rows) else None
                body = json.dumps({"data": page, "meta": {"cursor": cursor}}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                data = self.rfile.read(int(self.headers["Content-Length"]))
                request = ExportTraceServiceRequest.FromString(data)
                spans = [s for resource in request.resource_spans
                         for scope in resource.scope_spans for s in scope.spans]
                with collector.mutex:
                    collector.attempts.extend(spans)
                    collector.ingestion_versions.append(self.headers.get("x-langfuse-ingestion-version"))
                    failed = any(s.name == collector.reject_name_once for s in spans)
                    partial = any(s.name == collector.partial_name_once for s in spans)
                    if failed:
                        collector.reject_name_once = None
                    else:
                        for span in spans:
                            if partial and span.name == collector.partial_name_once:
                                continue
                            collector.spans[(span.trace_id, span.span_id)] = span
                    if partial:
                        collector.partial_name_once = None
                reply = ExportTraceServiceResponse()
                if partial:
                    reply.partial_success.rejected_spans = 1
                    reply.partial_success.error_message = "fixture rejection"
                if collector.response_format == "json":
                    payload = {"id": "fixture-queue-ack"}
                    if partial:
                        payload["partialSuccess"] = {"rejectedSpans": "1"}
                    body = json.dumps(payload).encode()
                    content_type = "application/json"
                else:
                    body = reply.SerializeToString()
                    content_type = "application/x-protobuf"
                self.send_response(400 if failed else 200)
                self.send_header("Content-Type", content_type)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

        super().__init__(("127.0.0.1", 0), Handler)


class ExporterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["LANGFUSE_MEDIA_UPLOAD_ENABLED"] = "false"
        sys.path.insert(0, str(SCRIPT.parent))
        cls.exporter = SimpleNamespace(**runpy.run_path(str(SCRIPT)))
        spec = importlib.util.spec_from_file_location("fixture_reconciler", SCRIPT.with_name("langfuse_reconcile.py"))
        cls.reconciler = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.reconciler)
        cls.projector = cls.reconciler.Projector()

    @classmethod
    def tearDownClass(cls):
        cls.projector.close()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.home = Path(self.temp.name)
        self.db = self.home / ".local/share/devin/cli/sessions.db"
        self.db.parent.mkdir(parents=True)
        with closing(sqlite3.connect(self.db)) as c, c:
            c.executescript("""
                CREATE TABLE sessions (id TEXT, working_directory TEXT, hidden INTEGER, model TEXT);
                CREATE TABLE message_nodes (row_id INTEGER PRIMARY KEY, session_id TEXT, chat_message TEXT);
            """)
            c.execute("INSERT INTO sessions VALUES (?, ?, 0, 'fixture-model')",
                      (SID, str(self.home)))
        self.collector = Collector()
        self.thread = threading.Thread(target=self.collector.serve_forever, daemon=True)
        self.thread.start()
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(("LANGFUSE", "CC_LANGFUSE", "OTEL", "MISE_AGE"))}
        self.env.update(HOME=str(self.home), DEVIN_TRACE_TO_LANGFUSE="true",
                        LANGFUSE_PUBLIC_KEY="pk-lf-fixture", LANGFUSE_SECRET_KEY="sk-lf-fixture",
                        LANGFUSE_BASE_URL=f"http://127.0.0.1:{self.collector.server_port}",
                        DEVIN_LANGFUSE_DETAIL="full", LANGFUSE_FLUSH_AT="1", LANGFUSE_FLUSH_INTERVAL="3600",
                        LANGFUSE_MEDIA_UPLOAD_ENABLED="false", PYTHONDONTWRITEBYTECODE="1")
        self.state_file = self.home / ".local/state/langfuse-export/state.json"

    def tearDown(self):
        self.collector.shutdown()
        self.collector.server_close()
        self.thread.join()
        self.temp.cleanup()

    def add(self, *rows, row_id=None):
        with closing(sqlite3.connect(self.db)) as c, c:
            for row in rows:
                if row_id is None:
                    c.execute("INSERT INTO message_nodes(session_id,chat_message) VALUES (?,?)",
                              (SID, json.dumps(row)))
                else:
                    c.execute("INSERT INTO message_nodes VALUES (?,?,?)", (row_id, SID, json.dumps(row)))
                    row_id += 1

    def run_export(self, dry=False):
        result = subprocess.run([sys.executable, str(SCRIPT), "devin", SID,
                                 *(["--dry-run"] if dry else [])],
                                env=self.env, capture_output=True, text=True, timeout=35)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def state(self):
        return json.loads(self.state_file.read_text()) if self.state_file.exists() else {}

    def fixture(self):
        self.add(message("user", "user-1", "first request"),
                 message("assistant", "assistant-1", "thinking", tools=[call()]),
                 message("tool", "result-1", "done", tool_id="tool-1"),
                 message("assistant", "assistant-2", "first answer"))

    def types(self):
        return [attributes(s).get("langfuse.observation.type")
                for s in self.collector.spans.values()]

    def root(self, text):
        return next(s for s in self.collector.spans.values()
                    if text in str(attributes(s).get("langfuse.observation.input", ""))
                    and attributes(s).get("langfuse.observation.type") == "span")

    def assert_tree(self):
        for (tid, _), span in self.collector.spans.items():
            if span.parent_span_id:
                self.assertIn((tid, span.parent_span_id), self.collector.spans)
            attrs = attributes(span)
            self.assertEqual(attrs.get("session.id"), SID)

    def test_default_turn_mode_preserves_error_usage_and_resumed_identity(self):
        self.env.pop("DEVIN_LANGFUSE_DETAIL")
        first = message("assistant", "assistant-1", "thinking", tools=[call()])
        first["metadata"]["metrics"] = {"input_tokens": 100, "output_tokens": 20}
        self.add(message("user", "user-1", "first request"), first,
                 message("tool", "result-1", "Exit code: 1\ncommand failed", tool_id="tool-1"),
                 message("assistant", "assistant-2", "first answer"))
        self.run_export()
        self.assertEqual(len(self.collector.spans), 1)
        root = self.root("first request")
        summary = json.loads(attributes(root)["langfuse.observation.metadata.telemetry_summary"])
        self.assertEqual(summary["generation_count"], 2)
        self.assertEqual(summary["tool_names"], {"Tool: exec": 1})
        self.assertEqual(summary["tool_call_count"], 1)
        self.assertEqual(summary["errors"][0]["name"], "Tool: exec")
        self.assertIn("command failed", summary["errors"][0]["status_message"])
        self.assertEqual(summary["usage_by_model"]["fixture-model"], {"input": 100, "output": 20})
        attempts = len(self.collector.attempts)
        self.run_export()
        self.assertEqual(len(self.collector.attempts), attempts)
        self.add(message("assistant", "assistant-3", "resumed", tools=[call("tool-2")]),
                 message("tool", "result-2", "Exit code: 0\ndone", tool_id="tool-2"),
                 message("assistant", "assistant-4", "latest answer"))
        self.run_export()
        self.assertEqual(len(self.collector.spans), 1)
        updated = self.root("first request")
        self.assertEqual(root.span_id, updated.span_id)
        summary = json.loads(attributes(updated)["langfuse.observation.metadata.telemetry_summary"])
        self.assertEqual(summary["tool_call_count"], 2)
        self.assertEqual(len(summary["errors"]), 1)
        self.assertIn("latest answer", attributes(updated)["langfuse.observation.output"])

    def test_turn_mode_explicit_tool_error_is_retained(self):
        self.env["DEVIN_LANGFUSE_DETAIL"] = "turn"
        error = message("tool", "result-1", "permission denied", tool_id="tool-1")
        error["is_error"] = True
        self.add(message("user", "user-1", "first request"),
                 message("assistant", "assistant-1", "thinking", tools=[call()]), error,
                 message("assistant", "assistant-2", "first answer"))
        self.run_export()
        summary = json.loads(attributes(self.root("first request"))["langfuse.observation.metadata.telemetry_summary"])
        self.assertEqual(summary["errors"][0]["status_message"], "permission denied")

    def test_custom_exporter_sends_realtime_ingestion_header(self):
        self.fixture()
        self.run_export()
        self.assertTrue(self.collector.ingestion_versions)
        self.assertEqual(set(self.collector.ingestion_versions), {"4"})

    def test_unchanged_export_makes_no_second_request(self):
        self.fixture()
        self.run_export()
        self.assertEqual(len(self.collector.spans), 4)
        attempts = len(self.collector.attempts)
        self.run_export()
        self.assertEqual(len(self.collector.attempts), attempts)
        self.assert_tree()

    def test_standard_otlp_protobuf_success_commits_checkpoint(self):
        self.collector.response_format = "protobuf"
        self.fixture()
        self.run_export()
        self.assertEqual(len(self.collector.spans), 4)
        self.assertEqual(self.state()[f"devin::{SID}"]["version"], 2)
        attempts = len(self.collector.attempts)
        self.run_export()
        self.assertEqual(len(self.collector.attempts), attempts)

    def test_resumed_tail_preserves_ids_and_adds_generation_and_tool(self):
        self.fixture()
        self.run_export()
        before = set(self.collector.spans)
        old_root = self.root("first request")
        self.add(message("assistant", "assistant-3", "resumed", tools=[call("tool-2")]),
                 message("tool", "result-2", "next result", tool_id="tool-2"),
                 message("assistant", "assistant-4", "latest answer"))
        self.run_export()
        self.assertTrue(before <= set(self.collector.spans))
        self.assertEqual(len(self.collector.spans), 7)
        self.assertEqual(old_root.span_id, self.root("first request").span_id)
        self.assertIn("latest answer", attributes(self.root("first request"))["langfuse.observation.output"])
        self.assert_tree()

    def test_tool_ids_reused_in_distinct_source_messages_do_not_merge_calls(self):
        self.add(message("user", "user-1", "first request"),
                 message("assistant", "assistant-1", "first", tools=[call()]),
                 message("tool", "result-1", "one", tool_id="tool-1"),
                 message("assistant", "assistant-2", "second", tools=[call()]),
                 message("tool", "result-2", "two", tool_id="tool-1"))
        self.run_export()
        self.assertEqual(len(self.collector.spans), 5)
        self.assertEqual(len({s.span_id for s in self.collector.spans.values()}), 5)
        self.assert_tree()

    def test_same_source_revision_updates_output_and_tool_result(self):
        self.fixture()
        self.run_export()
        before = set(self.collector.spans)
        self.add(message("assistant", "assistant-2", "revised answer"),
                 message("tool", "result-1", "revised tool result", tool_id="tool-1"))
        self.run_export()
        self.assertEqual(before, set(self.collector.spans))
        self.assertIn("revised answer", attributes(self.root("first request"))["langfuse.observation.output"])
        tool = next(s for s in self.collector.spans.values() if s.name == "Tool: exec")
        self.assertIn("revised tool result", attributes(tool)["langfuse.observation.output"])

    def test_initial_export_keeps_unique_tools_from_all_source_revisions(self):
        self.add(message("user", "user-1", "first request"),
                 message("assistant", "assistant-1", "old text",
                         tools=[call("tool-old"), call("tool-shared", arguments="old")]),
                 message("tool", "result-old", "old result", tool_id="tool-old"),
                 message("assistant", "assistant-1", "new text",
                         tools=[call("tool-shared", arguments="updated"), call("tool-new")]),
                 message("tool", "result-shared", "shared result", tool_id="tool-shared"),
                 message("tool", "result-new", "new result", tool_id="tool-new"))
        self.run_export()
        self.assertEqual(len(self.collector.spans), 5)  # root + generation + three tools
        tools = [s for s in self.collector.spans.values()
                 if attributes(s).get("langfuse.observation.type") == "tool"]
        self.assertEqual(len(tools), 3)
        self.assertTrue(any("updated" in attributes(s)["langfuse.observation.input"]
                            for s in tools))
        self.assertIn("new text", attributes(self.root("first request"))["langfuse.observation.output"])
        self.assert_tree()
        attempts = len(self.collector.attempts)
        self.run_export()
        self.assertEqual(len(self.collector.attempts), attempts)

    def test_shifted_turn_number_and_start_time_preserve_source_identity(self):
        self.fixture()
        self.run_export()
        before = set(self.collector.spans)
        root_id = self.root("first request").span_id
        # Insert an earlier turn and revise the existing user timestamp.
        self.add(message("user", "earlier-user", "earlier request"),
                 message("assistant", "earlier-assistant", "earlier answer"), row_id=-2)
        self.add(message("user", "user-1", "first request", timestamp="2026-10-04T00:01:00Z"))
        self.run_export()
        self.assertTrue(before <= set(self.collector.spans))
        self.assertEqual(len(self.collector.spans), 6)
        self.assertEqual(root_id, self.root("first request").span_id)
        self.assertEqual(self.root("first request").name, "Devin - Turn 2")
        self.assert_tree()

    def test_same_turn_number_and_timestamp_with_distinct_user_ids_stays_distinct(self):
        self.fixture()
        self.run_export()
        old_ids = set(self.collector.spans)
        # Context rebuilding replaces its visible history with a different logical user.
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("DELETE FROM message_nodes")
        self.add(message("user", "different-user", "first request"),
                 message("assistant", "different-assistant", "other answer"))
        self.run_export()
        self.assertTrue(old_ids <= set(self.collector.spans))
        self.assertEqual(len(self.collector.spans), 6)
        self.assertEqual(len({tid for tid, _ in self.collector.spans}), 2)

    def test_shorter_later_snapshot_does_not_remove_prior_unique_observations(self):
        self.fixture()
        self.run_export()
        before = set(self.collector.spans)
        with closing(sqlite3.connect(self.db)) as c, c:
            c.execute("DELETE FROM message_nodes WHERE row_id IN (2,3)")
        self.add(message("assistant", "assistant-3", "another continuation", tools=[call("unique-tool")]))
        self.run_export()
        self.assertTrue(before <= set(self.collector.spans))
        self.assertEqual(len(self.collector.spans), 6)
        self.assert_tree()

    def test_http_failure_keeps_checkpoint_and_retry_does_not_duplicate_partial_delivery(self):
        self.fixture()
        self.collector.reject_name_once = "Tool: exec"
        self.run_export()
        partial = set(self.collector.spans)
        self.assertTrue(partial)
        self.assertFalse(self.state())
        self.run_export()
        self.assertEqual(len(self.collector.spans), 4)
        self.assertTrue(partial <= set(self.collector.spans))
        self.assertTrue(self.state()["devin::" + SID]["turns"])
        self.assert_tree()

    def test_json_otlp_partial_success_keeps_checkpoint_for_retry(self):
        self.fixture()
        self.collector.partial_name_once = "Tool: exec"
        self.run_export()
        self.assertFalse(self.state_file.exists())
        accepted = set(self.collector.spans)
        self.run_export()
        self.assertTrue(accepted <= set(self.collector.spans))
        self.assertEqual(len(self.collector.spans), 4)
        self.assertEqual(self.state()[f"devin::{SID}"]["version"], 2)

    def test_otlp_partial_success_is_retried_without_advancing_checkpoint(self):
        self.collector.response_format = "protobuf"
        self.fixture()
        self.collector.partial_name_once = "Tool: exec"
        self.run_export()
        self.assertFalse(self.state())
        partial = set(self.collector.spans)
        self.run_export()
        self.assertTrue(partial <= set(self.collector.spans))
        self.assertEqual(len(self.collector.spans), 4)
        self.assert_tree()

    def test_checkpoint_write_failure_replays_same_ids(self):
        self.fixture()
        self.state_file.parent.mkdir(parents=True)
        blocker = self.state_file.with_suffix(".tmp")
        blocker.mkdir()
        self.run_export()
        before = set(self.collector.spans)
        self.assertFalse(self.state())
        blocker.rmdir()
        self.run_export()
        self.assertEqual(before, set(self.collector.spans))
        self.assertTrue(self.state())

    def test_corrupt_checkpoint_blocks_export_without_resetting_history(self):
        self.fixture()
        self.run_export()
        saved = self.state_file.read_text()
        attempts = len(self.collector.attempts)
        self.state_file.write_text("invalid JSON")
        self.run_export()
        self.assertEqual(len(self.collector.attempts), attempts)
        self.assertEqual(self.state_file.read_text(), "invalid JSON")
        self.state_file.write_text(saved)
        self.run_export()
        self.assertEqual(len(self.collector.attempts), attempts)

    def legacy_state(self, turn_count=0, signature="2:assistant-2:1"):
        state = {"devin::" + SID: {"offset": 0, "turn_count": turn_count,
                                  "buffer": signature, "updated": TS},
                 "unrelated-session": {"keep": True}}
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state))
        return self.state_file.read_text()

    def test_legacy_checkpoint_never_replays_history_by_default(self):
        self.fixture()
        saved = self.legacy_state()
        for _ in range(2):
            self.run_export()
            self.assertFalse(self.collector.attempts)
            self.assertEqual(self.state()["devin::" + SID]["buffer"], "2:assistant-2:1")
        self.assertNotIn("version", self.state()["devin::" + SID])

    def test_legacy_appended_data_retains_old_exporter_behavior(self):
        self.fixture()
        saved = self.legacy_state()
        self.run_export()
        self.add(message("assistant", "assistant-3", "resumed", tools=[call("new-tool")]),
                 message("tool", "result-new", "new result", tool_id="new-tool"),
                 message("user", "user-2", "new request"),
                 message("assistant", "assistant-4", "new answer"))
        self.run_export()
        self.assertEqual(len(self.collector.spans), 8)
        self.assertEqual(self.state()["devin::" + SID]["turn_count"], 1)
        self.assertNotIn("version", self.state()["devin::" + SID])
        with closing(sqlite3.connect(self.db)) as c:
            self.assertEqual(c.execute("SELECT count(*) FROM message_nodes").fetchone()[0], 8)

    def test_partial_old_delivery_does_not_trigger_implicit_migration(self):
        self.fixture()
        self.collector.reject_name_once = "Tool: exec"
        self.run_export()
        self.assertTrue(self.collector.spans)
        self.assertFalse(self.state_file.exists())
        partial = set(self.collector.spans)
        attempts = len(self.collector.attempts)
        # The old exporter could save this checkpoint after a failed flush.
        saved = self.legacy_state()
        self.run_export()
        self.assertEqual(set(self.collector.spans), partial)
        self.assertEqual(len(self.collector.attempts), attempts)
        self.assertEqual(self.state()["devin::" + SID]["buffer"], "2:assistant-2:1")
        self.assertNotIn("version", self.state()["devin::" + SID])

    def test_legacy_checkpoint_past_visible_end_is_preserved_without_replay(self):
        self.fixture()
        saved = self.legacy_state(turn_count=999, signature="old")
        self.run_export()
        self.assertFalse(self.collector.attempts)
        self.assertEqual(self.state()["devin::" + SID]["turn_count"], 0)
        self.assertNotIn("version", self.state()["devin::" + SID])

    def cloud_fixture(self):
        rows = []
        for span in self.collector.spans.values():
            attrs = attributes(span)
            prefix = "langfuse.observation.metadata."
            rows.append({"id": span.span_id.hex(), "traceId": span.trace_id.hex(),
                         "parentObservationId": span.parent_span_id.hex() or None,
                         "type": attrs["langfuse.observation.type"].upper(),
                         "startTime": datetime.fromtimestamp(span.start_time_unix_nano / 1e9, timezone.utc).isoformat(),
                         "endTime": datetime.fromtimestamp(span.end_time_unix_nano / 1e9, timezone.utc).isoformat(),
                         "input": attrs.get("langfuse.observation.input"),
                         "output": attrs.get("langfuse.observation.output"),
                         "model": attrs.get("langfuse.observation.model.name"),
                         "metadata": {k[len(prefix):]: v for k, v in attrs.items() if k.startswith(prefix)},
                         "sessionId": SID, "projectId": "fixture-project"})
        return rows

    def test_reconcile_filters_only_requested_session_on_every_page(self):
        import requests
        self.fixture()
        self.run_export()
        cloud = self.cloud_fixture()
        self.collector.observations = cloud + [
            {**row, "sessionId": "other-session"} for row in cloud[:2]]
        with requests.Session() as session:
            rows = self.reconciler.fetch(session, self.env["LANGFUSE_BASE_URL"], SID)
        self.assertEqual(rows, cloud)
        self.assertEqual(len(self.collector.read_queries), 2)
        for query in self.collector.read_queries:
            self.assertEqual(json.loads(query["filter"][0]), [
                {"type": "string", "column": "sessionId", "operator": "=", "value": SID}])
            self.assertEqual(query["limit"], ["1000"])
            self.assertEqual(query["fields"], ["basic,time,metadata,io,model"])
        self.assertNotIn("cursor", self.collector.read_queries[0])
        self.assertEqual(self.collector.read_queries[1]["cursor"], ["2"])
        self.exporter.devin_messages.__globals__["DEVIN_DB"] = self.db
        messages, cwd = self.exporter.devin_messages(SID, earliest=True)
        expected = self.projector.expected(self.exporter.lh.build_turns(messages), SID, cwd)
        self.assertEqual(self.reconciler.match(expected, rows, SID)[1], "verified")
        self.assertEqual(self.reconciler.match(expected, self.collector.observations, SID)[1],
                         "session_mismatch")

    def prepare_verified(self):
        self.fixture()
        self.legacy_state(signature="")
        self.run_export()  # real legacy lane, random old cloud IDs
        self.exporter.devin_messages.__globals__["DEVIN_DB"] = self.db
        messages, cwd = self.exporter.devin_messages(SID, earliest=True)
        turns = self.exporter.lh.build_turns(messages)
        expected = self.projector.expected(turns, SID, cwd)
        cloud = self.cloud_fixture()
        entry, reason = self.reconciler.match(expected, cloud, SID)
        self.assertEqual(reason, "verified")
        entry.update(legacy_fingerprint=self.reconciler.digest(self.state()["devin::" + SID]),
                     turns=self.exporter.turn_fingerprints(turns, SID, "devin", cwd,
                                                           self.exporter.repo_metadata(cwd)))
        manifest = {"schema_version": 1, "base_url": self.env["LANGFUSE_BASE_URL"],
                    "auth_fingerprint": hashlib.sha256(self.env["LANGFUSE_PUBLIC_KEY"].encode()).hexdigest(),
                    "sessions": {SID: entry}}
        path = self.state_file.with_name("migrations.json")
        path.write_text(json.dumps(manifest))
        return expected, cloud, manifest, path

    def test_unique_cloud_mapping_migrates_with_zero_historical_sends(self):
        self.prepare_verified()
        old = set(self.collector.spans)
        attempts = len(self.collector.attempts)
        self.run_export()
        self.assertEqual(set(self.collector.spans), old)
        self.assertEqual(len(self.collector.attempts), attempts)
        self.assertEqual(self.state()["devin::" + SID]["version"], 2)
        self.assertEqual(len(self.state()["devin::" + SID]["identities"]), 4)
        self.run_export()
        self.assertEqual(len(self.collector.attempts), attempts)

    def test_missing_cloud_node_rejects_migration(self):
        expected, cloud, _, _ = self.prepare_verified()
        self.assertEqual(self.reconciler.match(expected, cloud[:-1], SID)[1], "missing_cloud_match")

    def test_ambiguous_cloud_and_source_nodes_reject_migration(self):
        expected, cloud, _, _ = self.prepare_verified()
        root = next(row for row in cloud if row["parentObservationId"] is None)
        extra = {**root, "id": "f" * 16, "traceId": "e" * 32}
        self.assertEqual(self.reconciler.match(expected, cloud + [extra], SID)[1], "ambiguous_cloud_match")
        local_root = next(row for row in expected if row["parent"] is None)
        self.assertEqual(self.reconciler.match(expected + [{**local_root, "id": "d" * 16}], cloud, SID)[1],
                         "ambiguous_source")

    def test_append_after_verified_migration_preserves_old_cloud_ids(self):
        self.prepare_verified()
        self.run_export()
        old = set(self.collector.spans)
        self.add(message("assistant", "assistant-3", "resumed", tools=[call("new-tool")]),
                 message("tool", "result-new", "new result", tool_id="new-tool"),
                 message("assistant", "assistant-4", "new answer"))
        self.run_export()
        self.assertTrue(old <= set(self.collector.spans))
        self.assertEqual(len(self.collector.spans), 7)
        self.assert_tree()

    def test_partial_failed_verified_transition_retries_under_same_cloud_ids(self):
        self.prepare_verified()
        saved = self.state_file.read_text()
        self.add(message("assistant", "assistant-3", "resumed", tools=[call("new-tool")]),
                 message("tool", "result-new", "new result", tool_id="new-tool"))
        self.collector.reject_name_once = "Tool: exec"
        self.run_export()
        partial = set(self.collector.spans)
        self.assertEqual(self.state_file.read_text(), saved)
        self.run_export()
        self.assertTrue(partial <= set(self.collector.spans))
        self.assertEqual(len(self.collector.spans), 6)
        self.assertEqual(self.state()["devin::" + SID]["version"], 2)
        self.assert_tree()

    def test_stale_manifest_falls_back_without_stopping_new_exports(self):
        _, _, manifest, path = self.prepare_verified()
        manifest["sessions"][SID]["legacy_fingerprint"] = "0" * 64
        path.write_text(json.dumps(manifest))
        self.add(message("user", "user-2", "another request"),
                 message("assistant", "assistant-3", "another answer"))
        self.run_export()
        self.assertEqual(len(self.collector.spans), 6)
        self.assertNotIn("version", self.state()["devin::" + SID])

    def test_manifest_for_other_credentials_is_not_adopted(self):
        _, _, manifest, path = self.prepare_verified()
        manifest["auth_fingerprint"] = "0" * 64
        path.write_text(json.dumps(manifest))
        self.run_export()
        self.assertNotIn("version", self.state()["devin::" + SID])

    def test_missing_source_ids_and_repeated_identical_tools_remain_distinct(self):
        self.add(message("user", None, "same request"),
                 message("assistant", None, "answer", tools=[call(None), call(None)]),
                 message("user", None, "same request"),
                 message("assistant", None, "answer"))
        self.run_export()
        before = set(self.collector.spans)
        self.assertEqual(len(before), 6)
        self.assertEqual(len({tid for tid, _ in before}), 2)
        self.run_export()
        self.assertEqual(before, set(self.collector.spans))
        self.assert_tree()

    def test_opt_out_and_dry_run_do_not_send_or_checkpoint(self):
        self.fixture()
        self.env["DEVIN_TRACE_TO_LANGFUSE"] = "false"
        self.run_export()
        self.run_export(dry=True)
        self.assertFalse(self.collector.attempts)
        self.assertFalse(self.state())

    def test_parallel_hook_runs_share_one_checkpoint(self):
        self.fixture()
        args = [sys.executable, str(SCRIPT), "devin", SID]
        children = [subprocess.Popen(args, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    for _ in range(2)]
        for child in children:
            _, err = child.communicate(timeout=35)
            self.assertEqual(child.returncode, 0, err.decode())
        self.assertEqual(len(self.collector.spans), 4)
        self.assertEqual(len(self.collector.attempts), 4)
        self.assert_tree()


if __name__ == "__main__":
    unittest.main()
