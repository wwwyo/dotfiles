# Vim mode
bindkey -v
bindkey -M viins 'jj' vi-cmd-mode

# zsh-abbr: bindkey -v が main keymap を viins に切り替えた際に
# Space の bind が外れるため再登録する。Enter は viins デフォルトの
# accept-line をプラグインがラップ済みなので追加 bind 不要
bindkey -M viins ' ' abbr-expand-and-insert

# Register zle widgets
zle -N fzf-src

# Repository selector
stty -ixon  # disable flow control
bindkey '^s' fzf-src

# Navigation
bindkey '^f' forward-char
bindkey '^b' backward-char

