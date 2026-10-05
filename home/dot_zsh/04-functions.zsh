# fzf: ghq repository selector
function fzf-src () {
    local selected_dir=$(ghq list -p | fzf --query "$LBUFFER")
    if [ -n "$selected_dir" ]; then
        BUFFER="cd ${selected_dir}"
        zle accept-line
    fi
    zle clear-screen
}

# fzf: file finder
function fzf-find-file() {
    if git rev-parse 2> /dev/null; then
        source_files=$(git ls-files)
    else
        source_files=$(find . -type f)
    fi
    selected_files=$(echo $source_files | fzf --prompt "[find file] ")

    BUFFER="${BUFFER}$(echo $selected_files | tr '\n' ' ')"
    CURSOR=$#BUFFER
    zle redisplay
}

# Override find command: run fzf-find-file when called without arguments
unalias find 2>/dev/null
function find() {
    if [[ $# -eq 0 ]]; then
        fzf-find-file
    else
        command find "$@"
    fi
}
