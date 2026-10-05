#!/bin/sh
# Devin Stop + SessionEnd hook。stdin の JSON payload から session_id を取り、
# その時点までの turn を Langfuse に export する本体を detached で起動する。
# Stop（turn 完了ごと）で逐次送り、SessionEnd は最終 flush — SessionEnd が
# 発火しない/閉じない session でも pi/codex plugin と同様にほぼリアルタイムで
# trace が見えるようにするため。export は turn_count+末尾 signature の
# checkpoint で増分のみ送る（langfuse-export.py 側）。
# hook は順次実行されるので本体を待つと turn 応答が遅れる。
# 常に exit 0（hook 失敗で devin の挙動を変えない）

input=$(cat)

command -v jq >/dev/null 2>&1 || exit 0

sid=$(printf '%s' "$input" | jq -r '.session_id // empty' 2>/dev/null)
[ -n "$sid" ] || exit 0

MISE=/opt/homebrew/bin/mise
[ -x "$MISE" ] || MISE=$(command -v mise) || exit 0

# GUI 起動の devin は shell 活性化を経ないため mise env が乗らない。
# DEVIN_PROJECT_DIR の mise.local.toml（repo-local opt-in）と global env
# （復号された key）をここで評価する。age 復号に要る MISE_AGE_KEY も
# GUI には無いので keychain から補う
if [ -z "$MISE_AGE_KEY" ]; then
  MISE_AGE_KEY=$(security find-generic-password -a "$USER" -s mise-age-key -w 2>/dev/null) \
    && export MISE_AGE_KEY
fi

cd "${DEVIN_PROJECT_DIR:-$PWD}" 2>/dev/null || exit 0
eval "$("$MISE" env -s bash 2>/dev/null)"

# opt-in は dependency 解決（uv run の SDK resolve）より先に判定する。
# 未 opt-in repo では uv/network を一切触らずに終わらせる
[ "$DEVIN_TRACE_TO_LANGFUSE" = "true" ] || exit 0

UV=$(command -v uv) || UV="$HOME/.local/share/mise/shims/uv"
[ -x "$UV" ] || exit 0

LOG_DIR="$HOME/.local/state/langfuse-export"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/hook.log"
# hook 自体の stderr を残す。無制限に育たないよう 1MB で rotate
if [ -f "$LOG" ] && [ "$(wc -c <"$LOG")" -gt 1048576 ]; then
  mv "$LOG" "$LOG.old"
fi

nohup "$UV" run --quiet --script \
  "$HOME/.config/devin/hooks/langfuse-export.py" devin "$sid" \
  >>"$LOG" 2>&1 &

exit 0
