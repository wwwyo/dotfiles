"""Exercise CLI error handling and dispatch recovery without live services."""

import json
import os
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).with_name("pr_triage.py")
FIXTURE = r'''
import json, os, re, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

tool = Path(sys.argv[0]).name
args = sys.argv[1:]
root = Path(os.environ['FIXTURE_ROOT'])
mode = os.environ['FIXTURE_MODE']
with (root / 'calls.jsonl').open('a') as f:
    f.write(json.dumps([tool, *args]) + '\n')

def reply(result):
    print(json.dumps({'ok': True, 'result': result}))

def error(code):
    print(json.dumps({'ok': False, 'error': {'code': code, 'message': code}}))
    sys.exit(1)

if tool == 'orca':
    if mode == 'invalid-json':
        print('not JSON')
        sys.exit(1)
    if mode == 'stderr':
        print('host unavailable', file=sys.stderr)
        sys.exit(1)
    if mode == 'nonzero-success':
        reply({'worktrees': []})
        sys.exit(1)
    if mode in ('denied', 'zero-error'):
        print(json.dumps({'ok': False, 'error': {'code': 'runtime_access_denied', 'message': 'permission denied'}}))
        sys.exit(0 if mode == 'zero-error' else 1)
    if args[:2] == ['worktree', 'ps']:
        reply({'worktrees': []})
    elif args[:2] == ['worktree', 'create']:
        if not (root / 'registered').exists():
            error('repo_not_found')
        reply({'worktree': {'id': 'fixture::checkout', 'path': str(root / 'checkout')},
               'startupTerminal': {'handle': 'fixture-agent'}})
    elif args[:2] == ['repo', 'add']:
        (root / 'registered').touch()
        reply({})
    elif args[:2] == ['terminal', 'create']:
        reply({'terminal': {'handle': 'fixture-agent'}})
    elif args[:2] == ['terminal', 'show']:
        reply({'terminal': {'agentIdentity': 'pi', 'executionHostId': 'local',
                            'worktreePath': str(root / 'checkout')}})
    elif args[:2] == ['terminal', 'wait']:
        reply({'wait': {'satisfied': True}})
    elif args[:2] == ['terminal', 'send']:
        if mode.startswith('unsupported'):
            if mode in ('unsupported-evidence', 'unsupported-stale', 'unsupported-user-only', 'unsupported-error'):
                cwd = str(root / 'checkout')
                folder = '--' + re.sub(r'[/\\:]', '-', cwd.lstrip('/')) + '--'
                target = Path(os.environ['PI_CODING_AGENT_DIR']) / 'sessions' / folder
                target.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now(timezone.utc)
                if mode == 'unsupported-stale':
                    timestamp -= timedelta(hours=1)
                events = [
                    {'type': 'session', 'cwd': cwd, 'id': 'fixture-session'},
                    {'type': 'message', 'timestamp': timestamp.isoformat(), 'id': 'user-1',
                     'message': {'role': 'user', 'content': [{'type': 'text', 'text': args[args.index('--text') + 1]}]}},
                    {'type': 'message', 'timestamp': timestamp.isoformat(), 'id': 'assistant-1',
                     'message': {'role': 'assistant', 'model': 'mimo-v2.6-flash', 'provider': 'opencode-go',
                                 'content': [{'type': 'text', 'text': 'started'}], 'stopReason': 'stop'}}]
                if mode == 'unsupported-error':
                    events[-1]['message'].update(content=[], stopReason='error', usage={'output': 0})
                if mode == 'unsupported-user-only':
                    events = events[:2]
                (target / 'fixture.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
            reply({'send': {'accepted': True, 'prompt': {
                'provider': 'unsupported', 'requestId': 'request-1', 'stages': ['input_accepted']}}})
        else:
            reply({'stage': 'turn_started'})
    else:
        raise AssertionError(args)
elif tool == 'gh':
    if args[:2] == ['pr', 'view']:
        print(json.dumps({'number': 30, 'state': 'OPEN', 'author': {'login': 'wwwyo'},
                          'headRefOid': 'fixture-sha', 'headRefName': 'wwwyo/fix',
                          'baseRefName': 'main', 'mergeable': 'MERGEABLE',
                          'title': 'fixture', 'url': 'https://github.com/wwwyo/fixture/pull/30'}))
    elif args[:2] == ['api', 'graphql']:
        print(json.dumps({'data': {'repository': {'pullRequest': {'reviewThreads': {
            'nodes': [], 'pageInfo': {'hasNextPage': False}}}}}}))
    elif any('/reviews' in a for a in args):
        print(json.dumps({'id': 'review-1', 'state': 'CHANGES_REQUESTED',
                          'submittedAt': '2026-10-01T00:00:00Z', 'body': 'fix this',
                          'author': {'login': 'pullfrog[bot]'}}))
    else:
        print(json.dumps({'contexts': []}))
elif tool == 'mise':
    assert args == ['x', '--', 'pi', '--offline', '--list-models']
    print('opencode-go mimo-v2.6-flash 1M 128K yes yes')
    print('opencode-go deepseek-v4.1-flash 1M 128K yes yes')
elif tool != 'git':
    raise AssertionError(tool)
'''


class OrcaCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pr-triage-orca-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        bins = self.root / "bin"
        bins.mkdir()
        for name in ("orca", "gh", "git", "mise"):
            exe = bins / name
            exe.write_text(f"#!{sys.executable}\n" + FIXTURE)
            exe.chmod(0o755)
        self.env = dict(os.environ, FIXTURE_ROOT=str(self.root),
                        ORCA_CLI_COMMAND=str(bins / "orca"),
                        PATH=str(bins) + os.pathsep + os.environ["PATH"],
                        PR_WATCH_STATE_DIR=str(self.root / "state"),
                        PR_WATCH_ME_REPO=str(self.root / "me"),
                        PI_CODING_AGENT_DIR=str(self.root / "pi"),
                        PR_WATCH_SEND_WAIT_S="0")

    def run_cli(self, mode, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args],
                              env=dict(self.env, FIXTURE_MODE=mode),
                              capture_output=True, text=True, timeout=20)

    def test_unregistered_repo_is_registered_and_dispatch_starts(self):
        # Use a unique canonical directory so recovery exercises the real path
        # check without changing HOME or touching an existing checkout.
        repos = Path.home() / "src/github.com/wwwyo"
        repos.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="pr-triage-test-", dir=repos) as repo:
            result = self.run_cli("register", "dispatch", "--repo",
                                  f"wwwyo/{Path(repo).name}", "--number", "30")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["dispatched"])
        calls = [json.loads(s) for s in (self.root / "calls.jsonl").read_text().splitlines()]
        self.assertEqual([c[1:3] for c in calls if c[0] == "orca"], [
            ["worktree", "ps"], ["worktree", "create"], ["repo", "add"],
            ["worktree", "create"], ["terminal", "create"],
            ["terminal", "wait"], ["terminal", "show"], ["terminal", "send"]])
        create_call = next(c for c in calls if c[:3] == ["orca", "terminal", "create"])
        command = shlex.split(create_call[create_call.index("--command") + 1])
        self.assertEqual(command[:5], ["mise", "x", "--", "pi", "--no-sandbox"])
        self.assertEqual(command[5:], ["--model", "opencode-go/mimo-v2.6-flash", "--thinking", "high"])
        checkout = next(i for i, c in enumerate(calls) if c[0] == "git" and "checkout" in c)
        launch = next(i for i, c in enumerate(calls) if c[:3] == ["orca", "terminal", "create"])
        self.assertLess(checkout, launch)

    def test_unsupported_receipt_uses_fresh_native_evidence(self):
        (self.root / "registered").touch()
        result = self.run_cli("unsupported-evidence", "dispatch", "--repo", "wwwyo/fixture", "--number", "30")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["dispatched"])
        state = json.loads((self.root / "state/state.json").read_text())
        self.assertNotIn("delivery_pending", state["prs"]["wwwyo/fixture#30"])
        self.assertEqual(len(state["prs"]["wwwyo/fixture#30"]["dispatches"]), 1)

    def test_unverified_input_is_not_resent_on_next_dispatch(self):
        (self.root / "registered").touch()
        for mode in ("unsupported-empty", "unsupported-stale", "unsupported-user-only", "unsupported-error"):
            with self.subTest(mode=mode):
                # Separate state between scenarios; preserve state within each pair.
                self.env["PR_WATCH_STATE_DIR"] = str(self.root / mode)
                first = self.run_cli(mode, "dispatch", "--repo", "wwwyo/fixture", "--number", "30")
                # 次 tick の gate が行う state 整理を挟んでも pending は残る。
                prune = subprocess.run([sys.executable, "-c",
                    "import importlib.util; s=importlib.util.spec_from_file_location('pt', " + repr(str(SCRIPT)) + "); "
                    "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
                    "st=m.load_state(); m.prune_state(st); m.save_state(st)"],
                    env=self.env, capture_output=True, text=True)
                self.assertEqual(prune.returncode, 0, prune.stdout + prune.stderr)
                second = self.run_cli(mode, "dispatch", "--repo", "wwwyo/fixture", "--number", "30")
                for result in (first, second):
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    output = json.loads(result.stdout)
                    self.assertFalse(output["dispatched"])
                    self.assertTrue(output["needs_escalate"])
                calls = [json.loads(s) for s in (self.root / "calls.jsonl").read_text().splitlines()]
                sends = [c for c in calls if c[:3] == ["orca", "terminal", "send"]]
                self.assertEqual(len(sends), 1)
                (self.root / "calls.jsonl").unlink()

    def test_parallel_dispatch_sends_once(self):
        (self.root / "registered").touch()
        args = [sys.executable, str(SCRIPT), "dispatch", "--repo", "wwwyo/fixture", "--number", "30"]
        env = dict(self.env, FIXTURE_MODE="unsupported-evidence")
        processes = [subprocess.Popen(args, env=env, stdout=subprocess.PIPE,
                                      stderr=subprocess.PIPE, text=True) for _ in range(2)]
        outputs = []
        for process in processes:
            stdout, stderr = process.communicate(timeout=30)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            outputs.append(json.loads(stdout))
        self.assertEqual(sum(result["dispatched"] for result in outputs), 1)
        calls = [json.loads(s) for s in (self.root / "calls.jsonl").read_text().splitlines()]
        self.assertEqual(sum(c[:3] == ["orca", "terminal", "send"] for c in calls), 1)

    def test_other_errors_fail_closed_with_diagnostics(self):
        for mode, expected in [("denied", "runtime_access_denied"),
                               ("zero-error", "runtime_access_denied"),
                               ("invalid-json", "invalid JSON response"),
                               ("stderr", "host unavailable"),
                               ("nonzero-success", "failed(1)")]:
            with self.subTest(mode=mode):
                result = self.run_cli(mode, "sweep", "--dry-run")
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn(expected, json.loads(result.stdout)["error"])
                self.assertFalse((self.root / "registered").exists())


if __name__ == "__main__":
    unittest.main()
