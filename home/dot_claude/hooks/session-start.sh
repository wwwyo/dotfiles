#!/usr/bin/env bash
# SessionStart hook: settings.json の env は $HOME を展開しないため、PATH はここで組む。
# CLAUDE_ENV_FILE は毎回の Bash tool 実行前に source される。plain な export だけ書く。
# > ではなく >>: 他の hook が先に書いた export を消さないため。重複行は無害。
[ -n "${CLAUDE_ENV_FILE:-}" ] || exit 0
printf 'export PATH=%q\n' "$HOME/.local/share/mise/shims:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" >> "$CLAUDE_ENV_FILE"
