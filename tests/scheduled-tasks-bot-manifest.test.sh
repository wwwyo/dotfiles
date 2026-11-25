#!/usr/bin/env bash
# bot automation の manifest が sync_automations.py で bot 用の flag に変換されること、
# personal データを扱う daily-start / daily-end が pi で wwwyo/me を対象に走ることを検査する
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 - <<'PYTHON'
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, '.agents/scheduled-tasks/tools')
import sync_automations as s

me = os.path.expanduser('~/src/github.com/wwwyo/me')
for name in ('daily-start', 'daily-end'):
    m = s.load_manifest(Path(f'.agents/scheduled-tasks/{name}/automation.toml'))
    assert (m['bot'], m['agent'], m['runs_in']) == ('me', 'pi', 'new'), m
    assert f'{me}/.agents/skills/{name}/SKILL.md' in m['prompt']
    f = s.expected_flags(m)
    assert f[f.index('--bot') + 1] == 'me' and f[f.index('--agent') + 1] == 'pi'
    assert not {'--provider', '--workspace', '--repo', '--reuse-session'} & set(f)
    # edit は --bot を受け付けない
    assert '--bot' not in s.expected_flags(m, {'bot': {'agentSetup': {'agent': 'pi'}}})

for bad in ('provider = "pi"', 'reuse_session = true', 'runs_in = "chat"'):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'automation.toml'
        p.write_text(f'name = "x"\nbot = "me"\nagent = "pi"\nprompt = "p"\n{bad}\n')
        try:
            s.load_manifest(p)
        except RuntimeError:
            continue
        raise AssertionError(f'load_manifest が {bad} を通した')
PYTHON
echo "OK: scheduled-tasks bot manifest"
