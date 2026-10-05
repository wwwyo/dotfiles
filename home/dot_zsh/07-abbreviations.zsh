# zsh-abbr abbreviations
# -S: session abbreviation (defined here, not persisted to user store)
# -g: global abbreviation (expands anywhere on the line)

# Tools
# -f: force registration even when a command with the same name exists on PATH
abbr -S -f vim='nvim' >/dev/null
abbr -S -f cat='bat' >/dev/null
abbr -S -f ls='eza' >/dev/null
abbr -S -f tree='eza --tree' >/dev/null
abbr -S gw='gwq' >/dev/null
abbr -S -f python='python3' >/dev/null

# Coding agents
abbr -S yolo='claude --dangerously-skip-permissions' >/dev/null
abbr -S 'codex-yolo'='codex --dangerously-bypass-approvals-and-sandbox' >/dev/null

# Git shortcuts (top-level)
abbr -S gs='git status --short --branch' >/dev/null
abbr -S gci="git commit -v" >/dev/null
abbr -S gstash='git stash -uk' >/dev/null

if [[ "$OSTYPE" == darwin* ]]; then
  # デフォルトアプリの再適用（アプリに奪い返されたとき用）
  abbr -S 'duti-apply'='duti ~/.config/duti/defaults.duti' >/dev/null
  abbr -S -g copy='pbcopy' >/dev/null
fi

# Global abbreviations
abbr -S -g null='>/dev/null 2>&1' >/dev/null
