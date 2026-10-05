#!/usr/bin/env bash
# home/dot_config/git/bin/ssh-sign（gpg.ssh.program wrapper）の分岐検証。
# launchctl / ssh-add / ssh-keygen を PATH 先頭の fake に置き換え、
# wrapper が ssh-keygen に渡す SSH_AUTH_SOCK と透過性を観測する。
#
# What を固定する:
# - SSH_AUTH_SOCK 未設定 / socket 不在 / agent 到達不可(ssh-add -l rc=2) →
#   launchctl の socket で復帰
# - 有効な agent（rc 0 or 1）が既にある → 上書きしない
# - launchctl が無い（非macOS）→ 素通し
# - 引数・stdin・exit status が ssh-keygen のものに一致
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
wrapper="$repo_dir/home/dot_config/git/bin/ssh-sign"
fail() { echo "FAIL: $*" >&2; exit 1; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
fakebin="$tmp/bin"
mkdir -p "$fakebin"

# socket file は -S test に実体が要るので AF_UNIX で bind して作る
make_sock() {
  python3 -c 'import socket,sys; s=socket.socket(socket.AF_UNIX); s.bind(sys.argv[1]); s.close()' "$1"
}

# fake ssh-keygen: 見えた環境・引数・stdin・終了 status を記録する。
# wrapper が渡す PATH は fakebin のみ（外部コマンドが無い）ので cat は絶対 path
cat_bin="$(command -v cat)"
cat > "$fakebin/ssh-keygen" <<EOF
#!/bin/sh
{
  echo "SOCK=\${SSH_AUTH_SOCK-<unset>}"
  echo "ARGS=\$*"
} >> "\$OUT"
"$cat_bin" > "\$OUT.stdin"
exit "\${FAKE_KEYGEN_RC:-0}"
EOF

# fake ssh-add: `-l` の exit code を socket ごとに注入する。
# rc2=agent 到達不可は OpenSSH の規約。DEAD_SOCK に向いた呼び出しだけ 2 を返し、
# それ以外は FAKE_SSH_ADD_RC（既定 0 = identity あり）
cat > "$fakebin/ssh-add" <<'EOF'
#!/bin/sh
[ -n "${DEAD_SOCK:-}" ] && [ "${SSH_AUTH_SOCK:-}" = "$DEAD_SOCK" ] && exit 2
exit "${FAKE_SSH_ADD_RC:-0}"
EOF

# fake launchctl: getenv SSH_AUTH_SOCK だけ応える
cat > "$fakebin/launchctl" <<'EOF'
#!/bin/sh
if [ "${1:-}" = "getenv" ] && [ "${2:-}" = "SSH_AUTH_SOCK" ]; then
  printf '%s\n' "${FAKE_SOCK:-}"
  exit 0
fi
exit 1
EOF
chmod +x "$fakebin"/*

live_sock="$tmp/live.sock"
recovered_sock="$tmp/recovered.sock"
make_sock "$live_sock"
make_sock "$recovered_sock"

run_wrapper() {
  # stdin に固定データ、環境は引数で注入
  local path="$1"; shift
  env -i PATH="$path" OUT="$tmp/out" \
    SSH_SIGN_SSH_ADD="$fakebin/ssh-add" SSH_SIGN_LAUNCHCTL="${LAUNCHCTL_FAKE:-$fakebin/launchctl}" \
    "$@" /bin/sh -c 'printf "payload" | "$0" -Y sign -f key' "$wrapper"
}

assert_sock() {
  grep -q "^SOCK=$1$" "$tmp/out" || { cat "$tmp/out"; fail "expected SOCK=$1"; }
}

# --- 1. SSH_AUTH_SOCK 未設定 → launchctl の socket で復帰 ---
rm -f "$tmp/out"*
run_wrapper "$fakebin" FAKE_SOCK="$recovered_sock" FAKE_SSH_ADD_RC=0
assert_sock "$recovered_sock"
grep -q '^ARGS=-Y sign -f key$' "$tmp/out" || fail "args not forwarded"
[ "$(cat "$tmp/out.stdin")" = "payload" ] || fail "stdin not forwarded"

# --- 2. socket path が存在しない → 復帰 ---
rm -f "$tmp/out"*
run_wrapper "$fakebin" SSH_AUTH_SOCK="$tmp/no-such.sock" FAKE_SOCK="$recovered_sock" FAKE_SSH_ADD_RC=0
assert_sock "$recovered_sock"

# --- 3. socket はあるが agent 到達不可（ssh-add -l rc=2）→ 復帰 ---
rm -f "$tmp/out"*
run_wrapper "$fakebin" SSH_AUTH_SOCK="$live_sock" DEAD_SOCK="$live_sock" FAKE_SOCK="$recovered_sock"
assert_sock "$recovered_sock"

# --- 3b. launchd が返す socket が dead → export せず ssh-keygen へ委ねる ---
rm -f "$tmp/out"*
run_wrapper "$fakebin" FAKE_SOCK="$recovered_sock" DEAD_SOCK="$recovered_sock"
assert_sock "<unset>"

# --- 4. 有効な agent（rc=0）→ 上書きしない ---
rm -f "$tmp/out"*
run_wrapper "$fakebin" SSH_AUTH_SOCK="$live_sock" FAKE_SOCK="$recovered_sock" FAKE_SSH_ADD_RC=0
assert_sock "$live_sock"

# --- 4b. agent 生存だが identity 無し（rc=1）→ 上書きしない ---
rm -f "$tmp/out"*
run_wrapper "$fakebin" SSH_AUTH_SOCK="$live_sock" FAKE_SOCK="$recovered_sock" FAKE_SSH_ADD_RC=1
assert_sock "$live_sock"

# --- 5. launchctl 不在（非macOS 相当）→ 素通し ---
rm -f "$tmp/out"*
mkdir -p "$tmp/nolaunch"
ln -s "$fakebin/ssh-keygen" "$tmp/nolaunch/ssh-keygen"
LAUNCHCTL_FAKE=/nonexistent run_wrapper "$tmp/nolaunch" SSH_AUTH_SOCK="$live_sock"
assert_sock "$live_sock"

# --- 6. exit status 透過 ---
rm -f "$tmp/out"*
set +e
env -i PATH="$fakebin" OUT="$tmp/out" SSH_SIGN_SSH_ADD="$fakebin/ssh-add" SSH_SIGN_LAUNCHCTL="$fakebin/launchctl" \
  FAKE_SOCK="$recovered_sock" FAKE_SSH_ADD_RC=0 FAKE_KEYGEN_RC=7 \
  /bin/sh -c 'printf "payload" | "$0"' "$wrapper"
rc=$?
set -e
[ "$rc" = "7" ] || fail "exit status not forwarded (got $rc)"

echo "OK: ssh-sign wrapper branches"
