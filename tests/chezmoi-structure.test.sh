#!/usr/bin/env bash
# chezmoi source layout の構造的な検証。
# - home/ 配下は chezmoi 命名（dot_/private_/Library/run_*/.chezmoi*）のみ
# - run_after link script の link 対象 source dir が repo に存在する
# - repo root の deploy 対象 dir が link 対象リストから漏れていない
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

fail() { echo "FAIL: $*" >&2; exit 1; }

# --- home/ 直下の命名規則 ---
# 許可: .chezmoi* / dot_* / private_* / Library/ / run_* / symlink_*
# dot_* 等の dir の内側は literal な target 名なのでチェック対象外
for entry in home/* home/.[!.]*; do
  [ -e "$entry" ] || [ -L "$entry" ] || continue
  rel="${entry#home/}"
  case "$rel" in
    .chezmoi*|Library|dot_*|private_*|run_*|symlink_*) ;;
    *) fail "home/ 直下に chezmoi 命名でない entry: $rel" ;;
  esac
done

# --- run_after link script の source dir が存在する ---
link_script="home/run_after_20-link-repodirs.sh.tmpl"
[ -f "$link_script" ] || fail "$link_script not found"
while IFS= read -r src; do
  # "$WT/..." → repo 相対パス
  rel="${src#\"\$WT/}"
  rel="${rel%\"}"
  # link_dir は source 不在時に skip するので、存在しない entry は warn のみ
  [ -d "$repo_dir/$rel" ] || echo "warn: link 対象 source dir が存在しない (skip される): $rel"
done < <(grep -o '"\$WT/[^"]*"' "$link_script")

# --- home/ 内の nested dotfile は chezmoi が暗黙に無視するので禁止 ---
# deploy したい hidden file は dot_ prefix に rename する
while IFS= read -r f; do
  fail "home/ 内の nested dotfile（chezmoi が deploy しない）: ${f#home/} → dot_ に rename する"
done < <(find home -mindepth 2 -name '.*' ! -name '.chezmoi*')

# --- repo root の deploy 対象 dir が link list に含まれる ---
# repo 内部用途の dir は allowlist（deploy 対象外）
internal=(.cursor .github .agent .git)
for entry in .[!.]*/; do
  dir="${entry%/}"
  case " ${internal[*]} " in *" $dir "*) continue ;; esac
  # Tool caches are not deploy candidates; tracked files still require a link.
  if [ -z "$(git ls-files -- "$dir/")" ] && git check-ignore -q "$dir/"; then
    continue
  fi
  grep -q "\$WT/$dir" "$link_script" || \
    fail "$dir は deploy 対象候補だが link script にも internal allowlist にも無い"
done

# Shared security-update policy must agree across harnesses; other instructions
# may intentionally differ. Reading the Pi link also detects a broken target.
python3 - <<'PYTHON'
from pathlib import Path
paths = ["home/dot_codex/AGENTS.md", "home/dot_claude/CLAUDE.md",
         "home/dot_config/devin/AGENTS.md", "home/dot_pi/agent/AGENTS.md"]
policies = []
for path in paths:
    lines = [line.split("セキュリティ修正", 1)[1] for line in Path(path).read_text().splitlines()
             if line.startswith("- package install ") and "セキュリティ修正" in line]
    if len(lines) != 1:
        raise SystemExit(f"FAIL: {path}: expected one security-update policy")
    policies.append(lines[0])
if len(set(policies)) != 1:
    raise SystemExit("FAIL: security-update policy differs across global instructions")
PYTHON

echo "OK: chezmoi source layout is consistent"
