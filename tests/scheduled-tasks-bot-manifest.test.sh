#!/usr/bin/env bash
# bot automation の manifest が sync_automations.py で bot 用の flag に変換されることを検査する。
# daily-start / daily-end は Claude のクラウド routine に移したので、ここでは同じ形の manifest を組み立てて使う
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
python3 - <<'PYTHON'
import os
import sys
import tempfile
from pathlib import Path
sys.path.insert(0, '.agents/scheduled-tasks/tools')
import sync_automations as s

with tempfile.TemporaryDirectory() as d:
    p = Path(d) / 'automation.toml'
    p.write_text('name = "x"\nbot = "me"\nagent = "pi"\nruns_in = "new"\n'
                 'workdir = "~/w"\nprompt = "{{workdir}}/SKILL.md"\n')
    m = s.load_manifest(p)
    assert (m['bot'], m['agent'], m['runs_in']) == ('me', 'pi', 'new'), m
    assert os.path.expanduser('~/w/SKILL.md') in m['prompt'], m['prompt']
    f = s.expected_flags(m)
    assert f[f.index('--bot') + 1] == 'me' and f[f.index('--agent') + 1] == 'pi'
    assert not {'--provider', '--workspace', '--repo', '--reuse-session'} & set(f)
    # edit は --bot を受け付けない
    assert '--bot' not in s.expected_flags(m, {'bot': {'agentSetup': {'agent': 'pi'}}})

# 実 manifest がすべて load_manifest を通り、bot manifest は bot 用の flag だけになること
for toml in sorted(Path('.agents/scheduled-tasks').glob('*/automation.toml')):
    m = s.load_manifest(toml)
    if m.get('bot'):
        f = s.expected_flags(m)
        assert f[f.index('--bot') + 1] == m['bot'], toml
        assert not {'--provider', '--workspace', '--repo', '--reuse-session'} & set(f), toml

for bad in ('provider = "pi"', 'reuse_session = true', 'runs_in = "chat"'):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / 'automation.toml'
        p.write_text(f'name = "x"\nbot = "assist"\nagent = "pi"\nprompt = "p"\n{bad}\n')
        try:
            s.load_manifest(p)
        except RuntimeError:
            continue
        raise AssertionError(f'load_manifest が {bad} を通した')
PYTHON
echo "OK: scheduled-tasks bot manifest"
