#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# ///
"""session_eval — Langfuse session eval batch の tooling。

定時 batch (orca automation, 19:00 目安) と evaluator subagent が使う。
全 subcommand は JSON を stdout に出す。

  targets      未評価 session を列挙する (親 agent が対象を決める唯一の経路)
  transcript   1 session の judge 用 transcript を組み立てる
  score        session に score を書き戻す (POST /api/public/scores)
  comment      session に comment を書き戻す (POST /api/public/comments)
  lock         mkdir lock で batch を single-writer にする

Why urllib (langfuse SDK ではない): 必要なのは public REST の read/write
だけで、依存を持たない方が起動も速い。POST /api/public/scores は
ingestion 経路で存続している legacy endpoint (PRD で実測済み)。

書き戻すのは2つだけ:
  - 要約は comment オブジェクト (score value は機械分類の解釈を先回りして
    埋め込むので持たない — 事実と evaluator 所見の分離は comment 内でやる)
  - evaluated_until (NUMERIC, epoch) = 評価が覆った観測の上限
    (観測済み最新 obs の endTime or startTime)。壁時計の取得時刻では
    なく coverage で書く — fetch 後に ingest された turn も endTime が
    新しければ次回 run で再対象になる。score の timestamp はサーバ
    取り込み時刻で上書きされるためこの値でしか正確に記録できない。
    評価完了の marker を兼ねる — 最後に書く (comment だけ書けて途中死亡
    した session は wm が無いので次回 run でやり直される)

Why sentinel 判定が targets と transcript の 2 箇所: 列挙時に弾けば
evaluator の spawn 自体を省ける。transcript 側の再判定は、列挙と evaluator
起動の間に sentinel 付き trace が流れ込む race への保険。
"""

import argparse
import base64
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

# sentinel は 3 箇所に同一 literal がある — evaluator-prompt.md と
# session-eval/automation.toml の prompt にも書かれている。変えるときは
# 3 箇所同時に変えないと自己評価ループが復活する
SENTINEL = "session-eval-batch:9f3a2c7e"
# 合成 fixture session (telemetry QA 等) は評価・consolidate 対象から外す。
# sid prefix は API を呼ばずに弾け、root input の marker は sentinel と同じ
# 経路で拾う 2 段構え。除外対象は score/comment で追跡しない。
# この prefix は外部 consumer (wwwyo/me の day_sessions.py) も先判定に使う
SYNTHETIC_SESSION_PREFIX = "telemetry-qa-"
SYNTHETIC_MARKER = "[Synthetic"
SCORE_WATERMARK = "evaluated_until"  # 観測済み最新 obs の endTime or startTime の epoch (NUMERIC)。完了 marker を兼ねる
STATE_DIR = Path.home() / ".local" / "state" / "session-eval"
LOCK_DIR = STATE_DIR / "batch.lockdir"
DEFAULT_LOOKBACK_HOURS = 168.0   # 7d。定時 batch が数日止まっても拾い切れる下限
MAX_TRANSCRIPT_BYTES = 200_000   # 廃止した SessionEnd 要約 hook と同じ上限
DEFAULT_LOCK_TTL = 4 * 3600      # batch の最長想定 + 余裕。crash 時も翌日 run までに必ず回復する
API_PAGE_LIMIT = 1000            # v2 observations の上限 (v3 scores は 100 固定)
SCORES_PAGE_LIMIT = 100
SCORES_SID_CHUNK = 50            # scores API の sessionId 複数指定の 1 chunk 幅
MAX_COMMENT_CHARS = 4800         # comments API の content 上限は 5000。超過は
                                 # 400 で永久 wedge するので tool 側で切る
SENTINEL_WORKERS = 8             # sentinel/workdir 判定の並列度 (API + stat 連打)
RECOVER_STALL_S = 5              # mkdir→owner 書き込みの自己停止検知 (sec)。超えたら世代を疑い abort
RECOVER_MARKER_TTL_S = 60        # 回収 marker が残ったまま回収可能になるまでの秒数
MAX_PAGES = 20                   # ページング暴走の止血帯
SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._~:+-]{1,200}$")

ROOT_FILTER = json.dumps([{"type": "boolean", "column": "isRootObservation",
                           "operator": "=", "value": True}])
# v2 は metadata 値を 200 字で切ることがある。transcript_path/cwd 由来の
# repo 復元が黙って潰れないよう expand 指定しておく。expandMetadata は
# upstream では key 名を見ず非空なら全 key 展開のフラグとしてしか効かない
# — 空にすると repo 識別系の key がまとめて truncate されるので消さない
EXPAND_METADATA = "cwd,transcript_path,git_branch,telemetry_summary"


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def fail(msg, **kw):
    emit({"ok": False, "error": msg, **kw})
    sys.exit(1)


class ApiError(Exception):
    """API 層の失敗。raise して呼び出し側に委ねる (fail() しない —
    stdout の JSON 契約を壊すため)。cmd_* 境界で fail() に変換する。"""


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


# ---------- env ----------

def ensure_env():
    need = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
    if all(os.environ.get(k) for k in need):
        return
    # automation 経由の起動では shell 活性化を経ず mise env が乗らないことがある。
    # そのときは devin-langfuse plugin の langfuse-export.sh と同じ経路で自分で解決する。
    if sys.platform == "darwin" and not os.environ.get("MISE_AGE_KEY"):
        try:
            r = subprocess.run(
                ["security", "find-generic-password",
                 "-a", os.environ.get("USER", ""), "-s", "mise-age-key", "-w"],
                capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                os.environ["MISE_AGE_KEY"] = r.stdout.strip()
        except Exception:
            pass
    candidates = [shutil.which("mise")]
    if sys.platform == "darwin":
        candidates.append("/opt/homebrew/bin/mise")
    candidates.append(str(Path.home() / ".local" / "bin" / "mise"))
    mise = next((c for c in candidates if c and os.path.exists(c)), None)
    if not mise:
        fail("langfuse credentials missing and mise not found")
    try:
        # cwd=home で repo-local な mise.toml の LANGFUSE_* shadow を避ける
        # (wiki_route._get_typesafe_key と同じ経路)
        r = subprocess.run([mise, "env", "--json"], cwd=str(Path.home()),
                           capture_output=True, text=True, timeout=30)
    except Exception as e:
        fail(f"mise env failed: {e}")
    if r.returncode != 0:
        fail(f"mise env failed: {r.stderr.strip()[:300]}")
    # wiki_route.py と同じく --json 経路。export 行の regex パースは
    # shell escape・複数行値で壊れる
    for k, v in (json.loads(r.stdout or "{}")).items():
        # setdefault ではなく truthiness — 空文字で export 済みの
        # LANGFUSE_* は mise の実値で上書きする必要がある
        if not os.environ.get(k):
            os.environ[k] = v
    if not all(os.environ.get(k) for k in need):
        fail("LANGFUSE_PUBLIC_KEY/SECRET_KEY not available via env or mise")


# ---------- Langfuse REST ----------

def _auth():
    tok = (os.environ["LANGFUSE_PUBLIC_KEY"] + ":" +
           os.environ["LANGFUSE_SECRET_KEY"]).encode()
    return "Basic " + base64.b64encode(tok).decode()


def _base():
    return os.environ.get("LANGFUSE_BASE_URL") or "https://cloud.langfuse.com"


def _err_body(e):
    try:
        return e.read()[:300].decode("utf-8", "replace")
    except Exception:
        return ""


def _request(method, path, params=None, body=None):
    """429/5xx は retry。429 の Retry-After を尊重する (Langfuse API limits の案内)。
    POST は輸送層エラー (timeout/接続断) で再送しない — サーバ到達済みか判別不能で、
    再送すると score が二重に付く。GET は冪等なので何でも retry する。
    429 は rate-limit window が分単位なので 1,2,4 秒の再試行では window を
    跨げず全滅しうる — Retry-After 無しのときは 4s からの backoff で跨ぐ。"""
    url = _base() + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for i in range(6):
        try:
            req = urllib.request.Request(
                url, data=data, method=method,
                headers={"Authorization": _auth(),
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if not (e.code == 429 or e.code >= 500):
                raise ApiError(f"{method} {path} -> {e.code}: {_err_body(e)}")
            last = e
            if i == 5:
                break
            ra = (e.headers.get("Retry-After") or "")
            if ra.isdigit():
                wait = min(float(ra), 30.0)
            elif e.code == 429:
                wait = min(4.0 * (2 ** i), 30.0)
            else:
                wait = float(2 ** i)
            time.sleep(wait)
        except Exception as e:
            if method == "POST":
                raise ApiError(f"POST {path}: {e} (レスポンス不明のため再送しない)")
            last = e
            if i == 5:
                break
            time.sleep(2 ** i)
    raise ApiError(f"{method} {path} failed after retries: {last}")


def api_get(path, params):
    return _request("GET", path, params=params)


def api_post(path, body):
    return _request("POST", path, body=body)


def paged(path, params):
    """cursor ページング。上限到達・cursor 停滞は黙って打ち切ると session を
    取りこぼすので ApiError で fail-loud にする。"""
    params = dict(params)
    params.setdefault("limit", API_PAGE_LIMIT)
    prev = None
    for _ in range(MAX_PAGES):
        d = api_get(path, params)
        for o in d.get("data", []):
            yield o
        cur = (d.get("meta") or {}).get("cursor")
        if not cur:
            return
        if cur == prev:
            raise ApiError(f"GET {path}: cursor did not advance")
        prev = cur
        params["cursor"] = cur
    raise ApiError(f"GET {path}: exceeded MAX_PAGES={MAX_PAGES}")


# ---------- repo 識別 ----------

def _resolve_slug(slug):
    """`-` 連結 slug を実存 dir に写す (claude ~/.claude/projects、
    pi ~/.pi/agent/sessions の親 dir)。`-` は path 区切り・`.`・`_`・
    そのままの `-` のどれにも写りうるので、各階層で最長一致を試す。"""
    parts = [p for p in slug.split("-") if p]
    if not parts:
        return None
    path = "/"
    i = 0
    while i < len(parts):
        hit = None
        for j in range(len(parts), i, -1):
            for sep in ("-", ".", "_"):
                if os.path.isdir(os.path.join(path, sep.join(parts[i:j]))):
                    hit = (sep.join(parts[i:j]), j)
                    break
            if hit:
                break
        if not hit:
            return None
        path = os.path.join(path, hit[0])
        i = hit[1]
    return path


def resolve_workdir(md):
    """trace metadata → 起動 cwd の best-effort 復元。
    devin は transcript_path = working_directory、pi plugin は metadata.cwd、
    claude/pi exporter は transcript file の親 dir が slug 化された cwd。
    Codex は手掛かりを持たない → None (呼び出し側が fallback する)。"""
    cwd = md.get("cwd")
    if isinstance(cwd, str) and os.path.isdir(cwd):
        return cwd
    tp = md.get("transcript_path")
    if not isinstance(tp, str) or not tp:
        return None
    if os.path.isdir(tp):
        return tp
    parent = os.path.basename(os.path.dirname(tp))
    if parent.startswith("-"):
        return _resolve_slug(parent)
    return None


def repo_root(workdir):
    if not workdir:
        return None
    try:
        r = subprocess.run(["git", "-C", workdir, "rev-parse", "--show-toplevel"],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            return r.stdout.strip()
    except Exception:
        pass
    return None


def _git_common_root(workdir):
    """git-common-dir の親 = canonical repo root。linked worktree なら
    共有 .git の親（短命 worktree でない側）、standalone/main checkout
    なら workdir 自身。dir が消えている・repo でない → None。
    basename==".git" の guard は bare repo（自身が .git dir 相当）や
    submodule（<top>/.git/modules/<sub>）で親が root にならない形を
    弾くため。"""
    if not workdir or not os.path.isdir(workdir):
        return None
    try:
        r = subprocess.run(["git", "-C", workdir, "rev-parse",
                            "--path-format=absolute", "--git-common-dir"],
                           capture_output=True, text=True, timeout=3)
        if r.returncode == 0 and r.stdout.strip():
            common = r.stdout.strip()
            if os.path.basename(common) == ".git":
                return os.path.dirname(common)
    except Exception:
        pass
    return None


def _merge_hints(s, md):
    src = md.get("source")
    if not isinstance(src, str) or not src:
        # 環境によっては resourceAttributes がネストされるので両方見る
        ra = md.get("resourceAttributes.service.name") or \
            (md.get("resourceAttributes") or {}).get("service.name")
        src = ra if isinstance(ra, str) else None
    if src:
        s["sources"].add(src.split(":")[0])
    for k in ("cwd", "transcript_path", "git_branch", "repo_root",
              "repo_name"):
        v = md.get(k)
        if isinstance(v, str) and v and k not in s["hints"]:
            s["hints"][k] = v


def resolve_repo(md):
    """metadata → (workdir, repo_root)。

    emit 時に確定した cwd/repo_root があれば最優先 — worktree 削除後でも
    読める。cwd は「書かれた時点で真実」なので dir 実在を要求しない
    （resolve_workdir の isdir は曖昧な transcript_path の解釈判定用）。
    repo_root の優先順位: live wd の git-common-dir（canonical を権威と
    して答え、emit 済みが worktree を指す異常値も矯正）> emit 済み
    repo_root（実在のみ）> show-toplevel > 削除済み orca wd の
    ~/src 規約推測。短命 worktree dir を集約キーにしない。
    """
    cwd = md.get("cwd")
    wd = cwd if isinstance(cwd, str) and cwd else resolve_workdir(md)
    if wd is None:
        # emit 済み cwd/repo_root が無い歴史 trace の fallback。
        # orca worktree（<root>/orca/workspaces/<repo>/<slug>）は短命で
        # 掃除済みでも path が repo 名を保持する。claude 等の
        # transcript_path は ~/.claude/ 配下なのでこの pattern には合わない
        tp = md.get("transcript_path")
        if isinstance(tp, str) and "/orca/workspaces/" in tp:
            wd = tp
    rr = md.get("repo_root")
    # emit 済み repo_root は canonical checkout を指すので worktree と違い
    # 残っている前提 — 消えている値を consolidate の {REPO_ROOT} に流さない
    emitted = isinstance(rr, str) and rr and os.path.isdir(rr)
    # live wd は git-common-dir が canonical を権威として答える（orca か
    # どうかに依らない。emit 済みが worktree を指す異常値でも矯正される）
    canon = _git_common_root(wd)
    if canon:
        rr = canon
    elif not emitted:
        rr = repo_root(wd)
        if rr is None and wd:
            # dir が消えていて git が答えられない歴史 trace のみ規約で推定
            m = re.search(r"/orca/workspaces/([^/]+)/", wd)
            if m:
                cand = os.path.expanduser(
                    f"~/src/github.com/wwwyo/{m.group(1)}")
                if os.path.isdir(cand):
                    rr = cand
    return wd, rr


# ---------- sentinel ----------

def _io_marker_hit(o, needle):
    v = o.get("input")
    # str なら dumps 不要 — marker 文字列は JSON escape 対象の文字を含まない
    if not isinstance(v, str):
        v = json.dumps(v, ensure_ascii=False)
    return needle in v


def _io_prefix_hit(o, needle):
    """input 文字列の先頭に marker がある場合だけ True。
    fixture marker は root prompt の先頭に付ける約束なので、本文中の
    引用 ("[Synthetic example] のような..." 等) では合成 session と
    誤判定しない。"""
    v = o.get("input")
    return isinstance(v, str) and v.lstrip().startswith(needle)


def _sentinel_hit(o):
    return _io_marker_hit(o, SENTINEL)


def _synthetic_hit(o):
    return _io_prefix_hit(o, SYNTHETIC_MARKER)


def skip_marker_kind(sid):
    """session の root observation (=turn) の user input に sentinel があれば
    eval batch 自身の session ("self")、[Synthetic 系の fixture marker があれば
    合成 session ("synthetic")。どちらでもなければ None。
    失敗時は None (=含める) に倒す — transcript 側が再判定するので、
    ここでの取りこぼしは再評価で済む。

    外部 consumer: wwwyo/me の daily-end (day_sessions.py) が sentinel 表示に
    この戻り値を使う。語彙 ("self"/"synthetic"/None) を変えるときは
    そちらも追従させる。"""
    try:
        for o in paged("/api/public/v2/observations",
                       {"sessionId": sid, "fields": "basic,io",
                        "filter": ROOT_FILTER}):
            if o.get("sessionId") != sid:
                continue
            if _sentinel_hit(o):
                return "self"
            if _synthetic_hit(o):
                return "synthetic"
    except Exception:
        pass
    return None


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

    # sessionId で client 側集約。root 限定にはしない — root span が
    # sessionId を持たない agent (codex, pi) がいる
    sessions = {}
    unsafe_sids = set()
    for o in paged("/api/public/v2/observations",
                   {"fields": "basic,metadata", "expandMetadata": EXPAND_METADATA,
                    "fromStartTime": _iso(since), "toStartTime": _iso(now)}):
        sid = o.get("sessionId")
        if not sid:
            continue
        # 出力は親 agent が shell コマンド '{SESSION_ID}' に埋め込む。
        # ここで文字種を弾けば prompt 側のクォートが破られない
        if not SESSION_ID_RE.match(sid):
            unsafe_sids.add(sid)
            continue
        s = sessions.setdefault(sid, {"max_start": "", "max_end": "", "obs": 0,
                                      "sources": set(), "hints": {}})
        if (o.get("startTime") or "") > s["max_start"]:
            s["max_start"] = o["startTime"]
        # 「評価時点に存在しなかった obs」を拾い直すため endTime でも見る:
        # exporter は turn 完了時に start を user message 時刻へ backdate して
        # emit するので、start だけ見ると fetch 中に完了した turn が
        # watermark 以下に見えて二度と評価されない。endTime を持たない
        # agent は startTime で近似する (その場合の誤差は従来どおり)
        et = o.get("endTime") or o.get("startTime") or ""
        if et > s["max_end"]:
            s["max_end"] = et
        s["obs"] += 1
        _merge_hints(s, o.get("metadata") or {})

    # v3 は新しい順。対象 session 分だけを取れば全履歴スキャンが要らない
    # (sessionId はカンマ区切り複数指定可・実測済み)。fromTimestamp=since で
    # 更に絞る — 窓内に obs がある session が skip に必要とする score は
    # 必ず窓内にあり、窓より古い評価しか持たない session はどのみち
    # pending になるので無損失。
    # 打ち切りは「chunk 全 sid を1行でも観測済み」かつ「見えた sid の wm が
    # 全て解決済み」のときだけ — 未観測 sid に未読の score が残りうる限り
    # 読み続ける (score 無しの sid はそもそも行を返さない)
    last_wm = {}  # sid -> 最新 evaluated_until row (新しい順に来るので先勝ち)
    sids = list(sessions)
    for i in range(0, len(sids), SCORES_SID_CHUNK):
        chunk = sids[i:i + SCORES_SID_CHUNK]
        unseen = set(chunk)
        for sc in paged("/api/public/v3/scores",
                        {"fields": "subject",
                         "sessionId": ",".join(chunk),
                         "name": SCORE_WATERMARK,
                         "fromTimestamp": _iso(since),
                         "limit": SCORES_PAGE_LIMIT}):
            subj = sc.get("subject") or {}
            if subj.get("kind") != "session":
                continue
            sid_k = subj.get("id")
            if not sid_k:
                continue
            unseen.discard(sid_k)
            last_wm.setdefault(sid_k, sc)
            if not unseen:
                break

    # 評価済み = 最新 evaluated_until が存在し、その値 (評価が覆った観測の
    # 上限 epoch) が session の最新 completed obs (max endTime or startTime)
    # を覆っている。wm の score ts (サーバ ingest 時刻) ではなく値で比較する。
    # evaluated_until は evaluator が最後に書く = 完了 marker を兼ねるので、
    # comment だけ書けて途中死亡した session は wm が無く自然に再対象になる
    pending = []
    n_eval = 0
    for sid, s in sessions.items():
        wm = last_wm.get(sid)
        try:
            wm_epoch = float(wm.get("value")) if wm else None
        except (TypeError, ValueError):
            wm_epoch = None
        # max_end が空 (全 obs に start/endTime 無し) なら保守側 (再対象) に倒す
        if wm_epoch is not None and s["max_end"] and \
                _ts(s["max_end"]).timestamp() <= wm_epoch:
            n_eval += 1
            continue
        pending.append(sid)

    # sentinel 判定は session ごとに API round trip が要るので並列にする。
    # workdir/repo_root も stat 連打と git subprocess があるため同じ pool で回す
    def _sentinel_and_repo(sid):
        if sid.startswith(SYNTHETIC_SESSION_PREFIX):
            return "synthetic", None, None
        kind = skip_marker_kind(sid)
        if kind:
            return kind, None, None
        wd, rr = resolve_repo(sessions[sid]["hints"])
        return None, wd, rr

    with ThreadPoolExecutor(max_workers=SENTINEL_WORKERS) as ex:
        info_map = dict(zip(pending, ex.map(_sentinel_and_repo, pending)))

    targets = []
    n_self = 0
    n_synthetic = 0
    for sid in pending:
        kind, wd, rr = info_map[sid]
        if kind == "self":
            n_self += 1
            continue
        if kind == "synthetic":
            n_synthetic += 1
            continue
        s = sessions[sid]
        wm = last_wm.get(sid)
        targets.append({
            "session_id": sid,
            "reason": "new_traces" if wm else "no_score",
            "last_eval": (wm or {}).get("timestamp"),
            "evaluated_until": (wm or {}).get("value"),
            "last_activity": s["max_start"],
            "obs": s["obs"],
            "sources": sorted(s["sources"]),
            "workdir": wd,
            "repo_root": rr,
        })
    targets.sort(key=lambda t: t["last_activity"])
    emit({"ok": True,
          "window": {"from": _iso(since), "to": _iso(now)},
          "targets": targets,
          "skipped": {"evaluated": n_eval, "self": n_self,
                      "synthetic": n_synthetic,
                      "unsafe_sid": len(unsafe_sids),
                      "unsafe_sids": sorted(unsafe_sids)}})


def _io_text(v):
    """root observation の io を text に正規化する。
    devin/claude/pi は {"role":..,"content":..} の JSON string、
    codex は生の string で入る。"""
    if v is None:
        return ""
    if isinstance(v, str):
        try:
            d = json.loads(v)
            if isinstance(d, dict):
                return str(d.get("content") or d.get("text") or v)
        except Exception:
            pass
        return v
    if isinstance(v, dict):
        return str(v.get("content") or v.get("text") or
                  json.dumps(v, ensure_ascii=False))
    return json.dumps(v, ensure_ascii=False)


def _check_sid(sid):
    """session id は任意文字列で、そのまま shell コマンドに埋め込むと
    injection になる。許容文字種を制限して弾く。"""
    if not SESSION_ID_RE.match(sid):
        fail(f"unsafe session_id: {sid!r}")


def cmd_transcript(a):
    _check_sid(a.session_id)
    ensure_env()
    try:
        return _cmd_transcript(a)
    except ApiError as e:
        fail(str(e))


def telemetry_summary(metadata):
    """Compact exporters preserve evaluator signals without individual child spans."""
    value = (metadata or {}).get("telemetry_summary")
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    if not isinstance(value, dict) or value.get("version") != 1:
        return None
    if any(not isinstance(value.get(key), int) or isinstance(value.get(key), bool)
           or value[key] < 0 for key in ("generation_count", "tool_call_count")):
        return None
    if not isinstance(value.get("tool_names"), dict) or not isinstance(value.get("errors"), list):
        return None
    return value


def _cmd_transcript(a):
    sid = a.session_id
    # watermark は「この評価が覆った観測の上限」= 観測済み obs の max
    # (endTime or startTime) の epoch。壁時計の取得時刻を書くと、fetch 後に
    # ingest された turn が「endTime は古いのに transcript 未収録」になり
    # (per-turn export では exporter の emit+flush 遅延で普通に起きうる)、
    # wm 以下扱いされて二度と評価されない。coverage 上限を書くなら、あとから
    # 現れた turn は endTime がより新しいので次回 run で再対象になる
    fetched_at = int(time.time())
    # server 側の sessionId フィルタを信用しつつ、混在応答への防御として
    # 返却行の sessionId も照合する (upstream にフィルタ無視の不具合報告あり)。
    # all_obs (io なし) と turns (io あり・root のみ) は独立なので並列に取る —
    # 1 fetch にまとめると tool io まで取れるが、io は injection 面を広げるため
    # root span に限定する設計を維持する
    def _fetch(q):
        return [o for o in paged("/api/public/v2/observations", q)
                if o.get("sessionId") == sid]
    with ThreadPoolExecutor(max_workers=2) as ex:
        all_obs, turns = ex.map(_fetch, [
            {"sessionId": sid, "fields": "basic,metadata",
             "expandMetadata": EXPAND_METADATA},
            {"sessionId": sid, "fields": "basic,metadata,io",
             "expandMetadata": EXPAND_METADATA,
             "filter": ROOT_FILTER}])
    if not all_obs:
        fail(f"no observations for session {sid}")
    # root span に sessionId が無い実装や server 側 filter 無効化で turns が
    # 空になりうる — その場合も turn_count=0 の空 transcript を返し、
    # 「本文なし = signal なし」の判定は evaluator に任せる
    if any(_sentinel_hit(o) for o in turns):
        emit({"ok": True, "self": True, "session_id": sid})
        return
    if sid.startswith(SYNTHETIC_SESSION_PREFIX) or \
            any(_synthetic_hit(o) for o in turns):
        # self=true に寄せるのは後方互換 — caller は self だけ見て skip する
        emit({"ok": True, "self": True, "synthetic": True,
              "session_id": sid})
        return

    counts, tool_names = Counter(), Counter()
    hints = {"hints": {}, "sources": set()}
    errors = []
    compact = {}
    for o in all_obs:
        if not o.get("id"):
            continue
        summary = telemetry_summary(o.get("metadata"))
        if summary is not None:
            compact[o["id"]] = summary
    by_id = {o["id"]: o for o in all_obs if o.get("id")}

    def compact_child(o):
        # A revised tail can already have old full-mode children in Langfuse.
        # Its authoritative summary supersedes those children, not subagent turns.
        parent = o.get("parentObservationId")
        seen = set()
        while parent and parent not in seen:
            if parent in compact:
                return True
            if by_id.get(parent, {}).get("type") == "AGENT":
                return False
            seen.add(parent)
            parent = by_id.get(parent, {}).get("parentObservationId")
        return False

    for o in all_obs:
        t = o.get("type", "?")
        if t in ("GENERATION", "TOOL") and compact_child(o):
            continue
        counts[t] += 1
        summary = compact.get(o.get("id"))
        if summary is not None:
            for field, kind in (("generation_count", "GENERATION"), ("tool_call_count", "TOOL")):
                n = summary.get(field)
                if isinstance(n, int) and not isinstance(n, bool) and n >= 0:
                    counts[kind] += n
            names = summary.get("tool_names")
            if isinstance(names, dict):
                tool_names.update({name: n for name, n in names.items()
                                   if isinstance(name, str) and isinstance(n, int)
                                   and not isinstance(n, bool) and n >= 0})
            for error in summary.get("errors", []) if isinstance(summary.get("errors"), list) else []:
                if isinstance(error, dict):
                    errors.append({"startTime": error.get("start_time") or o.get("startTime"),
                                   "name": str(error.get("name") or "tool"),
                                   "statusMessage": str(error.get("status_message") or "")[:300]})
        if t == "TOOL":
            tool_names[o.get("name") or "?"] += 1
        _merge_hints(hints, o.get("metadata") or {})
        if o.get("level") == "ERROR":
            errors.append(o)

    items = ([(o.get("startTime") or "", "turn", o) for o in turns] +
             [(o.get("startTime") or "", "err", o) for o in errors])
    items.sort(key=lambda x: x[0])
    lines = []
    for _, kind, o in items:
        if kind == "err":
            lines.append("* %s [ERROR] %s — %s" % (
                o.get("startTime"), o.get("name"),
                (o.get("statusMessage") or "")[:300]))
            continue
        md = o.get("metadata") or {}
        tn = md.get("turn_number")
        name = o.get("name") or "?"
        # turn_number が名前に既に含まれる (Devin - Turn 3) なら重複表示しない
        label = name if (tn is None or str(tn) in name) else "turn %s (%s)" % (tn, name)
        lines.append("--- %s | %s ---" % (label, o.get("startTime")))
        lines.append("[user]\n" + _io_text(o.get("input")))
        lines.append("[assistant]\n" + _io_text(o.get("output")))

    first_ts = min((o.get("startTime") or "" for o in all_obs), default="")
    # last_ts は targets の skip predicate と同じ endTime or startTime の
    # max — watermark もこれから導いて header と score が drift しないようにする。
    # int() で秒に切り捨てると比較側の ms 精度とずれて T <= int(T) が
    # ほぼ常に false になり、新 obs 無しの session が毎 run 再対象になる。
    # 全 obs が timestamp を持たない病理ケースでは fetched_at に倒す
    # (その場合 targets は max_end 空で保守的に再対象にするので、
    #  何を書いても完了 marker としては機能する)
    last_ts = max((o.get("endTime") or o.get("startTime") or ""
                   for o in all_obs), default="")
    wm_epoch = _ts(last_ts).timestamp() if last_ts else fetched_at
    wd, rr = resolve_repo(hints["hints"])
    header = [
        "session: %s" % sid,
        "sources: %s | turns: %d | generations: %d | tool_calls: %d | errors: %d"
        % (",".join(sorted(hints["sources"])) or "?",
           len(turns), counts.get("GENERATION", 0), counts.get("TOOL", 0),
           len(errors)),
        # tool io は意図的に出さない (prompt injection 面を減らす) が、
        # 反復・未使用の判定材料として tool 名の集計は残す
        "tools: %s" % (", ".join("%s×%d" % kv for kv in
                       sorted(tool_names.items())) or "none"),
        "workdir: %s | repo_root: %s" % (wd or "?", rr or "?"),
        "window: %s .. %s" % (first_ts, last_ts),
        "note: 同一 turn_number が複数あるのは exporter が途中経過を再 emit したもの。"
        "ユーザーの繰り返し発言ではない",
        "",
    ]
    body = "\n".join(lines)
    raw = body.encode()
    if len(raw) > a.max_bytes:
        # byte 単位で切る。char スライスだと日本語 transcript で上限を超える
        half = a.max_bytes // 2
        marker = "\n\n... (中略: 全長 %d bytes のうち中盤を省略) ...\n\n" % len(raw)
        body = (raw[:half].decode("utf-8", "replace") + marker +
                raw[-half:].decode("utf-8", "replace"))
    emit({"ok": True, "self": False, "session_id": sid,
          "fetched_at": fetched_at,
          "evaluated_until": wm_epoch,
          "sources": sorted(hints["sources"]),
          "workdir": wd, "repo_root": rr,
          "git_branch": hints["hints"].get("git_branch"),
          "turn_count": len(turns), "tool_calls": counts.get("TOOL", 0),
          "error_count": len(errors),
          "first_ts": first_ts, "last_ts": last_ts,
          "transcript": "\n".join(header) + body})


def cmd_score(a):
    _check_sid(a.session_id)
    ensure_env()
    try:
        return _cmd_score(a)
    except ApiError as e:
        fail(str(e))


def _cmd_score(a):
    comment = a.comment
    if a.comment_file:
        comment = Path(a.comment_file).read_text(encoding="utf-8")
    dt = a.data_type.upper()
    body = {"sessionId": a.session_id, "name": a.name, "dataType": dt}
    # BOOLEAN は payload に数値 0/1 を渡す (読み出しは boolean で返る。実測済み)
    if dt == "BOOLEAN" and a.value not in ("0", "1"):
        fail("BOOLEAN --value must be 0 or 1")
    try:
        if dt == "BOOLEAN":
            body["value"] = int(a.value)
        elif dt == "NUMERIC":
            body["value"] = float(a.value)
        elif dt == "CATEGORICAL":
            body["value"] = str(a.value)
        else:
            fail(f"unknown --data-type: {a.data_type}")
    except ValueError:
        fail(f"invalid --value for {dt}: {a.value}")
    if comment:
        body["comment"] = comment
    resp = api_post("/api/public/scores", body)
    emit({"ok": True, "id": resp.get("id"), "name": a.name,
          "session_id": a.session_id})


def cmd_comment(a):
    _check_sid(a.session_id)
    ensure_env()
    try:
        return _cmd_comment(a)
    except ApiError as e:
        fail(str(e))


def _project_id():
    """comments API は projectId を body に要求する。public API key は
    project スコープなので GET /api/public/projects の1件目が自 project"""
    d = api_get("/api/public/projects", {})
    pid = (d.get("data") or [{}])[0].get("id")
    if not pid:
        raise ApiError("GET /api/public/projects returned no project")
    return pid


def _cmd_comment(a):
    """要約は score ではなく comment オブジェクトに書く。score value は
    機械分類の解釈を埋め込む形になるので持たない — 観測の記録と
    evaluator 所見の分離は comment 本文の見出しで行う。comment は
    append-only なので再評価では追記される (本文冒頭に evaluated_at を
    入れて新旧を区別するのは evaluator 側の責務)。"""
    content = a.content
    if a.content_file:
        content = Path(a.content_file).read_text(encoding="utf-8")
    if not content or not content.strip():
        fail("empty comment content")
    if len(content) > MAX_COMMENT_CHARS:
        # 上限超過の 400 は評価完了 marker が書けず、session が毎 run 再対象に
        # なる永久 wedge になる。モデルの予算超過を evaluator の問題にせず
        # tool 側で切り落とす
        content = (content[:MAX_COMMENT_CHARS] +
                   "\n\n...(comment 上限超過のため省略)")
    resp = api_post("/api/public/comments", {
        "projectId": _project_id(),
        "objectType": "SESSION",
        "objectId": a.session_id,
        "content": content,
    })
    emit({"ok": True, "id": resp.get("id"), "session_id": a.session_id})


def _lock_info():
    try:
        return json.loads((LOCK_DIR / "info.json").read_text())
    except Exception:
        return {}


def cmd_lock(a):
    # mkdir/rmtree の EACCES/ENOSPC 等も JSON 契約に乗せる
    try:
        _cmd_lock(a)
    except OSError as e:
        fail(f"lock: {e}")


def _cmd_lock(a):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if a.action == "status":
        emit({"ok": True, "locked": LOCK_DIR.exists(),
              "holder": _lock_info(), "lock": str(LOCK_DIR)})
        return
    if a.action == "release":
        try:
            shutil.rmtree(LOCK_DIR)
        except FileNotFoundError:
            pass
        emit({"ok": True, "released": True})
        return
    # acquire。fcntl.flock は macOS でも動くが fd が process 寿命に紐づくため、
    # acquire/release を別 process で行うこの CLI 形状には使えず mkdir lock
    try:
        os.mkdir(LOCK_DIR)
    except FileExistsError:
        pass
    else:
        _write_lock()
        return
    # stale 判定は「info.json の ts」と「dir inode」を同じ世代から取る必要がある。
    # stat → read → stat のサンドイッチで両端の inode が一致した場合だけ、
    # 読んだ info.ts はその dir 世代のものと確定できる（間に dir が差し替われば
    # fresh lock を stale 誤認して消しうる）
    try:
        ino1 = os.stat(LOCK_DIR).st_ino
    except OSError:
        emit({"ok": True, "acquired": False, "holder": _lock_info()})
        return
    info = _lock_info()
    try:
        st = os.stat(LOCK_DIR)
        if st.st_ino != ino1:
            raise OSError
    except OSError:
        # 判定中に dir が消えた/差し替わった — 保守的に locked 扱い
        emit({"ok": True, "acquired": False, "holder": info})
        return
    dir_ino = ino1
    try:
        age = time.time() - float(info.get("ts") or st.st_mtime)
    except Exception:
        age = 0
    if age < a.ttl_seconds:
        emit({"ok": True, "acquired": False, "holder": info,
              "age_s": int(age)})
        return
    # stale lock の回収権は LOCK_DIR 内の atomic mkdir で争う。
    # dir 世代の身元は (inode, info.ts) で持つ — stale 判定した dir が
    # 差し替わっていれば回収権は無効（他人の fresh lock を消さないため）
    nonce = _try_recovering()
    if nonce is None:
        emit({"ok": True, "acquired": False, "holder": info,
              "reason": "recovering"})
        return
    if not _recover_owned(dir_ino, nonce, info.get("ts")):
        emit({"ok": True, "acquired": False, "reason": "recovery_lost"})
        return
    try:
        shutil.rmtree(LOCK_DIR)
    except FileNotFoundError:
        pass  # release 等で dir ごと消えた — 次の mkdir が fresh acquire 相当
    try:
        os.mkdir(LOCK_DIR)
    except FileExistsError:
        # rmtree 後の隙間に別 process が正当 acquire した。single-writer は保たれる
        emit({"ok": True, "acquired": False, "holder": _lock_info()})
        return
    _write_lock()


def _try_recovering():
    """stale LOCK_DIR の回収権を取れたら所有証明の nonce を返す。取れなければ None。
    権利は固定名の marker dir (atomic mkdir) で表し、所有の証明は marker 内の
    owner ファイルに書いた nonce で行う — 同じ親 dir 内の rmdir→mkdir は
    inode を再利用するので、inode 一致は「同一 marker」の証明にならない。
    recoverer が rmtree 前に死ぬと marker が残るので、TTL 超の marker は
    回収して再試行する。mkdir→owner 書き込みの間に自分が長時間停止すると
    marker を盗まれて書き直されるので、monotonic clock で自己の停止を
    検知して abort する。"""
    marker = LOCK_DIR / "recovering"
    for _ in range(2):
        t0 = time.monotonic()
        try:
            os.mkdir(marker)
            nonce = secrets.token_hex(8)
            (marker / "owner").write_text(nonce)
            if time.monotonic() - t0 > RECOVER_STALL_S:
                # mkdir→書き込みの隙間に停止した — この marker は盗まれて
                # 作り直された他人のものかもしれない。所有不明なので退く
                # （rmtree は best-effort。既に dir ごと消えていてもよい）
                shutil.rmtree(marker, ignore_errors=True)
                return None
            return nonce
        except FileExistsError:
            try:
                if time.time() - marker.stat().st_mtime < RECOVER_MARKER_TTL_S:
                    return None
                shutil.rmtree(marker)
            except OSError:
                return None
        except OSError:
            # 回収対象の LOCK_DIR 自体が並走 process に消された、
            # または mkdir 直後に dir が消えて owner を書けなかった
            return None
    return None


def _recover_owned(dir_ino, nonce, info_ts):
    """削除してよいのは stale 判定した dir 世代だけ。
    dir inode は delete→recreate で再利用されうるため、世代の身元は
    (dir inode, info.json の ts) の組で見る — inode が再利用されても
    別 process が建てた fresh lock の info.ts は必ず違う。
    rmtree 直前にその組と marker の owner nonce を再照合する。
    dir が差し替わっていて自分の marker が新 dir に迷い込んでいる場合は掃除する。
    残存リスク: この検査→rmtree の数μsの隙間に 60s 超の停止が入る場合のみ。"""
    try:
        same_gen = (os.stat(LOCK_DIR).st_ino == dir_ino and
                    _lock_info().get("ts") == info_ts)
        own = (LOCK_DIR / "recovering" / "owner").read_text() == nonce
        if not (same_gen and own):
            if own:
                # 自分の marker が別世代 dir に迷い込んでいる — 掃除して退く
                shutil.rmtree(LOCK_DIR / "recovering", ignore_errors=True)
            return False
        return True
    except OSError:
        return False


def _write_lock():
    info = {"pid": os.getpid(), "ts": time.time(),
            "ts_iso": _iso(datetime.now(timezone.utc))}
    try:
        (LOCK_DIR / "info.json").write_text(json.dumps(info))
    except OSError:
        # mkdir 後に並走する stale 回収が LOCK_DIR ごと消した。
        # この process は lock を持っていないので偽って acquired:true を出さない
        emit({"ok": True, "acquired": False, "reason": "lock_vanished"})
        return
    emit({"ok": True, "acquired": True, "lock": str(LOCK_DIR)})


def main():
    p = argparse.ArgumentParser(prog="session_eval",
                                description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("targets", help="未評価 session を列挙")
    t.add_argument("--since", help="ISO8601。指定時は --lookback-hours より優先")
    t.add_argument("--lookback-hours", type=float,
                   default=DEFAULT_LOOKBACK_HOURS)
    t.set_defaults(fn=cmd_targets)

    tr = sub.add_parser("transcript", help="1 session の judge 用 transcript")
    tr.add_argument("session_id")
    tr.add_argument("--max-bytes", type=int, default=MAX_TRANSCRIPT_BYTES)
    tr.set_defaults(fn=cmd_transcript)

    s = sub.add_parser("score", help="session に score を書き戻す")
    s.add_argument("--session-id", required=True)
    s.add_argument("--name", required=True)
    # choices を付けない — argparse の exit-2 エラーは JSON 契約を壊すので、
    # 未知の dataType は cmd 側で fail() にする
    s.add_argument("--data-type", default="CATEGORICAL")
    s.add_argument("--value", required=True,
                   help="BOOLEAN は 0/1、CATEGORICAL は文字列、NUMERIC は数値")
    s.add_argument("--comment")
    s.add_argument("--comment-file")
    s.set_defaults(fn=cmd_score)

    c = sub.add_parser("comment", help="session に comment を書き戻す")
    c.add_argument("--session-id", required=True)
    c.add_argument("--content")
    c.add_argument("--content-file")
    c.set_defaults(fn=cmd_comment)

    lk = sub.add_parser("lock", help="batch の single-writer lock")
    lk.add_argument("action", choices=["acquire", "release", "status"])
    lk.add_argument("--ttl-seconds", type=int, default=DEFAULT_LOCK_TTL)
    lk.set_defaults(fn=cmd_lock)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
