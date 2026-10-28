"""Exercise CLI error handling and dispatch recovery without live services."""

import importlib.util
import json
import os
import shlex
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from types import SimpleNamespace
from datetime import datetime, timedelta, timezone


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
        worktrees = []
        if mode in ('busy-shell', 'busy-claude', 'recent-head', 'dirty'):
            worktrees = [{'worktreeId': 'fixture::checkout', 'path': str(root / 'checkout'),
                          'repo': 'fixture', 'branch': 'refs/heads/wwwyo/fix',
                          'status': 'inactive', 'agents': [], 'liveTerminalCount': 0}]
        reply({'worktrees': worktrees})
    elif args[:2] == ['terminal', 'list']:
        terms = []
        if mode.startswith('busy-'):
            terms = [{'handle': 'author', 'connected': True, 'status': 'running'}]
            if mode == 'busy-claude':
                terms[0]['agentIdentity'] = 'claude'
        reply({'terminals': terms})
    elif args[:2] == ['worktree', 'create']:
        if not (root / 'registered').exists():
            error('repo_not_found')
        reply({'worktree': {'id': 'fixture::checkout', 'path': str(root / 'checkout')},
               'startupTerminal': {'handle': 'fixture-agent'}})
    elif args[:2] == ['repo', 'add']:
        (root / 'registered').touch()
        reply({})
    elif args[:2] == ['repo', 'list']:
        repos = [{'path': str(root / 'checkout'), 'displayName': 'fixture'}] if (root / 'registered').exists() else []
        if mode == 'stale-candidate':
            repos.insert(0, {'path': str(root / 'stale'), 'displayName': 'fixture'})
        if mode == 'identity-fail':
            repos.insert(0, {'path': str(root / 'transferred'), 'displayName': 'fixture'})
        reply({'repos': repos})
    elif args[:2] == ['terminal', 'create']:
        reply({'terminal': {'handle': 'fixture-agent'}})
    elif args[:2] == ['terminal', 'show']:
        term = {'agentIdentity': 'pi', 'executionHostId': 'local'}
        if mode != 'unsupported-no-worktreepath':
            term['worktreePath'] = str(root / 'checkout')
        reply({'terminal': term})
    elif args[:2] == ['terminal', 'wait']:
        reply({'wait': {'satisfied': True}})
    elif args[:2] == ['terminal', 'send']:
        if mode.startswith('unsupported'):
            if mode in ('unsupported-evidence', 'unsupported-stale', 'unsupported-user-only', 'unsupported-error', 'unsupported-no-worktreepath'):
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
    if mode == 'enumerate-owners':
        assert args[:4] == ['api', '-X', 'GET', 'search/issues'], args
        assert 'q=is:pr is:open owner:wwwyo owner:fudoki-hensansitu' in args, args
        page = int(next(a.split('=', 1)[1] for a in args if a.startswith('page=')))
        owner = ['wwwyo', 'fudoki-hensansitu'][page - 1]
        print(json.dumps({'total_count': 2, 'items': [{
            'number': page, 'title': owner,
            'repository_url': 'https://api.github.com/repos/' + owner + '/fixture',
            'html_url': 'https://github.com/' + owner + '/fixture/pull/' + str(page),
            'user': {'login': 'wwwyo', 'type': 'User'}}]}))
    elif args[:1] == ['api'] and len(args) == 2 and args[1].startswith('repos/') \
            and args[1].count('/') == 2:
        if mode == 'identity-fail':
            print('gh: API rate limit exceeded', file=sys.stderr)
            sys.exit(1)
        print(json.dumps({'full_name': os.environ.get('FIXTURE_RESOLVED_REPO', args[1][6:])}))
    elif args[:2] == ['pr', 'view']:
        print(json.dumps({'number': 30, 'state': 'OPEN', 'author': {'login': 'wwwyo'},
                          'headRefOid': 'fixture-sha', 'headRefName': 'wwwyo/fix',
                          'updatedAt': datetime.now(timezone.utc).isoformat() if mode == 'recent-head' else '2026-10-01T00:00:00Z',
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
    print('opencode-go deepseek-v4.1-flash 1M 128K yes yes')
    print('opencode-go mimo-v2.6-flash 1M 128K yes yes')
elif tool == 'git':
    if '-C' in args and args[args.index('-C') + 1] == str(root / 'stale'):
        print('fatal: not a git repository', file=sys.stderr)
        sys.exit(128)
    if '-C' in args and args[args.index('-C') + 1] == str(root / 'transferred'):
        print('https://github.com/fudoki-hensansitu/fixture.git')
        sys.exit(0)
    if args[-3:] == ['remote', 'get-url', 'origin']:
        print('https://github.com/' + os.environ.get('FIXTURE_REMOTE', 'wwwyo/fixture') + '.git')
    elif mode == 'dirty':
        print(' M work.py')
else:
    raise AssertionError(tool)
'''


class OrcaCliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="pr-triage-orca-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'checkout').mkdir()
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

    def test_enumeration_includes_both_owners_across_pages(self):
        runner = """import importlib.util, json, sys
spec = importlib.util.spec_from_file_location('pt', sys.argv[1])
pt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pt)
print(json.dumps(pt.list_open_prs()))
"""
        result = subprocess.run([sys.executable, '-c', runner, str(SCRIPT)],
                                env=dict(self.env, FIXTURE_MODE='enumerate-owners'),
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual([(p['repo'], p['number']) for p in json.loads(result.stdout)],
                         [('wwwyo/fixture', 1), ('fudoki-hensansitu/fixture', 2)])

    def test_dispatch_cli_defers_without_starting_or_sending(self):
        for mode in ("busy-shell", "busy-claude", "recent-head", "dirty"):
            with self.subTest(mode=mode):
                (self.root / "calls.jsonl").unlink(missing_ok=True)
                result = self.run_cli(mode, "dispatch", "--repo", "wwwyo/fixture", "--number", "30")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                out = json.loads(result.stdout)
                self.assertFalse(out["dispatched"])
                self.assertTrue(out["defer"])
                calls = [json.loads(s) for s in (self.root / "calls.jsonl").read_text().splitlines()]
                orca_calls = [c[1:3] for c in calls if c[0] == "orca"]
                self.assertEqual(orca_calls, [["worktree", "ps"], ["terminal", "list"]])
                self.assertFalse((self.root / "state/state.json").exists())

    def registration_cli(self, repo="wwwyo/fixture", remote="wwwyo/fixture",
                         path_owner="wwwyo", resolved=None):
        # Keep the canonical-path fixture isolated; CI has no user's checkout.
        fixture_home = Path(tempfile.mkdtemp(dir=self.root))
        (fixture_home / "src/github.com" / path_owner / "fixture").mkdir(parents=True)
        (self.root / "registered").unlink(missing_ok=True)
        (self.root / "calls.jsonl").unlink(missing_ok=True)
        (self.root / "state/state.json").unlink(missing_ok=True)
        runner = """import runpy, sys
from pathlib import Path
from unittest.mock import patch
fixture_home, script, *args = sys.argv[1:]
sys.argv = [script, *args]
with patch.object(Path, 'home', return_value=Path(fixture_home)):
    runpy.run_path(script, run_name='__main__')
"""
        result = subprocess.run(
            [sys.executable, "-c", runner, str(fixture_home), str(SCRIPT),
             "dispatch", "--repo", repo, "--number", "30"],
            env=dict(self.env, FIXTURE_MODE="register", FIXTURE_REMOTE=remote,
                     FIXTURE_RESOLVED_REPO=resolved or remote),
            capture_output=True, text=True, timeout=20)
        return result

    def test_unregistered_repo_is_registered_and_dispatch_starts(self):
        result = self.registration_cli()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["dispatched"])
        calls = [json.loads(s) for s in (self.root / "calls.jsonl").read_text().splitlines()]
        self.assertEqual([c[1:3] for c in calls if c[0] == "orca"], [
            ["worktree", "ps"], ["repo", "list"], ["worktree", "create"], ["repo", "add"],
            ["worktree", "create"], ["terminal", "create"],
            ["terminal", "wait"], ["terminal", "show"], ["terminal", "send"]])
        create_call = next(c for c in calls if c[:3] == ["orca", "terminal", "create"])
        command = shlex.split(create_call[create_call.index("--command") + 1])
        self.assertEqual(command[:4], ["mise", "x", "--", "pi"])
        self.assertEqual(command[4:], ["--model", "opencode-go/deepseek-v4.1-flash", "--thinking", "high"])
        checkout = next(i for i, c in enumerate(calls) if c[0] == "git" and "checkout" in c)
        launch = next(i for i, c in enumerate(calls) if c[:3] == ["orca", "terminal", "create"])
        self.assertLess(checkout, launch)

    def test_stale_candidate_does_not_block_valid_checkout(self):
        (self.root / 'registered').touch()
        (self.root / 'stale').mkdir()
        result = self.run_cli('stale-candidate', 'dispatch', '--repo', 'wwwyo/fixture', '--number', '30')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)['dispatched'])
        calls = [json.loads(s) for s in (self.root / 'calls.jsonl').read_text().splitlines()]
        create = next(c for c in calls if c[:3] == ['orca', 'worktree', 'create'])
        self.assertEqual(create[create.index('--repo') + 1], f'path:{self.root / "checkout"}')

    def test_repeated_dispatch_errors_escalate_without_sending(self):
        args = ('dispatch', '--repo', 'wwwyo/fixture', '--number', '30')
        for count in range(1, 4):
            result = self.run_cli('denied', *args)
            self.assertEqual(result.returncode, 1 if count < 3 else 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)['needs_escalate'])
        state_path = self.root / 'state/state.json'
        state = json.loads(state_path.read_text())
        entry = state['prs']['wwwyo/fixture#30']
        self.assertEqual(entry['dispatch_failure']['count'], 3)
        self.assertEqual(entry['dispatches'], [])
        self.assertNotIn('delivery_pending', entry)
        (self.root / 'calls.jsonl').unlink()
        result = self.run_cli('denied', *args)
        self.assertTrue(json.loads(result.stdout)['needs_escalate'])
        calls = [json.loads(s) for s in (self.root / 'calls.jsonl').read_text().splitlines()]
        self.assertFalse(any(c[0] == 'orca' for c in calls))
        # Reaching the cap stops probes; a new head starts a fresh budget.
        result = self.run_cli('stderr', *args)
        self.assertTrue(json.loads(result.stdout)['needs_escalate'])
        entry['dispatch_failure']['sha'] = 'previous-head'
        state_path.write_text(json.dumps(state))
        result = self.run_cli('stderr', *args)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(state_path.read_text())['prs']['wwwyo/fixture#30']['dispatch_failure']['count'], 1)
        # Before the cap, a different error resets consecutive failures too.
        result = self.run_cli('denied', *args)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(json.loads(state_path.read_text())['prs']['wwwyo/fixture#30']['dispatch_failure']['count'], 1)

    def test_unresolvable_transfer_identity_does_not_abort_dispatch(self):
        # remote が別 owner を指す候補は gh api で引き直すが、その照会が失敗しても
        # 他の候補で canonical path が定まれば dispatch を続ける（fail-closed は
        # 候補が定まらないときだけ）。
        (self.root / 'registered').touch()
        (self.root / 'transferred').mkdir()
        result = self.run_cli('identity-fail', 'dispatch', '--repo', 'wwwyo/fixture', '--number', '30')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)['dispatched'])
        calls = [json.loads(s) for s in (self.root / 'calls.jsonl').read_text().splitlines()]
        create = next(c for c in calls if c[:3] == ['orca', 'worktree', 'create'])
        self.assertEqual(create[create.index('--repo') + 1], f'path:{self.root / "checkout"}')

    def test_stale_dispatch_failure_is_pruned(self):
        args = ('dispatch', '--repo', 'wwwyo/fixture', '--number', '30')
        self.run_cli('denied', *args)
        state_path = self.root / 'state/state.json'
        state = json.loads(state_path.read_text())
        entry = state['prs']['wwwyo/fixture#30']
        self.assertEqual(entry['dispatch_failure']['count'], 1)
        old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        entry['dispatch_failure']['at'] = old
        # 期限切れに加え、dispatch 履歴も古い entry は丸ごと消える
        entry['dispatches'] = [{'sha': 'old-head', 'sig': 'x', 'at': old}]
        state_path.write_text(json.dumps(state))
        prune = subprocess.run([sys.executable, "-c",
            "import importlib.util; s=importlib.util.spec_from_file_location('pt', " + repr(str(SCRIPT)) + "); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "st=m.load_state(); m.prune_state(st); m.save_state(st)"],
            env=self.env, capture_output=True, text=True)
        self.assertEqual(prune.returncode, 0, prune.stdout + prune.stderr)
        pruned = json.loads(state_path.read_text())
        self.assertNotIn('wwwyo/fixture#30', pruned.get('prs') or {})

    def test_fresh_dispatch_failure_survives_prune(self):
        args = ('dispatch', '--repo', 'wwwyo/fixture', '--number', '30')
        self.run_cli('denied', *args)
        state_path = self.root / 'state/state.json'
        state = json.loads(state_path.read_text())
        old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
        state['prs']['wwwyo/fixture#30']['dispatches'] = [{'sha': 'old-head', 'sig': 'x', 'at': old}]
        state_path.write_text(json.dumps(state))
        prune = subprocess.run([sys.executable, "-c",
            "import importlib.util; s=importlib.util.spec_from_file_location('pt', " + repr(str(SCRIPT)) + "); "
            "m=importlib.util.module_from_spec(s); s.loader.exec_module(m); "
            "st=m.load_state(); m.prune_state(st); m.save_state(st)"],
            env=self.env, capture_output=True, text=True)
        self.assertEqual(prune.returncode, 0, prune.stdout + prune.stderr)
        kept = json.loads(state_path.read_text())['prs']['wwwyo/fixture#30']
        self.assertEqual(kept['dispatch_failure']['count'], 1)

    def test_org_registration_accepts_current_and_transferred_checkout(self):
        for path_owner, remote in [('fudoki-hensansitu', 'fudoki-hensansitu/fixture'),
                                   ('wwwyo', 'wwwyo/fixture')]:
            with self.subTest(path_owner=path_owner):
                result = self.registration_cli(
                    repo='fudoki-hensansitu/fixture', remote=remote,
                    path_owner=path_owner, resolved='fudoki-hensansitu/fixture')
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertTrue(json.loads(result.stdout)['dispatched'])

    def test_registration_rejects_another_owners_same_name_checkout(self):
        result = self.registration_cli(repo='fudoki-hensansitu/fixture')
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn('canonical checkout ambiguous or unavailable', result.stdout)
        calls = [json.loads(s) for s in (self.root / 'calls.jsonl').read_text().splitlines()]
        self.assertFalse(any(c[:3] in [['orca', 'repo', 'add'],
                                      ['orca', 'worktree', 'create'],
                                      ['orca', 'terminal', 'create']] for c in calls))

    def test_unsupported_receipt_uses_fresh_native_evidence(self):
        (self.root / "registered").touch()
        result = self.run_cli("unsupported-evidence", "dispatch", "--repo", "wwwyo/fixture", "--number", "30")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["dispatched"])
        state = json.loads((self.root / "state/state.json").read_text())
        self.assertNotIn("delivery_pending", state["prs"]["wwwyo/fixture#30"])
        self.assertEqual(len(state["prs"]["wwwyo/fixture#30"]["dispatches"]), 1)

    def test_missing_worktree_path_uses_dispatch_worktree_evidence(self):
        # terminal の worktreePath が無くても、dispatch が知っている
        # 対象 worktree の path で session JSONL を探して送達を確認する。
        (self.root / "registered").touch()
        result = self.run_cli("unsupported-no-worktreepath", "dispatch",
                              "--repo", "wwwyo/fixture", "--number", "30")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["dispatched"])
        state = json.loads((self.root / "state/state.json").read_text())
        self.assertNotIn("delivery_pending", state["prs"]["wwwyo/fixture#30"])

    def test_escalate_reports_terminal_handle(self):
        # dispatch_failed で残った delivery_pending の handle を escalate が
        # 引き継ぎ、jsonl と戻り値に残す（人間の実査先）。
        (self.root / "registered").touch()
        self.run_cli("unsupported-error", "dispatch",
                     "--repo", "wwwyo/fixture", "--number", "30")
        result = self.run_cli("unsupported-error", "escalate",
                              "--repo", "wwwyo/fixture", "--number", "30",
                              "--reason", "unverified input")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        out = json.loads(result.stdout)
        self.assertTrue(out["escalated"])
        self.assertEqual(out["handle"], "fixture-agent")
        events = json.loads(self.run_cli(
            "unsupported-error", "events", "--event", "escalate").stdout)["events"]
        self.assertEqual(events[-1]["handle"], "fixture-agent")
        self.assertEqual(events[-1]["reason"], "unverified input")

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


class DispatchSafetyTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("triage_safety", SCRIPT)
        self.pt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.pt)
        self.now = datetime(2026, 10, 21, 3, 1, 42, tzinfo=timezone.utc)
        self.pt._now = lambda: self.now
        self.pr = dict(number=266, state="OPEN", isDraft=True,
                       headRefOid="dd2f9daa", headRefName="wwwyo/paddle-onnx-default",
                       mergeable="CONFLICTING", baseRefOid="base",
                       author={"login": "wwwyo"}, updatedAt="2026-10-21T02:38:11Z")
        self.w = dict(worktreeId="fixture::paddle", repo="fudoki", path="/fixture",
                      githubRepo="wwwyo/fudoki",
                      branch="refs/heads/wwwyo/paddle-onnx-default", status="inactive",
                      agents=[], liveTerminalCount=0)
        self.pt.sh = mock.Mock(return_value=SimpleNamespace(stdout=""))

    def route(self, terminals=(), worktree=True):
        return self.pt.checked_dispatch_route(
            [self.w] if worktree else [], {self.w["worktreeId"]: list(terminals)},
            "wwwyo/fudoki", self.pr)

    def old_head(self):
        self.pr["updatedAt"] = "2026-10-21T01:00:00Z"

    def test_dispatch_never_revives_another_owners_same_name_worktree(self):
        self.old_head()
        self.w['githubRepo'] = 'fudoki-hensansitu/fudoki'
        self.w['linkedPR'] = {'number': self.pr['number'], 'state': 'open'}
        self.assertEqual(self.route()['route'], 'spawn')
        self.w['githubRepo'] = None
        self.assertEqual(self.route()['route'], 'defer')

    def test_incident_pr_creation_and_recent_head_both_defer(self):
        # 12:01 tick / 11:38 PR creation, then head pushed a few minutes ago.
        for updated in ("2026-10-21T02:38:11Z", "2026-10-21T02:59:00Z"):
            with self.subTest(updated=updated):
                self.pr["updatedAt"] = updated
                self.assertEqual(self.route()["route"], "defer")
                self.assertEqual(self.route(worktree=False)["route"], "defer")

    def test_live_terminal_blocks_even_without_agent_identity_or_working_status(self):
        self.old_head()
        for term in ({"connected": True, "agentIdentity": "claude"},
                     {"connected": True}, {"agentIdentity": "claude"},
                     {"connected": True, "writable": False, "agentIdentity": "pi"}):
            with self.subTest(term=term):
                self.assertEqual(self.route([term])["route"], "defer")
        for field in ("liveTerminalCount", "unverifiableTerminalCount"):
            self.w[field] = 1
            self.assertEqual(self.route()["route"], "defer")
            self.w[field] = 0

    def test_dirty_and_git_failure_defer(self):
        self.old_head()
        for status in (" M source.py", "M  source.py", "?? output.json", "UU source.py"):
            self.pt.sh.return_value.stdout = status
            self.assertEqual(self.route()["reason"], "dirty worktree")
        self.pt.sh.side_effect = self.pt.ApiError("git timed out")
        self.assertEqual(self.route()["route"], "defer")

    def test_quiet_clean_unoccupied_worktree_can_revive(self):
        self.old_head()
        self.assertEqual(self.route([{"connected": False}])["route"], "revive")
        self.assertEqual(self.route(worktree=False)["route"], "spawn")

    def test_boundary_missing_invalid_and_future_timestamp(self):
        self.pr["updatedAt"] = self.pt._iso(self.now - timedelta(seconds=self.pt.DISPATCH_QUIET_S))
        self.assertEqual(self.route()["route"], "revive")
        for value in (None, "invalid", "2026-10-22T00:00:00Z"):
            self.pr["updatedAt"] = value
            self.assertEqual(self.route()["route"], "defer")

    def test_real_git_status_detects_index_and_untracked_changes(self):
        self.old_head()
        with tempfile.TemporaryDirectory(prefix="triage-dirty-") as tmp:
            subprocess.run(["git", "init", "-q", tmp], check=True)
            self.w["path"] = tmp
            spec = importlib.util.spec_from_file_location("triage_real_git", SCRIPT)
            real = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(real)
            self.pt.sh = real.sh
            self.assertEqual(self.route()["route"], "revive")
            target = Path(tmp) / "new.txt"
            target.write_text("work in progress")
            self.assertEqual(self.route()["reason"], "dirty worktree")
            subprocess.run(["git", "-C", tmp, "add", "new.txt"], check=True)
            self.assertEqual(self.route()["reason"], "dirty worktree")

    def test_plan_and_direct_dispatch_recheck_safety_before_any_mutation(self):
        facts = {"view": self.pr}
        items = [{"kind": "conflict", "body": "conflict"}]
        self.pt.dispatch_items = lambda *args: items
        self.pt.unaddressed_sig = lambda *args: "sig"
        self.pt.load_state = lambda: {}
        self.pt.pr_facts = lambda *args: facts
        self.pt.build_dispatch_message = lambda *args: "repair"
        self.pt.worktree_ps = lambda: [self.w]
        self.pt.terminal_list = lambda *args: [{"connected": True}]
        self.pt.orca_json = mock.Mock(side_effect=AssertionError("must not mutate Orca"))
        self.pt.save_state = mock.Mock(side_effect=AssertionError("must not consume dispatch budget"))
        self.pt.emit = mock.Mock()
        for recent, terminal, dirty in ((True, True, False), (False, True, False),
                                        (False, False, True)):
            with self.subTest(recent=recent, terminal=terminal, dirty=dirty):
                self.pr["updatedAt"] = "2026-10-21T02:59:00Z" if recent else "2026-10-21T01:00:00Z"
                terms = [{"connected": True}] if terminal else []
                self.pt.terminal_list = lambda *args: terms
                self.pt.sh.return_value.stdout = " M file" if dirty else ""
                entry = self.pt.compute_pr_decision(
                    {"repo": "wwwyo/fudoki", "number": 266}, facts,
                    [self.w], {self.w["worktreeId"]: terms}, {})
                self.assertEqual(entry["actions"][0]["type"], "hold")
                self.pt._cmd_dispatch(SimpleNamespace(repo="wwwyo/fudoki", number=266))
                self.assertFalse(self.pt.emit.call_args.args[0]["dispatched"])
                self.assertTrue(self.pt.emit.call_args.args[0]["defer"])
        self.pt.orca_json.assert_not_called()
        self.pt.save_state.assert_not_called()


class MergeableSettleTest(unittest.TestCase):
    """GitHub の mergeable は非同期計算のため、UNKNOWN の間だけ取り直す。"""

    def _load(self):
        spec = importlib.util.spec_from_file_location("pr_triage_under_test", SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        mod.MERGEABLE_RETRY_WAIT_S = 0  # テストでは sleep しない
        return mod

    def test_transient_unknown_is_refetched_until_settled(self):
        mod = self._load()
        seq = [{"mergeable": "UNKNOWN", "number": 1},
               {"mergeable": "MERGEABLE", "number": 1}]
        calls = []

        def fake_gh_json(args, **kwargs):
            calls.append(args)
            return dict(seq[min(len(calls) - 1, len(seq) - 1)])

        mod.gh_json = fake_gh_json
        view = mod.pr_view("wwwyo/fixture", 1)
        self.assertEqual(view["mergeable"], "MERGEABLE")
        self.assertEqual(len(calls), 2)

    def test_settled_mergeable_is_fetched_once(self):
        mod = self._load()
        calls = []

        def fake_gh_json(args, **kwargs):
            calls.append(args)
            return {"mergeable": "CONFLICTING", "number": 1}

        mod.gh_json = fake_gh_json
        view = mod.pr_view("wwwyo/fixture", 1)
        self.assertEqual(view["mergeable"], "CONFLICTING")
        self.assertEqual(len(calls), 1)

    def test_persistent_unknown_returns_after_bounded_retries(self):
        mod = self._load()
        calls = []

        def fake_gh_json(args, **kwargs):
            calls.append(args)
            return {"mergeable": "UNKNOWN", "number": 1}

        mod.gh_json = fake_gh_json
        view = mod.pr_view("wwwyo/fixture", 1)
        self.assertEqual(view["mergeable"], "UNKNOWN")
        self.assertEqual(len(calls), mod.MERGEABLE_RETRY)


if __name__ == "__main__":
    unittest.main()
