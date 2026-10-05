#!/usr/bin/env bash
# gitignore 済みの opt-in file は worktree に載らないので、main checkout から複製する。
# Orca / Codex の setup から絶対パスで呼ぶ。main checkout では no-op、無い file は skip。
set -eu

missing_only=0
case "${1-}" in
  --codex-session-start)
    session_cwd="$(python3 -c 'import json, sys; print(json.load(sys.stdin)["cwd"])')"
    cd "$session_cwd"
    missing_only=1
    ;;
  --help)
    printf '%s\n' '{"usage":"sync-local-worktree-files.sh [--codex-session-start]","default":"Copy local files from the main checkout into the current worktree","--codex-session-start":{"stdin":{"cwd":"string"},"behavior":"Copy only missing local files into a Codex-managed worktree"}}'
    exit 0
    ;;
  "") ;;
  *) echo "Unknown argument: $1" >&2; exit 2 ;;
esac

wt="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
# 保存先の名前では、変更された Codex の worktree root を判別できない。
if [ "$missing_only" = 1 ] && [ ! -f "$(dirname "$wt")/.codex-worktree-name" ]; then
  exit 0
fi
# `git worktree list` の先頭 entry が main checkout。git-common-dir の親を
# 推定する方法は --separate-git-dir の checkout で壊れるため使わない
main_root="$(git worktree list --porcelain | sed -n 's/^worktree //p' | head -1)"
if [ -z "$main_root" ] || [ "$wt" = "$main_root" ]; then
  exit 0
fi

for rel in mise.local.toml .claude/settings.local.json .codex/langfuse.json .pi/settings.json; do
  src="$main_root/$rel"
  [ -f "$src" ] || continue
  if [ "$missing_only" = 1 ] && { [ -e "$wt/$rel" ] || [ -L "$wt/$rel" ]; }; then
    continue
  fi
  mkdir -p "$wt/$(dirname "$rel")"
  cp "$src" "$wt/$rel"
done

# pi の install 先。settings.json だけ複製しても plugin は load されない
if [ -f "$wt/.pi/settings.json" ] && [ -d "$main_root/.pi/npm" ]; then
  # SessionStart は繰り返し発火するので、使用中の install 先を置き換えない。
  if [ "$missing_only" = 1 ] && { [ -e "$wt/.pi/npm" ] || [ -L "$wt/.pi/npm" ]; }; then
    exit 0
  fi
  tmp="$wt/.pi/.npm.sync-tmp"
  rm -rf "$tmp"
  cp -R "$main_root/.pi/npm" "$tmp"
  rm -rf "$wt/.pi/npm"
  mv "$tmp" "$wt/.pi/npm"
fi
