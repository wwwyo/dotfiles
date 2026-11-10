#!/bin/sh

# Codex は local plugin を ~/.codex/plugins/cache へコピーして読み、config.toml の
# [plugins."core@wwwyo"] 宣言だけでは cache に入らない。apply のたびに wwwyo/skills の
# core・local を入れ直し、cache を canonical checkout（~/src/github.com/wwwyo/skills）に揃える。
# skill を編集した直後に Codex へ反映したいときは同じ `codex plugin add` を手で叩く。

set -eu

skills="$HOME/src/github.com/wwwyo/skills"
command -v codex >/dev/null 2>&1 || { echo "skip (no codex)"; exit 0; }
[ -f "$skills/.agents/plugins/marketplace.json" ] || { echo "skip (no checkout): $skills"; exit 0; }

for plugin in core local; do
  if codex plugin add "$plugin@wwwyo" >/dev/null; then
    echo "codex plugin: $plugin@wwwyo"
  else
    echo "warn: codex plugin add $plugin@wwwyo failed" >&2
  fi
done
