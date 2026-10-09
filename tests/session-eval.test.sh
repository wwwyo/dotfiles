#!/usr/bin/env bash
# session_eval.py の非 API 部分の検証（lock のライフサイクル・slug 解決・io 正規化）。
# Langfuse に触れる経路は実 API のみが本物の挙動を持つので対象外。
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SE="$repo_dir/.agents/scheduled-tasks/session-eval/tools/session_eval.py"
TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

# --- lock: acquire → busy → release ---
# HOME を差し替えると mise shim 経由の python3 が real config を untrusted
# 扱いするので、元の config path を明示して shim を通す
export MISE_TRUSTED_CONFIG_PATHS="$HOME/.config/mise/config.toml:$HOME/.config/mise/conf.d:$repo_dir/mise.toml"
export REAL_HOME="$HOME"
export HOME="$TEST_ROOT/home"
mkdir -p "$HOME"
out=$(python3 "$SE" lock acquire)
printf '%s' "$out" | grep -q '"acquired": true' || fail "first acquire failed: $out"
out=$(python3 "$SE" lock acquire)
printf '%s' "$out" | grep -q '"acquired": false' || fail "second acquire should be busy: $out"
out=$(python3 "$SE" lock release)
printf '%s' "$out" | grep -q '"released": true' || fail "release failed: $out"
out=$(python3 "$SE" lock status)
printf '%s' "$out" | grep -q '"locked": false' || fail "status after release: $out"

# stale lock は回収される（ttl=0 で即 stale 化）
python3 "$SE" lock acquire >/dev/null
out=$(python3 "$SE" lock acquire --ttl-seconds 0)
printf '%s' "$out" | grep -q '"acquired": true' || fail "stale lock was not recovered: $out"
python3 "$SE" lock release >/dev/null

# 並走 acquire は winner が1つだけ
for i in 1 2 3 4 5; do python3 "$SE" lock acquire > "$TEST_ROOT/lock-$i.json" & done
wait
wins=$(grep -l '"acquired": true' "$TEST_ROOT"/lock-*.json | wc -l | tr -d ' ')
[ "$wins" = "1" ] || fail "parallel acquire winners=$wins (want 1)"
python3 "$SE" lock release >/dev/null

# stale lock の回収権競争でも winner は1つだけ。
# info.json の ts を過去に書き換えて stale 化し、回収後の fresh lock は
# age < ttl で守られる条件（=現実の起きうる競合）にする
python3 "$SE" lock acquire >/dev/null
python3 - <<'EOF'
import json, pathlib
p = pathlib.Path.home() / ".local/state/session-eval/batch.lockdir/info.json"
d = json.loads(p.read_text())
d["ts"] -= 300
p.write_text(json.dumps(d))
EOF
for i in 1 2 3 4 5; do python3 "$SE" lock acquire --ttl-seconds 120 > "$TEST_ROOT/steal-$i.json" & done
wait
wins=$(grep -l '"acquired": true' "$TEST_ROOT"/steal-*.json | wc -l | tr -d ' ')
[ "$wins" = "1" ] || fail "parallel stale-steal winners=$wins (want 1)"
python3 "$SE" lock release >/dev/null

# --- _resolve_slug / _io_text / resolve_workdir ---
# expanduser("~") は差し替え後の HOME を見るので、実 FS を見る検証は REAL_HOME を使う
python3 - "$SE" "$REAL_HOME" <<'EOF'
import importlib.util, os, sys
spec = importlib.util.spec_from_file_location("se", sys.argv[1])
se = importlib.util.module_from_spec(spec)
spec.loader.exec_module(se)
real_home = sys.argv[2]

dotfiles = os.path.join(real_home, "src/github.com/wwwyo/dotfiles")
if os.path.isdir(dotfiles):
    slug = "--Users-" + os.path.basename(real_home) + \
           "-src-github.com-wwwyo-dotfiles--"
    got = se._resolve_slug(slug)
    assert got == dotfiles, f"resolve_slug: {got} != {dotfiles}"
    # transcript file の親 dir から cwd を引く経路（pi/claude exporter 形式）
    md = {"transcript_path":
          os.path.join(real_home, ".pi/agent/sessions", slug, "x.jsonl")}
    assert se.resolve_workdir(md) == dotfiles, se.resolve_workdir(md)

# io 正規化: devin/pi 形式 (JSON string) / codex 形式 (plain) / dict / None
assert se._io_text('{"role":"user","content":"hello"}') == "hello"
assert se._io_text("plain codex input") == "plain codex input"
assert se._io_text({"role": "user", "content": "d"}) == "d"
assert se._io_text(None) == ""

# session_id の文字種制限（shell 挿入対策）
assert se.SESSION_ID_RE.match("01a0d738-cd64-7008-b87f-2ad11257b284")
assert se.SESSION_ID_RE.match("candy-lifeboat")
assert not se.SESSION_ID_RE.match("x;rm -rf /")
assert not se.SESSION_ID_RE.match("x$(touch /tmp/pwn)")

# resolve_repo: emit 済み > transcript_path > orca workspaces 規約 >
# canonical checkout。HOME は harness 側で $TEST_ROOT/home に差し替え済み
import json, pathlib, shutil, time
fake = pathlib.Path(os.environ["HOME"])
canon = fake / "src/github.com/wwwyo/dotfiles"
canon.mkdir(parents=True)
# emit 済み cwd/repo_root（実在）は一切の推測を経ずに返る。推測経路が
# 同じ答えを出せる値を避け、orca 規約とは別系統の dir を repo_root にする
other = fake / "elsewhere/repo"
other.mkdir(parents=True)
gone_wd = str(fake / "orca/workspaces/dotfiles/deleted-wt")
assert se.resolve_repo({"cwd": gone_wd, "repo_root": str(other)}) == \
    (gone_wd, str(other))
# emit 済み repo_root が消えていれば推測側へ落ちる（stale 値を通さない）
gone_rr = str(fake / "src/github.com/wwwyo/vanished")
wd, rr = se.resolve_repo({"cwd": gone_wd, "repo_root": gone_rr})
assert (wd, rr) == (gone_wd, str(canon)), (wd, rr)
# emit 済みの無い歴史 trace: 削除済み orca worktree の transcript_path から
# <repo> セグメントを取り canonical が残っていれば採用する
assert se.resolve_repo({"transcript_path": gone_wd}) == (gone_wd, str(canon))
# 生存 orca linked worktree: --show-toplevel は worktree 自身を返すが
# git-common-dir が canonical を正確に答える。canonical が ~/src 規約の
# 外にある場合（--repo path:）でも拾えることを実 worktree で pin する
import subprocess
main_repo = fake / "elsewhere/mainrepo"
subprocess.run(["git", "init", "-q", str(main_repo)], check=True)
subprocess.run(["git", "-C", str(main_repo), "-c", "user.email=t@t",
                "-c", "user.name=t", "commit", "-qm", "init",
                "--allow-empty"], check=True)
live = fake / "orca/workspaces/mainrepo/wt"
subprocess.run(["git", "-C", str(main_repo), "worktree", "add", "-q",
                str(live)], check=True)
wd, rr = se.resolve_repo({"cwd": str(live)})
# git は symlink を解決して返す（macOS /var → /private/var）ので resolve する
assert (wd, rr) == (str(live), str(main_repo.resolve())), (wd, rr)
# emit 済み repo_root が生存 worktree を指す異常値でも git が矯正する
_, rr = se.resolve_repo({"cwd": str(live), "repo_root": str(live)})
assert rr == str(main_repo.resolve()), rr
# 規約 dir があっても live dir には git が先に答える（順序を pin:
# 規約が先だと誤った同名 dir が採用される）
wrong = fake / "src/github.com/wwwyo/mainrepo"
wrong.mkdir(parents=True)
assert se.resolve_repo({"cwd": str(live)})[1] == str(main_repo.resolve())
# orca 規約の外にある live worktree でも git は canonical を答える
# （_git_common_root を orca パスに gate する実装に戻すとここで fail）
wt_out = fake / "outside/wt-out"
subprocess.run(["git", "-C", str(main_repo), "worktree", "add", "-q",
                str(wt_out)], check=True)
assert se.resolve_repo({"cwd": str(wt_out)}) == \
    (str(wt_out), str(main_repo.resolve()))
# workspaces 配下の standalone repo は規約名を貼らず自身を返す
alone = fake / "orca/workspaces/aloof/wt2"
subprocess.run(["git", "init", "-q", str(alone)], check=True)
assert se.resolve_repo({"cwd": str(alone)})[1] == str(alone.resolve())
# bare repo は git-common-dir の親が root でないので規約推測にも落ちない
bare = fake / "orca/workspaces/br/x.git"
subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
assert se.resolve_repo({"cwd": str(bare)})[1] is None
# canonical が無ければ発明しない
shutil.rmtree(canon)
assert se.resolve_repo({"transcript_path": gone_wd}) == (gone_wd, None)
# 規約に合わない path は repo を取らない
assert se.resolve_repo({"transcript_path": str(fake / "tmp/gone")})[1] is None
assert se.resolve_repo({}) == (None, None)

# _recover_owned: 世代身元は (dir inode, info.json ts) の組。それが stale
# 判定時と同じで、かつ marker/owner の nonce が自分のものの場合だけ削除を
# 許可する（rmdir→mkdir は同じ親 dir で inode を再利用するので inode 一致は
# 所有の証明にならない — 所有は owner file の nonce で見る）
ld = pathlib.Path(os.environ["HOME"]) / ".local/state/session-eval/batch.lockdir"
shutil.rmtree(ld, ignore_errors=True)
ld.mkdir(parents=True)
info_ts = time.time() - 300
(ld / "info.json").write_text(json.dumps({"ts": info_ts}))
dir_ino = ld.stat().st_ino
mk = ld / "recovering"
mk.mkdir()
(mk / "owner").write_text("nonce-a")
assert se._recover_owned(dir_ino, "nonce-a", info_ts)       # 正常: 同世代+自nonce
# info.json ts が違えば dir inode が同じでも別世代（inode 再利用対策）
assert not se._recover_owned(dir_ino, "nonce-a", info_ts + 999)
# dir 差し替わりでは自分の marker を stray として掃除される
assert not se._recover_owned(dir_ino + 10**9, "nonce-a", info_ts) and not mk.exists()
mk.mkdir(); (mk / "owner").write_text("nonce-b")
assert not se._recover_owned(dir_ino, "nonce-a", info_ts)   # 他人の marker
assert (mk / "owner").read_text() == "nonce-b"               # 他人のは消さない
# dir 差し替え + 自分の marker が新 dir に迷い込んだケース → 掃除して False。
# rmtree→mkdir は inode を再利用しうるので info.json 不在 (=ts None) でも
# 別世代と判定できることを兼ねて検証する
shutil.rmtree(ld); ld.mkdir()
mk.mkdir(); (mk / "owner").write_text("nonce-c")
assert not se._recover_owned(dir_ino, "nonce-c", info_ts)
assert not mk.exists(), "迷い込んだ marker が掃除されていない"

# skip_marker_kind: sentinel→"self"、synthetic marker→"synthetic"、
# 通常→None、API 失敗→fail-open の None (wwwyo/me の day_sessions.py が
# この語彙の consumer — 変えると向こうの sentinel 表示が壊れる)
real_paged = se.paged
def fake_paged(path, params):
    sid = params["sessionId"]
    if sid == "boom":
        raise se.ApiError("429 storm")
    inp = {"self-sid": f"x {se.SENTINEL} y",
           "syn-sid": "[Synthetic fixture] qa",
           "mid-quote": "前段で [Synthetic fixture] を引用した本文"}.get(
               sid, "real work")
    yield {"sessionId": sid, "input": inp}
se.paged = fake_paged
assert se.skip_marker_kind("self-sid") == "self"
assert se.skip_marker_kind("syn-sid") == "synthetic"
assert se.skip_marker_kind("real-sid") is None
# 本文中の引用は誤判定しない（先頭 marker だけが対象）
assert se.skip_marker_kind("mid-quote") is None
# lookup 失敗は None に倒す（除外しない）
assert se.skip_marker_kind("boom") is None
se.paged = real_paged

# _request: 429 の retry。urlopen/sleep を stub して試行回数と wait を pin
import email.message, io, urllib.error
def http_err(code, ra=None):
    m = email.message.Message()
    if ra is not None:
        m["Retry-After"] = ra
    return urllib.error.HTTPError("https://x.test/y", code, "e", m, None)
opened = {"n": 0}
sleeps = []
real_urlopen = se.urllib.request.urlopen
real_sleep = se.time.sleep
try:
    # Retry-After 指定の 429 は指定秒を尊重して成功まで retry する
    se.time.sleep = sleeps.append
    def flaky(url, **kw):
        opened["n"] += 1
        if opened["n"] <= 3:
            raise http_err(429, ra="2")
        return io.StringIO('{"ok": true}')
    se.urllib.request.urlopen = flaky
    assert se.api_get("/y", {}) == {"ok": True}
    assert opened["n"] == 4 and sleeps == [2.0, 2.0, 2.0]
    # Retry-After 無しの持続 429 は floor つき backoff で最後まで retry
    opened["n"] = 0; sleeps.clear()
    def always429(url, **kw):
        opened["n"] += 1
        raise http_err(429)
    se.urllib.request.urlopen = always429
    try:
        se.api_get("/y", {})
        raise AssertionError("429 storm should raise ApiError")
    except se.ApiError:
        pass
    assert opened["n"] == 6
    assert sleeps == [4.0, 8.0, 16.0, 30.0, 30.0]
    # POST の輸送層エラーは再送しない（score 二重付与防止）
    opened["n"] = 0; sleeps.clear()
    def conn_reset(url, **kw):
        opened["n"] += 1
        raise OSError("connection reset")
    se.urllib.request.urlopen = conn_reset
    try:
        se.api_post("/y", {})
        raise AssertionError("POST transport error should raise ApiError")
    except se.ApiError:
        pass
    assert opened["n"] == 1 and sleeps == []
finally:
    se.urllib.request.urlopen = real_urlopen
    se.time.sleep = real_sleep
print("ok")
EOF

echo "OK: session_eval lock/slug/io"

# Compact observations must retain evaluator signals through the public API path.
python3 "$repo_dir/.agents/scheduled-tasks/session-eval/tools/test_turn_summary.py"
