#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHONDONTWRITEBYTECODE=1 python3 - "$repo_dir" <<'PY'
import ast
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
import tomllib

source = Path(sys.argv[1])
pr_workflow = (source / '.github/workflows/skillctrl.md').read_text()
upd_workflow = (source / '.github/workflows/skillctrl-update.md').read_text()
pr_compiled = (source / '.github/workflows/skillctrl.lock.yml').read_text()
upd_compiled = (source / '.github/workflows/skillctrl-update.lock.yml').read_text()
engine = (source / '.github/workflows/shared/skillctrl-engine.md').read_text()
test_workflow = (source / '.github/workflows/test.yml').read_text()


def runs(document, name):
    blocks = []
    lines = document.splitlines()
    for i, line in enumerate(lines):
        match = re.fullmatch(r'( *)- name: ' + re.escape(name), line)
        if not match:
            continue
        indent = len(match[1])
        for j in range(i + 1, len(lines)):
            if lines[j].startswith(' ' * (indent + 2) + 'run: '):
                value = lines[j].strip().removeprefix('run: ')
                if value != '|':
                    blocks.append(ast.literal_eval(value))
                    break
                body = []
                for row in lines[j + 1:]:
                    if row.strip() and len(row) - len(row.lstrip()) <= indent + 2:
                        break
                    body.append(row[indent + 4:])
                blocks.append('\n'.join(body) + '\n')
                break
    assert blocks, name
    return blocks


# The same trusted pin is read four times per workflow and once by test.yml.
for workflow in [pr_workflow, upd_workflow]:
    pin_scripts = runs(workflow, 'Read the trusted skillctrl pin')
    assert len(pin_scripts) == 4 and len(set(pin_scripts)) == 1
assert runs(test_workflow, 'Read the trusted skillctrl pin') == [pin_scripts[0]]
assert 'CHECKER_SOURCE: ${{ github.event.pull_request.base.sha || github.sha }}' in pr_workflow + upd_workflow
assert 'SKILLCTRL_BIN: ${{ steps.skillctrl-cli.outputs.binary }}' in pr_compiled + upd_compiled
assert '--mount /tmp/gh-aw:/tmp/gh-aw:rw' in pr_compiled + upd_compiled
assert "jq -e '.local.lock_changed == false'" in pr_workflow + upd_workflow

# PR check and scheduled update are separate workflows.
assert 'schedule:' not in pr_workflow and 'workflow_dispatch' not in pr_workflow
on_block = upd_workflow.split('on:', 1)[1].split('permissions:', 1)[0]
assert 'pull_request' not in on_block
assert 'cron: "0 0 * * 6"' in upd_workflow and 'workflow_dispatch' in upd_workflow
assert '--adapter git update' in upd_workflow
assert '--adapter git update' not in pr_workflow
# The check JSON predicate is read strictly in both workflows.
assert ".local.lock_changed | if type == \"boolean\"" in pr_workflow
assert ".local.lock_changed | if type == \"boolean\"" in upd_workflow
# The PR check may comment findings but never publishes skill content edits.
assert 'add-comment:' in pr_workflow
assert "add_comment" in pr_workflow
assert "allowed = re.compile(r'^(?:\\.agents/skillctrl/lock\\.json|\\.agents/skillctrl/upstreams\\.json|\\.agents/skillctrl/intents/lock\\.json)$')" in pr_workflow
assert "allowed = re.compile(r'^(?:\\.agents/skills/|skills-lock\\.json$|\\.agents/skillctrl/lock\\.json$|\\.agents/skillctrl/upstreams\\.json$|\\.agents/skillctrl/intents/lock\\.json$)')" in upd_workflow
# Both update publish lanes supersede an existing update branch tip so the
# push stays fast-forward when a previous draft PR is still open.
assert upd_workflow.count('merge -s ours') == 2
for stem in ['ci', 'lock', 'skillctrl', 'update', 'upstream']:
    assert not (source / '.agents/skillctrl' / (stem + '.py')).exists()
    assert stem + '.py' not in pr_workflow + upd_workflow + engine + pr_compiled + upd_compiled
for removed in ['SKILLCTRL_BIN" ci ', 'SKILLCTRL_BIN" plan', 'SKILLCTRL_BIN" prompt',
                'SKILLCTRL_BIN" schedule', '--repo ', 'worktree-provider',
                'skillctrl status', 'skillctrl schema']:
    assert removed not in pr_workflow + upd_workflow + engine, removed

binary = os.environ.get('SKILLCTRL_BIN')
if not binary:
    binary = subprocess.check_output(['mise', 'which', 'skillctrl'], cwd=source, text=True).strip()
assert Path(binary).is_file()
node = shutil.which('node')
assert node, 'Node is required to exercise the actual engine harness'

with tempfile.TemporaryDirectory(prefix='skillctrl-workflow-') as tmp:
    tmp = Path(tmp)
    root = tmp / 'repo'
    root.mkdir()
    artifacts = tmp / 'artifacts'
    artifacts.mkdir()
    cli_dir = tmp / 'cli'
    outputs = tmp / 'outputs'
    summary = tmp / 'summary'
    env = dict(os.environ, SKILLCTRL_BIN=binary, CI_DIR=str(artifacts),
               GITHUB_OUTPUT=str(outputs), GITHUB_STEP_SUMMARY=str(summary),
               GITHUB_ENV=str(tmp / 'env'), GH_TOKEN='fixture-read-token')

    def command(args, check=True, extra=None):
        result = subprocess.run(args, cwd=root, env=env | (extra or {}), text=True,
                                capture_output=True)
        if check and result.returncode:
            raise AssertionError(f'{args}:\n{result.stdout}\n{result.stderr}')
        return result

    def git(*args):
        return command(['git', *args]).stdout.strip()

    def write(path, value):
        dest = root / path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(value)

    def commit():
        git('add', '-A')
        git('-c', 'core.hooksPath=/dev/null', 'commit', '-qm', 'fixture')
        return git('rev-parse', 'HEAD')

    def run_step(document, name, check=True, extra=None, index=0):
        paths = {'/tmp/gh-aw/skillctrl-cli': str(cli_dir),
                 '/tmp/gh-aw/skillctrl': str(artifacts), '/tmp/skillctrl': str(tmp / 'ci')}
        script = re.sub('|'.join(re.escape(path) for path in paths),
                        lambda match: paths[match[0]], runs(document, name)[index])
        return command(['bash', '-euo', 'pipefail', '-c', script], check=check, extra=extra)

    git('init', '-q')
    git('config', 'user.name', 'Fixture')
    git('config', 'user.email', 'fixture@example.invalid')
    git('config', 'commit.gpgsign', 'false')
    lock_text = (source / 'home/dot_config/mise/mise.lock').read_text()
    toolchain = tomllib.loads(lock_text)['tools']['go'][0]['version']
    config = '''[tools]
"go:github.com/wwwyo/skillctrl" = "a931afd1294d7b07669e8659aadf0de9854c51fc"
go = "GO_FIXTURE_VERSION"
node = "24.21.0"
"npm:@earendil-works/pi-coding-agent" = "1.0.0"
unrelated = "9.9.9"
[settings]
pin = true
minimum_release_age = "7d"
[env]
UNRELATED_SECRET = "fixture-only-do-not-copy"
'''
    config = config.replace('GO_FIXTURE_VERSION', toolchain)
    write('home/dot_config/mise/config.toml', config)
    trusted_lock = re.search(r'(?ms)^\[\[tools\."go:github\.com/wwwyo/skillctrl"\]\]\n.*?(?=^\[\[tools\.|\Z)', lock_text)[0]
    trusted_go_lock = re.search(r'(?ms)^\[\[tools\.go\]\]\n.*?(?=^\[\[tools\.|\Z)', lock_text)[0]
    write('home/dot_config/mise/mise.lock', trusted_lock + trusted_go_lock + '[[tools.unrelated]]\nversion = "9.9.9"\n')
    write('home/dot_pi/agent/models.json', '{"fixture": true}')
    for name in ['imported', 'handwritten']:
        write('.agents/skills/' + name + '/SKILL.md', 'original body\n')
    write('skills-lock.json', json.dumps({'version': 3, 'skills': {
        'imported': {'source': 'fixture/source', 'sourceType': 'github',
                     'sourceUrl': 'https://example.invalid/source.git',
                     'skillPath': 'skills/imported/SKILL.md'}}}))
    write('.agents/skillctrl/upstreams.json', json.dumps({'version': 1, 'skills': {}}))
    write('.agents/skillctrl/intents/handwritten.md', 'intent does not opt in\n')
    write('.agents/skillctrl/intents/lock.json', json.dumps({'version': 2, 'skills': {
        'handwritten': 'legacy-hash'}}))
    base = commit()
    env.update(CHECKER_SOURCE=base, PR_BASE=base, PR_HEAD=base)

    # The trusted pin step rejects mutable refs and strips unrelated settings.
    run_step(pr_workflow, 'Read the trusted skillctrl pin')
    selected = tomllib.loads((cli_dir / 'mise.toml').read_text())
    assert selected == {'tools': {'go:github.com/wwwyo/skillctrl': 'a931afd1294d7b07669e8659aadf0de9854c51fc', 'go': toolchain},
                        'settings': {'pin': True, 'minimum_release_age': '7d'}}
    assert (cli_dir / 'mise.toml').read_text().count('pi-coding-agent') == 0
    assert (cli_dir / 'node.txt').read_text() == '24.21.0'
    assert (cli_dir / 'mise.lock').read_text() == trusted_lock + trusted_go_lock
    selected_lock = tomllib.loads((cli_dir / 'mise.lock').read_text())
    assert set(selected_lock['tools']) == {'go:github.com/wwwyo/skillctrl', 'go'}
    assert selected_lock['tools']['go'][0]['platforms.linux-x64']['checksum'].startswith('sha256:')
    for invalid_lock in [trusted_lock, trusted_lock + trusted_go_lock.replace('version = ' + json.dumps(toolchain), 'version = "0.0.0"')]:
        write('home/dot_config/mise/mise.lock', invalid_lock)
        rejected = commit()
        assert run_step(pr_workflow, 'Read the trusted skillctrl pin', check=False,
                        extra={'CHECKER_SOURCE': rejected}).returncode != 0
    write('home/dot_config/mise/mise.lock', trusted_lock + trusted_go_lock + '[[tools.unrelated]]\nversion = "9.9.9"\n')
    base = commit()
    env.update(CHECKER_SOURCE=base, PR_BASE=base, PR_HEAD=base)
    assert run_step(pr_workflow, 'Read the trusted skillctrl pin', check=False,
                    extra={'CHECKER_SOURCE': 'HEAD'}).returncode != 0

    # A stale accepted entry for an unregistered skill is reported as pending
    # cleanup without needing intent review.
    run_step(pr_workflow, 'Select changed skill inputs')
    plan = json.loads((artifacts / 'plan.json').read_text())
    assert plan['changed'] and not plan['needs_review']
    assert 'node=24.21.0\n' in outputs.read_text()
    assert 'source=' + base + '\n' in outputs.read_text()

    # The deterministic job prunes stale entries without accepting content.
    (tmp / 'ci').mkdir(exist_ok=True)
    run_step(pr_workflow, 'Apply imported originals and prune stale accepted hashes')
    stored = json.loads((root / '.agents/skillctrl/lock.json').read_text())
    assert stored['acceptedHashes'] == {}
    assert not (root / '.agents/skillctrl/intents/lock.json').exists()
    assert not (root / '.agents/skillctrl/upstreams.json').exists()
    base = commit()
    env['PR_BASE'] = base

    # An intent-only edit leaves the accepted lock aligned; the AI job and the
    # deterministic repair lane are both skipped.
    write('.agents/skillctrl/intents/handwritten.md', 'edited intent only\n')
    head = commit()
    env['PR_HEAD'] = head
    outputs.write_text('')
    run_step(pr_workflow, 'Select changed skill inputs')
    plan = json.loads((artifacts / 'plan.json').read_text())
    assert not plan['changed'] and not plan['needs_review']

    # Drift on an intent-bearing registered skill routes to the reviewer.
    write('.agents/skillctrl/intents/imported.md', 'preserve this criterion\n')
    write('.agents/skills/imported/SKILL.md', 'unaccepted edit\n')
    head = commit()
    env['PR_HEAD'] = head
    outputs.write_text('')
    run_step(pr_workflow, 'Select changed skill inputs')
    plan = json.loads((artifacts / 'plan.json').read_text())
    assert plan['changed'] and plan['needs_review']
    assert plan['review_skills'] == ['imported']

    # The PR publish scope admits only accepted-lock changes: a reviewer patch
    # that edits skill content is rejected before it can be applied.
    write('.agents/skills/imported/SKILL.md', 'auto-fix attempt\n')
    git('add', '-A')
    diff = git('diff', '--cached', 'HEAD')
    (artifacts / 'repair.patch').write_text(diff + '\n')
    git('reset', '--hard', '-q', 'HEAD')
    assert '.agents/skills/imported/SKILL.md' in diff
    result = run_step(pr_workflow, 'Validate repair scope and apply the patch', check=False)
    assert result.returncode != 0
    assert 'out-of-scope' in result.stderr + result.stdout
    # The same content edit is in scope for the scheduled update workflow.
    assert run_step(upd_workflow, 'Validate repair scope and apply the patch').returncode == 0
    git('reset', '--hard', '-q', 'HEAD')
    # A lock-only patch is publishable by the PR check.
    write('.agents/skillctrl/lock.json', json.dumps({'version': 1, 'upstreams': {}, 'acceptedHashes': {}}) + '\n')
    git('add', '-A')
    (artifacts / 'repair.patch').write_text(git('diff', '--cached', 'HEAD') + '\n')
    git('reset', '--hard', '-q', 'HEAD')
    assert run_step(pr_workflow, 'Validate repair scope and apply the patch').returncode == 0
    git('reset', '--hard', '-q', 'HEAD')

    # The engine harness resets to the selected head, runs the reviewer,
    # and exports a patch plus the offline check result.
    tools = tmp / 'tools'
    tools.mkdir()
    (artifacts / 'source.txt').write_text(base)
    (artifacts / 'plan.json').write_text(json.dumps({'head': head, 'review_skills': ['imported']}))
    prompt = artifacts / 'prompt.md'
    prompt.write_text('review contract\n')
    reviewer = tools / 'reviewer'
    reviewer.write_text('#!/usr/bin/env bash\nset -euo pipefail\n'
                        '"$SKILLCTRL_BIN" record imported\n'
                        'printf "criterion verified\\n"\n')
    reviewer.chmod(0o755)
    safe = tools / 'safeoutputs'
    safe.write_text('#!/usr/bin/env bash\nset -euo pipefail\nprintf "%s\\n" "$*" > "$HANDOFF"\n')
    safe.chmod(0o755)
    harness = textwrap.dedent(engine.split('    harness-script: |\n', 1)[1].split('\n---', 1)[0])
    harness = harness.replace("'/tmp/gh-aw/skillctrl'", json.dumps(str(artifacts)))
    script = artifacts / 'engine.cjs'
    script.write_text(harness)
    handoff = artifacts / 'handoff'
    env['PATH'] = str(tools) + os.pathsep + env['PATH']
    command([node, str(script), str(reviewer)], extra={
        'GH_AW_PROMPT': str(prompt), 'SKILL_MODEL': 'opencode-go/space-bunny-free',
        'OPENCODE_API_KEY': 'fixture-credential-never-publish', 'HANDOFF': str(handoff)})
    assert handoff.read_text().strip() == 'apply_skill_repairs --head ' + head
    patch = (artifacts / 'repair.patch').read_text()
    assert 'skillctrl/lock.json' in patch
    assert 'SKILL.md' not in patch
    result = json.loads((artifacts / 'result.json').read_text())
    assert result['check']['local']['lock_changed'] is False
    stored = json.loads((root / '.agents/skillctrl/lock.json').read_text())
    assert 'imported' in stored['acceptedHashes']

    # The publish gate fails closed while drift remains.
    gate_env = {'SELECT_RESULT': 'success', 'SELECT_PLAN': json.dumps(plan),
                'CHANGED': 'true', 'AUTHENTICATED': 'true'}
    assert run_step(pr_workflow, 'Report final skill hash alignment', check=False,
                    extra=gate_env).returncode != 0
    status_dir = tmp / 'ci-status'
    status_dir.mkdir()
    (status_dir / 'skillctrl-lock-state.json').write_text(
        json.dumps({'local': {'lock_changed': False}}))
    for workflow in [pr_workflow, upd_workflow]:
        assert run_step(workflow, 'Report final skill hash alignment', extra=gate_env).returncode == 0

print('OK: trusted CLI pin, separate workflows, strict gate, PR review scope, engine export and final gate')
PY
