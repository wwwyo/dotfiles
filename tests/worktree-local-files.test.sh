#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python3 - "$repo_dir" <<'PY'
import os
from pathlib import Path
import subprocess
import sys
import tempfile

script = Path(sys.argv[1]) / '.agents/skills/project-setup/tools/sync-local-worktree-files.sh'
with tempfile.TemporaryDirectory(prefix='worktree local files ') as directory:
    root = Path(directory)
    main = root / 'main'
    worktree = root / 'custom location' / 'repo'
    nested = worktree / 'nested'
    nested.mkdir(parents=True)
    files = ['mise.local.toml', '.claude/settings.local.json', '.pi/settings.json', '.pi/langfuse.json', '.pi/npm/plugin.txt', '.pi/git/plugin.txt']
    for relative in files:
        source = main / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text('source')
    binaries = root / 'bin'
    binaries.mkdir()
    git = binaries / 'git'
    git.write_text('''#!/usr/bin/env python3
import os, sys
if sys.argv[1:] == ['rev-parse', '--show-toplevel']:
    if os.environ.get('NO_GIT'):
        sys.exit(128)
    print(os.environ['TEST_GIT_ROOT'])
elif sys.argv[1:] == ['worktree', 'list', '--porcelain']:
    print('worktree ' + os.environ['TEST_MAIN_ROOT'])
else:
    sys.exit(2)
''')
    git.chmod(0o755)
    env = {**os.environ, 'PATH': str(binaries) + os.pathsep + os.environ['PATH'], 'TEST_GIT_ROOT': str(worktree), 'TEST_MAIN_ROOT': str(main)}

    def run(*args, cwd=nested, extra_env=None):
        result = subprocess.run(['bash', str(script), *args], cwd=cwd, env={**env, **(extra_env or {})}, text=True, capture_output=True, check=True)
        assert result.stdout == '', result.stdout

    run(extra_env={'NO_GIT': '1'})
    assert not any((worktree / relative).exists() for relative in files), 'Non-Git directory must remain untouched'
    run(cwd=main, extra_env={'TEST_GIT_ROOT': str(main)})
    assert all((main / relative).read_text() == 'source' for relative in files), 'Main checkout must remain untouched'
    run()
    assert all((worktree / relative).read_text() == 'source' for relative in files)
    for relative in files:
        (worktree / relative).write_text('{"enabled":false}')
    run()
    assert all((worktree / relative).read_text() == 'source' for relative in files), 'Orca setup must refresh local files'

print('OK: worktree local files are copied from the main checkout only into linked worktrees')
PY
