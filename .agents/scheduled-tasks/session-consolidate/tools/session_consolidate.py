#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""session_consolidate — 評価済み session の記録 comment から 学習候補 を
repo/wiki 単位で束ねる consolidation batch の tooling。

定時 batch (orca automation) と consolidator subagent が使う。
全 subcommand は JSON を stdout に出す。

  targets      未 consolidate の評価済み session を repo_root で束ねて列挙
               (親 agent が対象を決める唯一の経路)
  record       1 session の最新記録 comment を全文で返す (drill down 用)
  score        session に score を書き戻す (POST /api/public/scores)
  lock         mkdir lock で batch を single-writer にする

Langfuse API・lock 機構・repo 識別は session_eval.py (同 repo の正本) を
import して再利用する — session_eval 側の動作は変えない。STATE_DIR /
LOCK_DIR だけはこの process 内で consolidate 用の path に差し替える
(lock 関数が module global を参照する実装なので、差し替えは import 直後の
1 箇所で行う)。

対象 predicate (ADR 0003 の「consolidated score が無い」からの確定版):
  - 最新 evaluated_until score がある (評価完了 marker)
  - 最新記録 comment (evaluator が書いた `<!-- session-eval` 形式) に
    学習候補 節がある — 値が「特になし」でも対象に含める。
    含めないと consolidator が見る前に wedge する
  - 最新 consolidated score が無い、またはその値 < 最新 evaluated_until
    の値 — 「score が無い」だけだと session が再評価されて新しい学習候補が
    付いても二度と拾えない。値比較にすると再評価分は自然に再対象になる

書き戻すのは consolidated score (NUMERIC) だけ。値は「束ねた時点の
evaluated_until の値」— 壁時計ではなく coverage にすると上記の再対象
predicate と整合する。comment は append-only で consolidate 側は書かない
(処理の記録は score の comment 列に PR URL 等で残せる)。
"""

import argparse
import importlib.util
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SE_PATH = (Path(__file__).resolve().parent.parent.parent /
            "session-eval" / "tools" / "session_eval.py")
_spec = importlib.util.spec_from_file_location("session_eval", _SE_PATH)
se = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(se)

# lock は consolidate 専用の state dir にする (session-eval と lock を
# 共有すると片方の稼働中に他方が常に busy になる)
se.STATE_DIR = Path.home() / ".local" / "state" / "session-consolidate"
se.LOCK_DIR = se.STATE_DIR / "batch.lockdir"

emit = se.emit
fail = se.fail
ApiError = se.ApiError
_iso = se._iso
_ts = se._ts
paged = se.paged
api_post = se.api_post
ensure_env = se.ensure_env

# sentinel は 3 箇所に同一 literal — consolidator-prompt.md と
# session-consolidate/automation.toml にも書かれている。変えるときは
# 3 箇所同時に変えないと自己 consolidation ループが復活する。
# eval の sentinel とは別 literal — eval batch の session は eval 側の
# sentinel で既に弾かれている。consolidate の prompt には eval の
# sentinel も併記してあるので、この batch の session は eval にも
# 載らない (=記録 comment を持たず consolidate 対象にもならない)
SENTINEL = "session-consolidate-batch:5d1e8b4a"
# se の sentinel 判定関数は module global の SENTINEL を読む。
# STATE_DIR/LOCK_DIR と同じく差し替えれば eval 側の _sentinel_hit /
# has_sentinel をそのまま再利用できる (この process で eval sentinel を
# 引く必要はない — eval session は記録 comment を持たず対象外なので)
se.SENTINEL = SENTINEL
SCORE_EVALUATED = "evaluated_until"   # session-eval が書く watermark/完了 marker
SCORE_CONSOLIDATED = "consolidated"   # この batch が書く処理済み marker
DEFAULT_LOOKBACK_HOURS = 36.0         # 閾値ゲートで保留された pending
                                      # session はこの窓を超えると静かに落ちる
SESSION_WORKERS = 8                   # comment/sentinel/repo 解決の並列度
LEARNING_HEADING = "学習候補"
RECORD_MARKER = "<!-- session-eval"


def has_own_sentinel(sid):
    """session の root observation の user input に consolidate sentinel が
    あればこの batch 自身の session。失敗時は None (=不明) を返し、
    呼び出し側が self とは別 counter に数える — True に倒すと API 障害で
    全件が self skip になり、障害が「対象 0 件の静かな週」と見分け付か
    ない。eval の has_sentinel は transcript 側で再判定するので
    fail-open でよかったが、こちらに二段目のチェックは無い。"""
    try:
        for o in paged("/api/public/v2/observations",
                       {"sessionId": sid, "fields": "basic,io",
                        "filter": se.ROOT_FILTER}):
            if o.get("sessionId") == sid and se._sentinel_hit(o):
                return True
    except Exception:
        return None
    return False


# ---------- 記録 comment ----------

def fetch_comments(sid):
    """session の comment を新しい順に返す。comments API は page 番号 paging。"""
    out = []
    for page in range(1, se.MAX_PAGES + 1):
        d = se.api_get("/api/public/comments",
                       {"objectType": "SESSION", "objectId": sid,
                        "page": page, "limit": 50})
        rows = d.get("data") or []
        out.extend(rows)
        meta = d.get("meta") or {}
        if len(out) >= (meta.get("totalItems") or len(out)) or not rows:
            break
    out.sort(key=lambda c: c.get("createdAt") or "", reverse=True)
    return out


def pick_record_comment(comments):
    """最新の evaluator 記録 comment を返す (無ければ None)。
    evaluator は `<!-- session-eval evaluated_at=... -->` を冒頭に書く。
    comment は append-only なので複数評価では最新を採用する。"""
    for c in comments:
        if RECORD_MARKER in (c.get("content") or ""):
            return c
    return None


def extract_learning(content):
    """記録 comment から `学習候補` 節の本文を取る。見つからなければ None。
    節は `- **学習候補**: <内容>` の形で解釈の末尾にある。"""
    m = re.search(r"- \*\*%s\*\*:\s*(.*?)(?=\n- \*\*|\n##|\Z)"
                  % re.escape(LEARNING_HEADING), content or "", re.S)
    if not m:
        return None
    # 見出し以降を全部取ると、後続に項目・追記が増える形式変更で無関係な
    # 本文まで consolidator に渡る。次の箇条書き項目・見出しで打ち切る
    return m.group(1).strip()


# ---------- score 集約 ----------

def _latest_scores(sids, name):
    """sid -> 最新の同名 score row。v3 は新しい順なので先勝ち。
    chunk 全 sid を1行でも観測した時点で打ち切る (session_eval.targets と
    同じ考え方 — 未観測 sid に未読行が残りうる限り読み続ける)。"""
    latest = {}
    for i in range(0, len(sids), se.SCORES_SID_CHUNK):
        chunk = sids[i:i + se.SCORES_SID_CHUNK]
        unseen = set(chunk)
        for sc in paged("/api/public/v3/scores",
                        {"fields": "subject",
                         "sessionId": ",".join(chunk),
                         "name": name,
                         "limit": se.SCORES_PAGE_LIMIT}):
            subj = sc.get("subject") or {}
            if subj.get("kind") != "session":
                continue
            sid_k = subj.get("id")
            if not sid_k:
                continue
            unseen.discard(sid_k)
            latest.setdefault(sid_k, sc)
            if not unseen:
                break
    return latest


def _score_epoch(row):
    try:
        return float(row.get("value")) if row else None
    except (TypeError, ValueError):
        return None


def _needs_consolidation(ev, co):
    """対象 predicate の核心: evaluated_until (ev) があり、consolidated
    (co) が無いか ev 未満なら対象。co >= ev は処理済み — `>=`/`>` を
    間違えると処理済み session を全件再列挙する。"""
    return ev is not None and (co is None or co < ev)


# ---------- subcommands ----------

def cmd_targets(a):
    ensure_env()
    try:
        return _cmd_targets(a)
    except ApiError as e:
        fail(str(e))


def _cmd_targets(a):
    now = datetime.now(timezone.utc)
    if a.since:
        try:
            since = _ts(a.since)
        except ValueError:
            fail(f"invalid --since: {a.since}")
    else:
        since = now - timedelta(hours=a.lookback_hours)

    # sessionId で client 側集約 (session_eval.targets と同じ経路・同じ理由:
    # root 限定だと sessionId を持たない agent がいる。repo 識別 hint も
    # ここで拾う)
    sessions = {}
    unsafe_sids = set()
    for o in paged("/api/public/v2/observations",
                   {"fields": "basic,metadata",
                    "expandMetadata": se.EXPAND_METADATA,
                    "fromStartTime": _iso(since), "toStartTime": _iso(now)}):
        sid = o.get("sessionId")
        if not sid:
            continue
        if not se.SESSION_ID_RE.match(sid):
            unsafe_sids.add(sid)
            continue
        s = sessions.setdefault(sid, {"max_start": "", "sources": set(),
                                      "hints": {}})
        if (o.get("startTime") or "") > s["max_start"]:
            s["max_start"] = o["startTime"]
        se._merge_hints(s, o.get("metadata") or {})

    # 窓内に obs が無い session の補完。exporter は turn の startTime を
    # user message 時刻へ backdate するので、長期 session の新 turn は
    # 窓外の startTime を持ち observation 集約では拾えない。再評価された
    # 形跡 (= evaluated_until score の ingest 時刻が窓内) だけでも拾う。
    # score の timestamp はサーバ ingest 時刻 — 値の coverage ではない。
    # 補完経路の失敗で本流 (observation 集約) まで落とさないよう、
    # ApiError は補完 0 件として扱う — ただし unattended run の唯一の
    # 故障 signal を残すため emit に backfill_incomplete を載せる
    backfill_incomplete = False
    try:
        for sc in paged("/api/public/v3/scores",
                        {"fields": "subject",
                         "name": SCORE_EVALUATED,
                         "fromTimestamp": _iso(since),
                         "limit": se.SCORES_PAGE_LIMIT}):
            # server 側 filter を信用しない (filter 無視の不具合への防御)
            if sc.get("name") != SCORE_EVALUATED:
                continue
            subj = sc.get("subject") or {}
            if subj.get("kind") != "session":
                continue
            sid = subj.get("id")
            if not sid or sid in sessions:
                continue
            if not se.SESSION_ID_RE.match(sid):
                unsafe_sids.add(sid)
                continue
            # obs 無しなので hints/sources/max_start は空 — repo_root は
            # 解決不能で fallback 側に回る
            sessions[sid] = {"max_start": "", "sources": set(), "hints": {}}
    except ApiError:
        backfill_incomplete = True

    sids = list(sessions)
    eval_wm = _latest_scores(sids, SCORE_EVALUATED)
    # consolidated は evaluated を持つ sid にしか意味を持たないので絞る —
    # 未評価 sid 分の scores API 走査は無駄
    ev_sids = [s for s in sids
               if _score_epoch(eval_wm.get(s)) is not None]
    cons_wm = _latest_scores(ev_sids, SCORE_CONSOLIDATED)

    candidates = []
    n_no_eval = n_done = 0
    for sid in sids:
        ev = _score_epoch(eval_wm.get(sid))
        if ev is None:
            n_no_eval += 1
            continue
        co = _score_epoch(cons_wm.get(sid))
        if not _needs_consolidation(ev, co):
            n_done += 1
            continue
        candidates.append((sid, ev))

    # 記録 comment / sentinel / repo 解決は session ごとの API round trip と
    # stat/subprocess があるので並列にする
    def _resolve(item):
        sid, ev = item
        own = has_own_sentinel(sid)
        if own is None:
            # 判定不能は self とは別に数える — 全件 self になると API 障害が
            # 「対象 0 件の静かな週」と見分け付かない
            return {"sentinel_error": True}
        if own:
            return {"self": True}
        rec = pick_record_comment(fetch_comments(sid))
        if rec is None:
            # 記録 comment 自体が無い — evaluator が comment だけ書けず
            # 死亡した残骸の可能性がある (目視の価値がある)
            return {"no_record": True}
        learning = extract_learning(rec.get("content"))
        if learning is None:
            # 記録はあるが 学習候補 節が無い — session_eval の 4800 字
            # tail 切り落としで節ごと消えた記録等。原因が違うので別 counter
            return {"no_learning": True}
        wd, rr = se.resolve_repo(sessions[sid]["hints"])
        return {"session_id": sid, "evaluated_until": ev,
                "comment_id": rec.get("id"),
                "last_activity": sessions[sid]["max_start"],
                "sources": sorted(sessions[sid]["sources"]),
                "learning": learning,
                "workdir": wd, "repo_root": rr}

    groups = {}
    n_self = n_no_record = n_no_learning = n_sentinel_err = 0
    with ThreadPoolExecutor(max_workers=SESSION_WORKERS) as ex:
        for r in ex.map(_resolve, candidates):
            if r.get("sentinel_error"):
                n_sentinel_err += 1
                continue
            if r.get("self"):
                n_self += 1
                continue
            if r.get("no_record"):
                n_no_record += 1
                continue
            if r.get("no_learning"):
                n_no_learning += 1
                continue
            root = r.pop("repo_root")
            r.pop("workdir")
            groups.setdefault(root or "", []).append(r)

    out_groups = [{"repo_root": root or None,
                   "sessions": sorted(v, key=lambda s: s["last_activity"])}
                  for root, v in sorted(groups.items())]
    emit({"ok": True,
          "window": {"from": _iso(since), "to": _iso(now)},
          "groups": out_groups,
          "skipped": {"no_eval": n_no_eval,
                      "already_consolidated": n_done,
                      "no_record": n_no_record,
                      "no_learning": n_no_learning,
                      "self": n_self,
                      "sentinel_error": n_sentinel_err,
                      "backfill_incomplete": backfill_incomplete,
                      "unsafe_sid": len(unsafe_sids),
                      "unsafe_sids": sorted(unsafe_sids)}})


def cmd_record(a):
    se._check_sid(a.session_id)
    ensure_env()
    try:
        rec = pick_record_comment(fetch_comments(a.session_id))
    except ApiError as e:
        fail(str(e))
    if not rec:
        fail(f"no record comment for session {a.session_id}")
    emit({"ok": True, "session_id": a.session_id,
          "comment_id": rec.get("id"),
          "created_at": rec.get("createdAt"),
          "content": rec.get("content")})


def cmd_score(a):
    se._check_sid(a.session_id)
    ensure_env()
    try:
        body = {"sessionId": a.session_id, "name": a.name,
                "dataType": "NUMERIC", "value": float(a.value)}
    except ValueError:
        fail(f"invalid --value: {a.value}")
    if a.comment:
        body["comment"] = a.comment
    try:
        resp = api_post("/api/public/scores", body)
    except ApiError as e:
        fail(str(e))
    emit({"ok": True, "id": resp.get("id"), "name": a.name,
          "session_id": a.session_id})


def main():
    p = argparse.ArgumentParser(prog="session_consolidate",
                                description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("targets",
                       help="未 consolidate の評価済み session を repo 別に列挙")
    t.add_argument("--since", help="ISO8601。指定時は --lookback-hours より優先")
    t.add_argument("--lookback-hours", type=float,
                   default=DEFAULT_LOOKBACK_HOURS)
    t.set_defaults(fn=cmd_targets)

    r = sub.add_parser("record", help="1 session の最新記録 comment を返す")
    r.add_argument("session_id")
    r.set_defaults(fn=cmd_record)

    s = sub.add_parser("score", help="session に score を書き戻す")
    s.add_argument("--session-id", required=True)
    s.add_argument("--name", default=SCORE_CONSOLIDATED)
    s.add_argument("--value", required=True, help="NUMERIC の数値")
    s.add_argument("--comment")
    s.set_defaults(fn=cmd_score)

    lk = sub.add_parser("lock", help="batch の single-writer lock")
    lk.add_argument("action", choices=["acquire", "release", "status"])
    lk.add_argument("--ttl-seconds", type=int, default=se.DEFAULT_LOCK_TTL)
    lk.set_defaults(fn=se.cmd_lock)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
