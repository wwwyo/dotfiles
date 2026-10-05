# Completion settings
zstyle ":completion:*:commands" rehash 1

# Git info for prompt
autoload -Uz vcs_info
setopt prompt_subst
zstyle ':vcs_info:git:*' check-for-changes true
zstyle ':vcs_info:git:*' stagedstr "%F{magenta}!"
zstyle ':vcs_info:git:*' unstagedstr "%F{yellow}+"
zstyle ':vcs_info:*' formats "%F{cyan}%c%u[%b]%f"
zstyle ':vcs_info:*' actionformats '[%b|%a]'
precmd () { vcs_info }

# Prompt
PROMPT='
[%B%F{green}%~%f%b]%F{cyan}${vcs_info_msg_0_}%f
%F{yellow}$%f '
