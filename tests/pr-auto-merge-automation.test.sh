#!/usr/bin/env bash
# pr-auto-merge の automation prompt が skill（wwwyo/skills）の同実行 merge を打ち消さないこと、
# skill の参照先が canonical checkout であることを検査する
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 - <<'PYTHON'
import tomllib
from pathlib import Path
automation = tomllib.loads(Path('.agents/scheduled-tasks/pr-auto-merge/automation.toml').read_text())
prompt = automation['prompt']
assert 'merge_ready: true' in prompt
assert 'ok でも merge action は追加せず' not in prompt
skill = '~/src/github.com/wwwyo/skills/.agents/skills/pr-auto-merge/'
assert skill in prompt and skill in automation['precheck']
assert '~/.agents/skills' not in prompt + automation['precheck']
PYTHON
echo "OK: pr-auto-merge automation"
