#!/bin/sh

# Orca が配る skill（orca-cli・orchestration・orca-computer-use）は wwwyo/skills に置かず、
# Orca 自身に ~/.agents/skills へ copy させ、~/.claude/skills へ link させる。
# Codex・pi は ~/.agents/skills を直接読む。Orca 本体の更新時には、Orca が手つかずの copy を
# 自動で置き換える。ここでは新しい machine や、消えたときに入れ直すだけ。
# 入っていて手つかずなら "No change"。手で変えた copy は Orca が skip を報告するので、警告にとどめる。

set -eu

command -v orca >/dev/null 2>&1 || { echo "skip (no orca)"; exit 0; }

if ! orca skills install --skill orca-cli --skill orchestration --skill orca-computer-use --agent claude; then
  echo "warn: orca skills install failed" >&2
fi
