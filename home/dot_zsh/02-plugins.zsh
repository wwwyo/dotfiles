# Zinit installer
if [[ ! -f $HOME/.local/share/zinit/zinit.git/zinit.zsh ]]; then
    print -P "%F{33} %F{220}Installing %F{33}ZDHARMA-CONTINUUM%F{220} Initiative Plugin Manager (%F{33}zdharma-continuum/zinit%F{220})…%f"
    command mkdir -p "$HOME/.local/share/zinit" && command chmod g-rwX "$HOME/.local/share/zinit"
    command git clone https://github.com/zdharma-continuum/zinit "$HOME/.local/share/zinit/zinit.git" && \
        print -P "%F{33} %F{34}Installation successful.%f%b" || \
        print -P "%F{160} The clone has failed.%f%b"
fi

source "$HOME/.local/share/zinit/zinit.git/zinit.zsh"
autoload -Uz _zinit
(( ${+_comps} )) && _comps[zinit]=_zinit

zinit light zdharma-continuum/fast-syntax-highlighting

# zsh-abbr (abbreviation expansion)
zinit light olets/zsh-abbr

# Homebrew (fpath を整えてから compinit する。`bun` 等の補完ファイルが
# 末尾で `command -v compinit` を見て独自にフル compinit を走らせるため、
# それより前に compinit を済ませておく必要がある)
for _brew_share in /opt/homebrew/share /home/linuxbrew/.linuxbrew/share; do
    if [[ -d $_brew_share ]]; then
        FPATH=$_brew_share/zsh-completions:$FPATH
        [[ -f $_brew_share/zsh-autosuggestions/zsh-autosuggestions.zsh ]] &&
            source $_brew_share/zsh-autosuggestions/zsh-autosuggestions.zsh
        break
    fi
done
unset _brew_share

autoload -Uz compinit
# 1日1回だけフル実行、それ以外はキャッシュから即起動
if [[ -n ${ZDOTDIR:-$HOME}/.zcompdump(#qN.mh+24) ]]; then
    compinit
else
    compinit -C
fi

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# Google Cloud SDK
if [ -f "$HOME/google-cloud-sdk/path.zsh.inc" ]; then
    . "$HOME/google-cloud-sdk/path.zsh.inc"
fi
if [ -f "$HOME/google-cloud-sdk/completion.zsh.inc" ]; then
    . "$HOME/google-cloud-sdk/completion.zsh.inc"
fi

# mise
(( $+commands[mise] )) && eval "$(mise activate zsh)"

# Cloudflare CLI
(( $+commands[cf] )) && source <(cf complete zsh)

# zoxide
(( $+commands[zoxide] )) && eval "$(zoxide init zsh)"
