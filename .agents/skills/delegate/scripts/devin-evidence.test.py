"""Black-box evidence-reader checks: privacy, schema failure and native DB rewrites."""

import gzip
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("devin-evidence.py")
SECRET = "private-test-token-DO-NOT-EMIT"


class EvidenceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.addCleanup(self.tmp.cleanup)

    def run_reader(self, *args, success=True):
        result = subprocess.run([sys.executable, str(SCRIPT), *map(str, args)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0 if success else 1, result.stdout)
        self.assertNotIn(SECRET, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["ok"], success)
        return data

    def transcript(self):
        path = self.root / "native.json"
        path.write_text(json.dumps({"schema_version": "ATIF-v1.7", "session_id": "fixture",
            "agent": {"name": "devin", "version": "3000.11.3", "model_name": "SWE-2 Medium"},
            "steps": [{"step_id": i, "source": source, "timestamp": f"2026-10-09T03:33:0{i}Z",
                       "message": SECRET, "reasoning_content": SECRET,
                       "tool_calls": [{"arguments": SECRET}],
                       "model_name": "swe-2-medium" if source == "agent" else None,
                       "extra": {"generation_model": "swe-2-medium" if source == "agent" else None}}
                      for i, source in enumerate(("system", "user", "agent", "user", "agent"), 1)]}))
        return path

    def test_transcript_progress_and_log_allowlist(self):
        path = self.transcript()
        log = self.root / "native.log.gz"
        with gzip.open(log, "wt") as stream:
            stream.write(f"2026-10-09T03:45:00Z INFO toolbox: command={SECRET} HTTP 502 Bad Gateway\n")
            stream.write(f"2026-10-09T03:45:01Z WARN connect_rpc::stream: is_timeout=false is_body=false is_decode=true error={SECRET} unexpected EOF during chunk size line HTTP body stream error while reading Connect response\n")
            stream.write(f"2026-10-09T03:45:02Z ERROR affogato::agent::control_loop: attempts=3 error={SECRET} Exhausted inference retries; stopping turn\n")
            stream.write(f"2026-10-09T03:45:03Z WARN inference::retry: unknown={SECRET}\n")
        data = self.run_reader("--transcript", path, "--after-step", 3, "--log", log)
        self.assertEqual(data["transcript"]["sources"], {"user": 1, "agent": 1})
        self.assertEqual(data["transcript"]["latest_turns"][0]["first_agent_step_id"], 5)
        self.assertEqual(data["transcript"]["models"][0]["generation_model"], "swe-2-medium")
        self.assertEqual(data["logs"][0]["event_counts"],
                         {"http_body_stream_error": 1, "inference_retries_exhausted": 1})
        self.assertEqual(data["logs"][0]["unrecognized_target_logger_lines"], 1)
        self.assertFalse(data["logs"][0]["events"][0]["is_timeout"])

    def test_fail_closed_without_raw_exception(self):
        path = self.root / "invalid.json"
        path.write_text(SECRET)
        self.run_reader("--transcript", path, success=False)
        path.write_text(json.dumps({"schema_version": "ATIF-v99", "message": SECRET}))
        self.run_reader("--transcript", path, success=False)
        self.run_reader("--session", "../escape", success=False)
        self.run_reader("--transcript", self.root / SECRET, success=False)

    def test_database_dedup_generation_time_and_read_only(self):
        path = self.root / "sessions.db"
        with sqlite3.connect(path) as db:
            db.executescript("CREATE TABLE sessions(id TEXT, model TEXT); CREATE TABLE message_nodes(row_id INTEGER, session_id TEXT, chat_message TEXT);")
            db.execute("INSERT INTO sessions VALUES (?, ?)", ("fixture", ""))
            for rid, mid, role, time, model in ((1, "u", "user", "03:00:00", None),
                    (2, "a", "assistant", "03:01:00", "swe-2-max"),
                    (3, "a", "assistant", "03:01:00", "swe-2-max"),
                    (4, "c", "assistant", "03:02:00", "compactor")):
                message = {"message_id": mid, "role": role, "content": SECRET,
                           "metadata": {"is_user_input": role == "user", "created_at": f"2026-10-09T{time}Z",
                                        "generation_model": model}}
                db.execute("INSERT INTO message_nodes VALUES (?, ?, ?)", (rid, "fixture", json.dumps(message)))
        before = path.read_bytes()
        data = self.run_reader("--session", "fixture", "--database", path)["database"]
        self.assertEqual((data["raw_rows"], data["unique_message_ids"], data["agent_messages"]), (4, 3, 1))
        self.assertEqual(data["generation_models"], {"swe-2-max": 1})
        self.assertIsNone(data["saved_model_not_execution_proof"])
        delta = self.run_reader("--session", "fixture", "--database", path,
                                "--after-time", "2026-10-09T12:01:00+09:00")["database"]
        self.assertEqual(delta["agent_messages"], 0)
        self.assertEqual(delta["compactor_messages"], 1)
        self.assertEqual(path.read_bytes(), before)
        missing = self.root / "missing.db"
        self.run_reader("--session", "fixture", "--database", missing, success=False)
        self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
