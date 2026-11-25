#!/usr/bin/env bash
# check_failed_runs.py の集計規則の検証。
#   - turn の最後が error/aborted のときだけ「失敗 run」に数える（retry で復帰した
#     turn・toolUse で続く turn は失敗ではない）
#   - 同じ errorMessage は 1 行にまとめ、期間と cwd を添える
#   - 窓の外（mtime が古い）session は読まない
#   - 窓は失敗 turn の時刻で判定する（mtime が新しくても窓外の失敗は出さない）
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOL="$repo_dir/.agents/scheduled-tasks/tools/check_failed_runs.py"
TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
run() {
  local out rc=0
  if out=$(python3 "$TOOL" "$@" 2>"$TEST_ROOT/cmd.err"); then rc=0; else rc=$?; fi
  [ "$rc" -eq 0 ] || fail "check_failed_runs $* exited $rc: $(cat "$TEST_ROOT/cmd.err")"
  printf '%s' "$out"
}

# --- fixture: 2 session、うち 3 turn が失敗、1 turn は retry で復帰 ---
SESS="$TEST_ROOT/sessions"
mkdir -p "$SESS/--Users-someone--" "$SESS/--Users-someone-orca--"

# fixture の時刻は固定値ではなく now からの相対で作る — 窓判定が実時刻基準なので、
# 固定日付にすると実行日によって期待件数が変わる
python3 - "$SESS" <<'PY'
import json, sys, os
from datetime import datetime, timedelta, timezone

root = sys.argv[1]
NOW = datetime.now(timezone.utc)

def ts(**kw):
    d = NOW - timedelta(**kw)
    return d.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

def write(path, sid, cwd, messages):
    lines = [{"type": "session", "version": 3, "id": sid, "timestamp": ts(days=5), "cwd": cwd}]
    for role, stamp, extra in messages:
        msg = {"role": role, "content": "x", "timestamp": stamp}
        msg.update(extra)
        lines.append({"type": "message", "timestamp": stamp, "message": msg})
    with open(path, "w") as fh:
        for line in lines:
            fh.write(json.dumps(line) + "\n")

me = os.path.join(root, "--Users-someone--", "a.jsonl")
write(me, "sess-a", "/Users/someone/me", [
    ("user", ts(days=3, minutes=1), {}),
    ("assistant", ts(days=3), {"stopReason": "toolUse"}),
    ("assistant", ts(days=3, seconds=-9), {"stopReason": "stop"}),
    # 402 で落ちて retry で復帰した turn → 失敗ではない
    ("user", ts(days=2, minutes=1), {}),
    ("assistant", ts(days=2, seconds=59),
     {"stopReason": "error", "errorMessage": "429: rate limit"}),
    ("assistant", ts(days=2), {"stopReason": "stop"}),
    # 最後まで error の turn → 失敗
    ("user", ts(days=1, minutes=1), {}),
    ("assistant", ts(days=1, seconds=59),
     {"stopReason": "error", "errorMessage": "402: Insufficient balance."}),
])

orca = os.path.join(root, "--Users-someone-orca--", "b.jsonl")
write(orca, "sess-b", "/Users/someone/orca/workspaces/me/run", [
    ("user", ts(hours=7), {}),
    ("assistant", ts(hours=6, minutes=59),
     {"stopReason": "error", "errorMessage": "402: Insufficient balance."}),
    ("user", ts(hours=3), {}),
    ("assistant", ts(hours=2, minutes=58), {"stopReason": "aborted"}),
])

# mtime が新しいのに失敗が窓外の session（30 日前に落ちて、直近に成功 turn が積まれた型）
mixed = os.path.join(root, "--Users-someone--", "mixed.jsonl")
write(mixed, "sess-mixed", "/Users/someone/mixed", [
    ("user", ts(days=30, minutes=1), {}),
    ("assistant", ts(days=30, seconds=59),
     {"stopReason": "error", "errorMessage": "402: Insufficient balance."}),
    ("user", ts(hours=1), {}),
    ("assistant", ts(minutes=59), {"stopReason": "stop"}),
])
PY

# 窓の外の session（mtime を 30 日前にする）— 失敗 turn を持っていても数えない
OLD="$SESS/--Users-someone--/old.jsonl"
cp "$SESS/--Users-someone--/a.jsonl" "$OLD"
touch -t 202601010000 "$OLD"

out=$(run --sessions-dir "$SESS" --days 7)
printf '%s' "$out" | grep -q '^failed runs: 3 turns in 2 sessions (3 pi sessions scanned' \
  || fail "件数が想定と違う: $out"
# mtime が新しくても、窓外の失敗 turn は出さない
printf '%s' "$out" | grep -q 'sess-mixed' && fail "窓外の失敗 turn を数えている: $out"
# retry で復帰した turn の 429 は出ない
printf '%s' "$out" | grep -q '429' && fail "復帰した turn を失敗に数えている: $out"
# 同じ errorMessage は 1 行にまとまり、2 cwd を添える
printf '%s' "$out" | grep -q '2x \[error\] .*me (1), .*orca/workspaces/me/run (1)' \
  || fail "errorMessage の集約が想定と違う: $out"
printf '%s' "$out" | grep -q '1x \[aborted\]' || fail "aborted turn が出ていない: $out"

# 失敗が無ければ none
EMPTY="$TEST_ROOT/empty"
mkdir -p "$EMPTY/--x--"
python3 - "$EMPTY/--x--/ok.jsonl" <<'PY'
import json, sys
lines = [
    {"type": "session", "id": "s", "cwd": "/tmp"},
    {"type": "message", "timestamp": "2026-11-16T00:00:00.000Z",
     "message": {"role": "user", "content": "x"}},
    {"type": "message", "timestamp": "2026-11-16T00:00:01.000Z",
     "message": {"role": "assistant", "stopReason": "stop"}},
]
open(sys.argv[1], "w").write("\n".join(json.dumps(l) for l in lines) + "\n")
PY
out=$(run --sessions-dir "$EMPTY" --days 7)
printf '%s' "$out" | grep -q '^failed runs: none' || fail "none の表示が想定と違う: $out"


# --- errorMessage の切り詰め: group key は全文、表示だけ MSG_LIMIT ---
LONG="$TEST_ROOT/longmsg"
mkdir -p "$LONG/--x--"
python3 - "$LONG/--x--/long.jsonl" <<'PY'
import json, sys
from datetime import datetime, timedelta, timezone
NOW = datetime.now(timezone.utc)

def ts(**kw):
    d = NOW - timedelta(**kw)
    return d.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

head = "provider returned an error: " + "a" * 160
lines = [{"type": "session", "id": "s-long", "cwd": "/tmp"}]
for tail in (" cause-one", " cause-two"):
    lines += [
        {"type": "message", "timestamp": ts(hours=2),
         "message": {"role": "user", "content": "x"}},
        {"type": "message", "timestamp": ts(hours=2, minutes=59),
         "message": {"role": "assistant", "stopReason": "error",
                     "errorMessage": head + tail}},
    ]
open(sys.argv[1], "w").write("\n".join(json.dumps(l) for l in lines) + "\n")
PY
json_long=$(run --sessions-dir "$LONG" --days 7 --json)
printf '%s' "$json_long" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["failed_turns"] == 2, d["failed_turns"]
groups = d["groups"]
assert len(groups) == 2, groups
assert all(len(g["error"]) > 140 for g in groups), groups
' || fail "長い errorMessage の集約が想定と違う: $json_long"
text_long=$(run --sessions-dir "$LONG" --days 7)
line=$(printf '%s' "$text_long" | grep -m1 '^    provider returned')
[ "${#line}" -le 150 ] || fail "表示が切り詰められていない: $line"

# JSON 出力
json_out=$(run --sessions-dir "$SESS" --days 7 --json)
printf '%s' "$json_out" | python3 -c '
import json, sys
d = json.load(sys.stdin)
assert d["failed_turns"] == 3, d["failed_turns"]
groups = d["groups"]
assert len(groups) == 2, groups
assert groups[0]["error"].startswith("402"), groups[0]
assert groups[0]["turns"] == 2 and len(groups[0]["sessions"]) == 2, groups[0]
' || fail "JSON 出力が想定と違う: $json_out"

echo "OK: check_failed_runs"
