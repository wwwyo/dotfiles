#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

fail() { echo "FAIL: $*" >&2; exit 1; }

# codex は ~/.agents/skills を native discovery するので .codex/skills の symlink は対象外
for tool_dir in .claude/skills; do
  # 評価 workspace は skill の隣に置くため、entrypoint を持つ dir を検査する。
  for skill in .agents/skills/*/; do
    [ -f "$skill/SKILL.md" ] || continue
    name="$(basename "$skill")"
    link="$tool_dir/$name"
    [ -L "$link" ] || fail "$link is not a symlink"
    [ -e "$link" ] || fail "$link is dangling"
  done

  # tool 側の entry は .agents/skills 配下を指す symlink（.system はツール固有の実 dir なので除外）
  for link in "$tool_dir"/* "$tool_dir"/.[!.]*; do
    [ -e "$link" ] || [ -L "$link" ] || continue
    name="$(basename "$link")"
    [ "$name" = ".system" ] && continue
    [ -L "$link" ] || fail "$link is not a symlink"
    [ -e "$link" ] || fail "$link is dangling"
    [ -d ".agents/skills/$name" ] || fail "$link has no counterpart in .agents/skills"
    [ -f ".agents/skills/$name/SKILL.md" ] || fail "$link points to a directory without SKILL.md"
  done
done

echo "OK: .agents/skills is fully symlinked into .claude/skills"
