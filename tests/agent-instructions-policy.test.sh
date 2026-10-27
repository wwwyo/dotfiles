#!/usr/bin/env bash
# harness ごとの global instructions のうち、共通に揃っていなければならない
# 規則だけを比較する。他は harness 固有に違いうるので比較しない。
# Pi は Codex の AGENTS.md を symlink で読むため、実体は 3 file。
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

fail() { echo "FAIL: $*" >&2; exit 1; }

[ -L home/dot_pi/agent/AGENTS.md ] || fail "home/dot_pi/agent/AGENTS.md は symlink であるべき"
[ "$(readlink home/dot_pi/agent/AGENTS.md)" = "../../dot_codex/AGENTS.md" ] ||
  fail "home/dot_pi/agent/AGENTS.md の参照先が変わった（Codex と別の規則を読む）"

python3 - <<'PYTHON'
from pathlib import Path

paths = ["home/dot_codex/AGENTS.md", "home/dot_claude/CLAUDE.md",
         "home/dot_config/devin/AGENTS.md"]
policies = []
for path in paths:
    lines = [line.split("セキュリティ修正", 1)[1] for line in Path(path).read_text(encoding="utf-8").splitlines()
             if line.startswith("- package install ") and "セキュリティ修正" in line]
    if len(lines) != 1:
        raise SystemExit(f"FAIL: {path}: expected one security-update policy")
    policies.append(lines[0])
if len(set(policies)) != 1:
    raise SystemExit("FAIL: security-update policy differs across global instructions")
PYTHON

echo "OK: security-update policy agrees across harness instructions"
