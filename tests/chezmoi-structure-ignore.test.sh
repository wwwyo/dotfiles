#!/usr/bin/env bash
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
fixture_dir=$(mktemp -d)
trap 'rm -rf "$fixture_dir"' EXIT

mkdir -p "$fixture_dir/home" "$fixture_dir/tests" "$fixture_dir/.cloudflare"
cp "$repo_dir/tests/chezmoi-structure.test.sh" "$fixture_dir/tests/"
touch "$fixture_dir/home/run_after_20-link-repodirs.sh.tmpl"
printf '%s\n' '.cloudflare/' > "$fixture_dir/.gitignore"
printf '%s\n' 'cache' > "$fixture_dir/.cloudflare/cache.json"
git -C "$fixture_dir" init -q
git -C "$fixture_dir" add -- .gitignore home tests

bash "$fixture_dir/tests/chezmoi-structure.test.sh" >/dev/null

expect_missing_link() {
  local directory="$1" output
  if output=$(bash "$fixture_dir/tests/chezmoi-structure.test.sh" 2>&1); then
    echo "FAIL: $directory without a deploy link was accepted" >&2
    exit 1
  fi
  [[ "$output" == *"$directory は deploy 対象候補"* ]] || {
    echo "FAIL: unexpected error: $output" >&2
    exit 1
  }
}

# An ignore rule must not hide files already managed by Git.
git -C "$fixture_dir" add -f -- .cloudflare/cache.json
expect_missing_link .cloudflare
git -C "$fixture_dir" rm -q --cached -- .cloudflare/cache.json

# A new, non-ignored settings directory still needs a deploy decision.
mkdir "$fixture_dir/.settings"
touch "$fixture_dir/.settings/config"
expect_missing_link .settings

echo "OK: ignored caches are skipped; tracked and non-ignored settings are checked"
