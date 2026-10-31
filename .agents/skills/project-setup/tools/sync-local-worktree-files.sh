#!/usr/bin/env bash
# gitignore 済みの opt-in file は worktree に載らないので、main checkout から複製する。
# Orca の setup から絶対パスで呼ぶ。main checkout では no-op、無い file は skip。
set -eu

case "${1-}" in
  --help)
    printf '%s\n' '{"usage":"sync-local-worktree-files.sh","default":"Copy local files from the main checkout into the current worktree"}'
    exit 0
    ;;
  "") ;;
  *) echo "Unknown argument: $1" >&2; exit 2 ;;
esac

wt="$(git rev-parse --show-toplevel 2>/dev/null)" || exit 0
# `git worktree list` の先頭 entry が main checkout。git-common-dir の親を
# 推定する方法は --separate-git-dir の checkout で壊れるため使わない
main_root="$(git worktree list --porcelain | sed -n 's/^worktree //p' | head -1)"
if [ -z "$main_root" ] || [ "$wt" = "$main_root" ]; then
  exit 0
fi

for rel in mise.local.toml .claude/settings.local.json .pi/settings.json .pi/langfuse.json; do
  src="$main_root/$rel"
  [ -f "$src" ] || continue
  mkdir -p "$wt/$(dirname "$rel")"
  cp "$src" "$wt/$rel"
done

# pi の install 先（npm: package は .pi/npm、git: package は .pi/git）。
# settings.json だけ複製すると、trust 後の初回起動で install し直すまで plugin が load されない
if [ -f "$wt/.pi/settings.json" ]; then
  for dir in npm git; do
    [ -d "$main_root/.pi/$dir" ] || continue
    tmp="$wt/.pi/.$dir.sync-tmp"
    rm -rf "$tmp"
    cp -R "$main_root/.pi/$dir" "$tmp"
    rm -rf "$wt/.pi/$dir"
    mv "$tmp" "$wt/.pi/$dir"
  done
fi
