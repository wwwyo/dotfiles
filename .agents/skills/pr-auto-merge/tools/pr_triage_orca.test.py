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
import json, os, sys
from pathlib import Path

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
    elif args[:2] == ['terminal', 'wait']:
        reply({'wait': {'satisfied': True}})
    elif args[:2] == ['terminal', 'send']:
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
        for name in ("orca", "gh", "git"):
            exe = bins / name
            exe.write_text(f"#!{sys.executable}\n" + FIXTURE)
            exe.chmod(0o755)
        self.env = dict(os.environ, FIXTURE_ROOT=str(self.root),
                        ORCA_CLI_COMMAND=str(bins / "orca"),
                        PATH=str(bins) + os.pathsep + os.environ["PATH"],
                        PR_WATCH_STATE_DIR=str(self.root / "state"),
                        PR_WATCH_ME_REPO=str(self.root / "me"))

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
            ["terminal", "wait"], ["terminal", "send"]])
        create_call = next(c for c in calls if c[:3] == ["orca", "terminal", "create"])
        command = shlex.split(create_call[create_call.index("--command") + 1])
        self.assertEqual(command[:5], ["mise", "x", "--", "pi", "--no-sandbox"])
        self.assertEqual(command[5:], ["--model", "opencode-go/mimo-v2.6-flash", "--thinking", "high"])
        checkout = next(i for i, c in enumerate(calls) if c[0] == "git" and "checkout" in c)
        launch = next(i for i, c in enumerate(calls) if c[:3] == ["orca", "terminal", "create"])
        self.assertLess(checkout, launch)

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
