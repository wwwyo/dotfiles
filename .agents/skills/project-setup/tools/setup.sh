#!/usr/bin/env bash
# project-setup の決定的な手順をまとめる。ヒアリング・文書生成・commit 対象の判断は agent が持つ。
# init 以外は対象 repo の root を cwd にして呼ぶ。結果は stdout に 1 行の JSON で返す。
set -euo pipefail

usage() {
  cat <<'JSON'
{"usage":"setup.sh <command> [args]","commands":{
"init":{"args":"<repo|owner/repo>","behavior":"ghq create (git init 込み) し CLAUDE.md と最小 .gitignore を置く。既存の dir・file は変更しない","stdout":{"path":"string","owner":"string","repo":"string","created":"bool"}},
"tools":{"args":"<tool[@prefix]>...","behavior":"mise use --pin --before 7d で exact pin する"},
"telemetry":{"args":"","behavior":"Claude/Codex/pi の Langfuse opt-in と orca.yaml の setup script を置く。orca.yaml が既にあれば書かず orca_yaml=skipped を返す"},
"license":{"args":"<key> [--holder <name>]","behavior":"gh api licenses/<key> から LICENSE を生成し [year]/[fullname] 系の placeholder を埋める。holder 既定は gh の name","stdout":{"placeholders_remaining":"string[]"}},
"publish":{"args":"--visibility public|private [--owner <owner>]","behavior":"commit 済みの HEAD で gh repo create --push し、delete-branch-on-merge と gh secure を設定する。commit は呼び出し側が行う"}}}
JSON
}

die() { printf '{"error":%s}\n' "$(jq -Rn --arg m "$1" '$m')" >&2; exit "${2:-1}"; }

dotfiles="$HOME/src/github.com/wwwyo/dotfiles"
sync_script="$dotfiles/.agents/skills/project-setup/tools/sync-local-worktree-files.sh"

cmd_init() {
  [ $# -eq 1 ] || die "init takes <repo|owner/repo>" 2
  case "$1" in
    */*/*|/*|*..*|*[[:space:]]*) die "invalid repo: $1" 2 ;;
    */*) owner="${1%%/*}" repo="${1#*/}" ;;
    *) owner=wwwyo repo="$1" ;;
  esac
  path="$(ghq root)/github.com/$owner/$repo"
  created=false
  if [ ! -d "$path" ]; then
    ghq create "github.com/$owner/$repo" >/dev/null
    created=true
  fi
  [ -d "$path/.git" ] || git -C "$path" init -q
  # CLAUDE.md は AGENTS.md を読まない agent への転送 1 行だけを持つ
  [ -e "$path/CLAUDE.md" ] || printf 'read @AGENTS.md\n' >"$path/CLAUDE.md"
  [ -e "$path/.gitignore" ] || printf '%s\n' node_modules/ .DS_Store .env .env.local '*.log' >"$path/.gitignore"
  jq -cn --arg path "$path" --arg owner "$owner" --arg repo "$repo" --argjson created "$created" \
    '{path:$path, owner:$owner, repo:$repo, created:$created}'
}

cmd_tools() {
  [ $# -ge 1 ] || die "tools takes <tool[@prefix]>..." 2
  mise use --pin --before 7d "$@" >&2
  jq -cn --args '{pinned:$ARGS.positional}' "$@"
}

cmd_telemetry() {
  [ $# -eq 0 ] || die "telemetry takes no args" 2
  mkdir -p .claude .codex
  # 収集は個人設定なので gitignore される local file に書く
  [ -e .claude/settings.local.json ] || jq -n '{enabledPlugins:{"langfuse-observability@langfuse-observability":true}}' >.claude/settings.local.json
  printf '{"enabled": true}\n' >.codex/langfuse.json
  pi install -l --approve "git:github.com/wwwyo/pi-observability-plugin@v0.2.0" >&2
  orca_yaml=skipped
  if [ ! -e orca.yaml ]; then
    cat >orca.yaml <<YAML
scripts:
  setup: '[ ! -x "\$HOME/src/github.com/wwwyo/dotfiles/.agents/skills/project-setup/tools/sync-local-worktree-files.sh" ] || "\$HOME/src/github.com/wwwyo/dotfiles/.agents/skills/project-setup/tools/sync-local-worktree-files.sh"'
YAML
    orca_yaml=written
  fi
  jq -cn --arg orca_yaml "$orca_yaml" --arg sync "$sync_script" '{orca_yaml:$orca_yaml, sync_script:$sync}'
}

cmd_license() {
  [ $# -ge 1 ] || die "license takes <key> [--holder <name>]" 2
  key="$1"; shift
  holder=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --holder) holder="${2:?}"; shift 2 ;;
      *) die "unknown arg: $1" 2 ;;
    esac
  done
  [ -n "$holder" ] || holder="$(gh api user --jq '.name // .login')"
  year="$(date +%Y)"
  # GPL 系の <https://fsf.org/> 等の角括弧 URL は対象外にするため、placeholder を名指しで置換する
  gh api "licenses/$key" --jq .body |
    YEAR="$year" HOLDER="$holder" perl -pe '
      s/\[(year|yyyy)\]|<year>/$ENV{YEAR}/g;
      s/\[(fullname|name of copyright owner)\]|<name of author>|<copyright holders>/$ENV{HOLDER}/g;
    ' >LICENSE
  remaining="$(grep -oE '\[[a-z ]+\]|<(year|name of author|copyright holders)>' LICENSE | sort -u | jq -R . | jq -cs . || true)"
  jq -cn --arg key "$key" --arg holder "$holder" --argjson remaining "${remaining:-[]}" \
    '{license:$key, holder:$holder, placeholders_remaining:$remaining}'
}

cmd_publish() {
  visibility="" owner=wwwyo
  while [ $# -gt 0 ]; do
    case "$1" in
      --visibility) visibility="${2:-}"; shift 2 ;;
      --owner) owner="${2:?}"; shift 2 ;;
      *) die "unknown arg: $1" 2 ;;
    esac
  done
  case "$visibility" in public|private) ;; *) die "--visibility must be public or private" 2 ;; esac
  git rev-parse --verify -q HEAD >/dev/null || die "no commit yet: commit the setup files first"
  # 既存 repo の cwd で誤って呼ばれたときに別名の repo を作らない
  [ -z "$(git remote)" ] || die "remote already configured: publish is only for a new repo"
  repo="$owner/$(basename "$(git rev-parse --show-toplevel)")"
  gh repo create "$repo" "--$visibility" --source . --push >&2
  gh repo edit "$repo" --delete-branch-on-merge >&2
  if [ "$visibility" = public ]; then
    mise exec -- gh secure --repo "$repo" --yes vulnerability-reporting secret-scanning dependabot code-scanning >&2
  else
    mise exec -- gh secure --repo "$repo" --yes dependabot >&2
  fi
  jq -cn --arg repo "$repo" --arg visibility "$visibility" '{repo:$repo, visibility:$visibility}'
}

case "${1-}" in
  init|tools|telemetry|license|publish) c="$1"; shift; "cmd_$c" "$@" ;;
  --help|-h|help) usage ;;
  *) usage >&2; exit 2 ;;
esac
