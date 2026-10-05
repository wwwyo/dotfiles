#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$repo_dir" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

hook = Path(sys.argv[1]) / '.agents/hooks/deny-git-add-all.py'


def run(command, tool='Bash', timeout=10):
    payload = json.dumps({'tool_name': tool, 'tool_input': {'command': command}})
    result = subprocess.run(['python3', str(hook)], input=payload,
                            capture_output=True, text=True, timeout=timeout)
    return result.returncode


deny = [
    'git add -A',
    'git add --all',
    'git add .',
    'git add -Au',
    'git add -uA',
    'git -C dir add -A',
    'git -C some/dir -c core.x=1 add --all',
    'git add --verbose -A',
    'git add -- .',
    'cd sub && git add -A',
    'git status; git add .',
    'git -C add -A',  # dir 名が add の病理ケース
]
allow = [
    'git add ./foo.ts',
    'git add path/',
    'git add -u',
    'git add foo.ts bar.ts',
    'git commit -m "use git add -A carefully"',
    "echo 'git add --all is banned'",
    'cat <<EOF\ngit add -A\nEOF',
    'git status',
    'git add',               # 引数なし
    'git additions -A',      # add という substring だけでは止めない
    'git -C dir add -v foo', # -v だけなら通す
]
for command in deny:
    assert run(command) == 2, f'should deny: {command}'
    assert run(command, tool='exec') == 2, f'exec should deny: {command}'
for command in allow:
    assert run(command) == 0, f'should allow: {command}'

# CodeQL py/redos 指摘の病理入力: '-!' の繰り返しで指数的 backtracking しないこと
pathological = '&git\t' + '-!\t' * 20000
assert run(pathological, timeout=10) == 0, 'pathological input timed out or denied'
assert run('git ' + ' -x' * 2000 + ' add -A', timeout=10) == 2
print('deny-git-add-all: ok')
PY
