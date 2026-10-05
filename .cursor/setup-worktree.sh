#!/bin/bash
set -e

# worktreeのセットアップ時にファイルをコピーするスクリプト
# $ROOT_WORKTREE_PATH はプライマリ作業ツリーのパス

ROOT_PATH="${ROOT_WORKTREE_PATH:-$PWD}"

# .agent ファイルをコピー（ルート直下）
if [ -f "$ROOT_PATH/.agent" ]; then
  cp "$ROOT_PATH/.agent" "./.agent"
  echo "Copied: .agent"
fi

# **/.agent ファイルをコピー（サブディレクトリ内）
find "$ROOT_PATH" -type f -name ".agent" ! -path "$ROOT_PATH/.agent" 2>/dev/null | while read -r src_file; do
  rel_path="${src_file#$ROOT_PATH/}"
  dest_file="./$rel_path"
  dest_parent=$(dirname "$dest_file")
  mkdir -p "$dest_parent"
  cp "$src_file" "$dest_file"
  echo "Copied: $rel_path"
done

# .env* ファイルをコピー（ルート直下）
find "$ROOT_PATH" -maxdepth 1 -type f -name ".env*" 2>/dev/null | while read -r src_file; do
  filename=$(basename "$src_file")
  cp "$src_file" "./$filename"
  echo "Copied: $filename"
done

# **/.env* ファイルをコピー（サブディレクトリ内）
find "$ROOT_PATH" -type f -name ".env*" ! -path "$ROOT_PATH/.env*" 2>/dev/null | while read -r src_file; do
  rel_path="${src_file#$ROOT_PATH/}"
  dest_file="./$rel_path"
  dest_parent=$(dirname "$dest_file")
  mkdir -p "$dest_parent"
  cp "$src_file" "$dest_file"
  echo "Copied: $rel_path"
done

# node_modules ディレクトリをコピー（.cache を除外）
if [ -d "$ROOT_PATH/node_modules" ]; then
  if command -v rsync >/dev/null 2>&1; then
    rsync -av --exclude=".cache" "$ROOT_PATH/node_modules" ./
  else
    # rsyncがない場合の代替手段
    cp -r "$ROOT_PATH/node_modules" ./ 2>/dev/null || true
    # .cache ディレクトリを削除
    find ./node_modules -type d -name ".cache" -exec rm -rf {} + 2>/dev/null || true
  fi
  echo "Copied directory: node_modules (excluding .cache)"
fi

echo "Worktree setup completed!"
