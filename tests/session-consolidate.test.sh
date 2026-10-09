#!/usr/bin/env bash
# session_consolidate.py の非 API 部分の検証（記録 comment の選択・
# 学習候補 抽出・lock の独立性）。Langfuse に触れる経路は実 API のみが
# 本物の挙動を持つので対象外。
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SC="$repo_dir/.agents/scheduled-tasks/session-consolidate/tools/session_consolidate.py"
TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

# HOME を差し替えると mise shim 経由の python3 が real config を untrusted
# 扱いするので、元の config path を明示して shim を通す
export MISE_TRUSTED_CONFIG_PATHS="$HOME/.config/mise/config.toml:$HOME/.config/mise/conf.d:$repo_dir/mise.toml"
export HOME="$TEST_ROOT/home"
mkdir -p "$HOME"

# --- lock: session-eval とは別 state dir で独立に acquire できる ---
out=$(python3 "$SC" lock acquire)
printf '%s' "$out" | grep -q '"acquired": true' || fail "acquire failed: $out"
printf '%s' "$out" | grep -q 'session-consolidate' || fail "wrong lock dir: $out"
out=$(python3 "$SC" lock acquire)
printf '%s' "$out" | grep -q '"acquired": false' || fail "second acquire should be busy: $out"
python3 "$SC" lock release >/dev/null
# eval 側の lock dir を作っていないこと（共有すると片方が常に busy になる）
[ ! -e "$HOME/.local/state/session-eval" ] || fail "eval state dir was created"

python3 - "$SC" <<'EOF'
import importlib.util, sys
spec = importlib.util.spec_from_file_location("sc", sys.argv[1])
sc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sc)

# --- pick_record_comment: marker 付き最新を採用、append-only の追記に追従 ---
rec = lambda s: {"content": s, "createdAt": "2026-09-20T00:00:00Z"}
assert sc.pick_record_comment([]) is None
assert sc.pick_record_comment([rec("ただの雑談 comment")]) is None
old = rec("<!-- session-eval evaluated_at=1 -->\n## 事実\n- **学習候補**: 古い")
new = rec("<!-- session-eval evaluated_at=2 -->\n## 事実\n- **学習候補**: 新しい")
assert sc.pick_record_comment([new, old]) is new   # createdAt 順は fetch が並べる
assert sc.pick_record_comment([rec("評価以外"), new]) is new

# --- extract_learning: 学習候補 節の本文を取る。見出し無しは None ---
content = ("<!-- session-eval evaluated_at=x -->\n## 事実\n- x\n\n"
           "## 解釈（evaluator 所見）\n- **学び・発見**: foo\n"
           "- **学習候補**: skill X に手順を追記\n  複数行も含む\n")
assert sc.extract_learning(content) == "skill X に手順を追記\n  複数行も含む"
assert sc.extract_learning(content.replace("学習候補", "学習こ候補")) is None
assert sc.extract_learning("- **学習候補**: 特になし") == "特になし"
assert sc.extract_learning(None) is None

# --- sentinel: eval とは別 literal。se.SENTINEL は差し替え済みで一致する
# (差し替えを忘れると se._sentinel_hit が eval sentinel を見て自己
#  session を取りこぼす)
assert sc.se.SENTINEL == sc.SENTINEL
assert sc.SENTINEL != "session-eval-batch:9f3a2c7e"
assert sc.se._sentinel_hit({"input": "x session-consolidate-batch:5d1e8b4a y"})
assert not sc.se._sentinel_hit({"input": "session-eval-batch:9f3a2c7e"})
assert not sc.se._sentinel_hit({"input": "plain"})

# sentinel は automation.toml / consolidator-prompt.md にも同一 literal が
# 要る (消えると自己 consolidation ループが復活)。加えて両方に eval
# sentinel の併記が要る — 無いとこの batch の session が日次 eval に
# 評価されて翌翌週の対象に戻る
import pathlib
# stdin script の __file__ は "<stdin>" なので module の方を使う
task_dir = pathlib.Path(sc.__file__).resolve().parent.parent
for f in (task_dir / "automation.toml",
          task_dir / "references" / "consolidator-prompt.md"):
    text = f.read_text()
    assert sc.SENTINEL in text, f"{f.name} missing consolidate sentinel"
    assert "session-eval-batch:9f3a2c7e" in text, \
        f"{f.name} missing eval sentinel"

# --- _score_epoch / _needs_consolidation ---
assert sc._score_epoch({"value": 12.5}) == 12.5
assert sc._score_epoch(None) is None
assert sc._score_epoch({"value": "abc"}) is None
# predicate の核心: co >= ev は処理済み。`>=`/`>` の転倒は処理済み全件の
# 再列挙になる
assert not sc._needs_consolidation(10.0, 10.0)   # co == ev: 済み
assert not sc._needs_consolidation(10.0, 11.0)   # co > ev: 済み
assert sc._needs_consolidation(10.0, 9.0)        # co < ev: 再評価分を拾う
assert sc._needs_consolidation(10.0, None)       # co 無し: 対象
assert not sc._needs_consolidation(None, None)   # 未評価: 対象外

# --- se 再利用: lock path が差し替え済み・API helper は同じ実体 ---
import pathlib
assert "session-consolidate" in str(sc.se.LOCK_DIR)
assert sc.paged is sc.se.paged and sc.ensure_env is sc.se.ensure_env
print("ok")
EOF

echo "OK: session_consolidate lock/record/learning"
