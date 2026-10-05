# PATH
export PATH="$HOME/.local/bin:$PATH"
export PATH="$HOME/go/bin:$PATH"
export PATH="$HOME/development/flutter/bin:$PATH"
[[ -d /opt/homebrew/opt/mysql@8.0/bin ]] && export PATH="/opt/homebrew/opt/mysql@8.0/bin:$PATH"

# bun
export BUN_INSTALL="$HOME/.bun"
export PATH="$BUN_INSTALL/bin:$PATH"

# Antigravity
export PATH="$HOME/.antigravity/antigravity/bin:$PATH"

# mise
export PATH="$HOME/.local/share/mise/shims:$PATH"

# History
export HISTFILE="$HOME/.zsh_history"
export HISTSIZE=100000
export SAVEHIST=100000
setopt HIST_IGNORE_ALL_DUPS
setopt HIST_FIND_NO_DUPS
setopt SHARE_HISTORY
setopt APPEND_HISTORY

# fzf
export FZF_DEFAULT_OPTS='--reverse'

# Misc
ZLE_REMOVE_SUFFIX_CHARS=$''

# mise + age: 復号鍵(age secret key)を MISE_AGE_KEY へ渡す
# macOS は Keychain、それ以外は gitignore 済みの ~/.config/mise/age.txt から読む
# 生鍵は git に乗せず、暗号文のみ mise.toml (git追跡) に格納する
# mise は precmd で env を再評価するので、export 後の prompt で復号値が入る
if command -v security >/dev/null 2>&1; then
  _mise_age_key="$(security find-generic-password -a "$USER" -s mise-age-key -w 2>/dev/null)"
elif [[ -r "$HOME/.config/mise/age.txt" ]]; then
  _mise_age_key="$(<"$HOME/.config/mise/age.txt")"
fi
[[ -n "${_mise_age_key:-}" ]] && export MISE_AGE_KEY="$_mise_age_key"
unset _mise_age_key
