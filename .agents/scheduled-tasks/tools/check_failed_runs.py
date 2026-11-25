#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""check_failed_runs — 直近 N 日の pi session から「何もせず終わった run」を集計する。

無人 automation の失敗は repo に痕跡を残さない（`daily/<date>/` が無い、commit が
無い、だけ）。pi の session jsonl には失敗時の `stopReason` と provider が返した
`errorMessage` が残るので、そこだけを読んで原因文付きで列挙する。Langfuse の評価を
待たずに、402（残高切れ）・429（rate limit / 無料枠）のような「1 手目で落ちて何も
生成しない」失敗を翌日には拾えるようにするのが目的。評価 batch（session-eval）が
毎 run の冒頭で呼び、報告に載せる。

  python3 check_failed_runs.py [--days 7] [--sessions-dir DIR] [--json]

- 対象は pi の session file のみ（`~/.pi/agent/sessions/*/*.jsonl`）。claude / codex
  の session はここには無い — Langfuse 側の評価で拾う
- 窓は失敗 turn の時刻で判定する。file mtime は「その session が最近書かれたか」の
  前段フィルタにだけ使い、そのままでは使わない — 古い session に成功 turn が 1 つ
  積まれると mtime が更新され、窓外の失敗が「直近の失敗」として出てしまう
- 「失敗 turn」= user message で始まる turn の最後の assistant message が
  `stopReason: error|aborted` か `errorMessage` 付き。turn の途中で失敗して retry で
  復帰したものは数えない（retry 後の assistant message が turn の最後になる）
- 同じ `errorMessage` はまとめて 1 行にし、件数・期間・cwd を添える（残高切れのように
  数日続く outage を 1 行で読めるようにする）
- 出力は報告用のテキスト。失敗が見つかっても exit 0（呼び出し側の batch を止めない）
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from datetime import datetime, timezone

DEFAULT_SESSIONS_DIR = "~/.pi/agent/sessions"
FAILED_STOP_REASONS = {"error", "aborted"}
MSG_LIMIT = 140


def _parse_ts(ts):
    """jsonl の timestamp（ISO8601 文字列 or epoch 秒/ms）を aware datetime に。"""
    if ts is None or isinstance(ts, bool):
        return None
    if isinstance(ts, (int, float)):
        sec = ts / 1000 if ts > 1e11 else ts
        return datetime.fromtimestamp(sec, timezone.utc)
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _iso(ts):
    """jsonl の timestamp を UTC の ISO に揃える。読めない値は素通しする。"""
    if ts is None:
        return None
    dt = _parse_ts(ts)
    if dt is None:
        return str(ts)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _normalize_message(msg):
    """errorMessage を 1 行に潰す。切り詰めは表示時だけ行う — group key に使う
    値を切ると、先頭 MSG_LIMIT 字が同じで原因が違う error を 1 行に混ぜてしまう。"""
    return " ".join(str(msg).split())


def _session_failed_turns(path):
    """1 session file → 失敗 turn の list。壊れた行は無視する。"""
    sid = cwd = None
    turn = None
    failed = []
    try:
        fh = open(path, encoding="utf-8", errors="replace")
    except OSError:
        return []
    # 失敗判定は turn の区切り（次の user message / EOF）で行う。ループ中に
    # 判定すると、error の後の retry で復帰した turn を失敗に数えてしまう
    with fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            kind = d.get("type")
            if kind == "session":
                sid = d.get("id")
                cwd = d.get("cwd")
                continue
            if kind != "message":
                continue
            m = d.get("message") or {}
            role = m.get("role")
            if role == "user":
                if turn and _turn_failed(turn["last"]):
                    failed.append(_row(sid, cwd, turn))
                turn = {"start": _iso(d.get("timestamp")), "last": None, "last_ts": None}
            elif role == "assistant" and turn is not None:
                turn["last"] = m
                turn["last_ts"] = _iso(d.get("timestamp"))
    if turn and _turn_failed(turn["last"]):
        failed.append(_row(sid, cwd, turn))
    return failed


def _turn_failed(last):
    if not last:
        return False
    return last.get("stopReason") in FAILED_STOP_REASONS or bool(last.get("errorMessage"))


def _row(sid, cwd, turn):
    last = turn["last"]
    return {
        "session_id": sid,
        "cwd": cwd,
        "start": turn["start"],
        "end": turn["last_ts"],
        "stop_reason": last.get("stopReason"),
        "error": _normalize_message(last.get("errorMessage") or ""),
    }


def _in_window(row, cutoff):
    """失敗 turn の時刻が窓内か。時刻が読めない turn は落とさず残す。"""
    for ts in (row["end"], row["start"]):
        dt = _parse_ts(ts)
        if dt is not None:
            return dt.timestamp() >= cutoff
    return True


def collect(sessions_dir=DEFAULT_SESSIONS_DIR, days=7, now=None):
    """直近 `days` 日の失敗 turn を返す。

    file mtime は session を読むかの前段フィルタ。窓の判定は失敗 turn の時刻で
    行う — mtime だけだと、古い session に成功 turn が積まれて更新されたときに
    窓外の失敗まで拾ってしまう。
    """
    now = now or datetime.now(timezone.utc)
    cutoff = now.timestamp() - days * 86400
    root = os.path.expanduser(sessions_dir)
    rows = []
    seen_sessions = 0
    for path in sorted(glob.glob(os.path.join(root, "*", "*.jsonl"))):
        try:
            if os.path.getmtime(path) < cutoff:
                continue
        except OSError:
            continue
        seen_sessions += 1
        rows.extend(r for r in _session_failed_turns(path)
                    if _in_window(r, cutoff))
    rows.sort(key=lambda r: r["start"] or "")
    return rows, seen_sessions


def group(rows):
    """errorMessage ごとにまとめる。長い outage を 1 行で読むため。"""
    groups = {}
    for r in rows:
        key = r["error"] or f"(no error message; stopReason={r['stop_reason']})"
        g = groups.setdefault(key, {"error": key, "turns": 0, "cwds": {}, "first": None,
                                    "last": None, "stop_reasons": set(), "sessions": []})
        g["turns"] += 1
        # errorMessage だけあって stopReason が無い行がある。None を混ぜると
        # sorted()/join() が型エラーで落ちるので、報告は残したまま文字列に倒す
        g["stop_reasons"].add(r["stop_reason"] or "unknown")
        cwd = r["cwd"] or "(unknown cwd)"
        g["cwds"][cwd] = g["cwds"].get(cwd, 0) + 1
        if r["start"] and (g["first"] is None or r["start"] < g["first"]):
            g["first"] = r["start"]
        if r["end"] and (g["last"] is None or r["end"] > g["last"]):
            g["last"] = r["end"]
        if r["session_id"] and r["session_id"] not in g["sessions"]:
            g["sessions"].append(r["session_id"])
    out = sorted(groups.values(), key=lambda g: (-g["turns"], g["error"]))
    for g in out:
        g["stop_reasons"] = sorted(g["stop_reasons"])
        g["cwds"] = sorted(g["cwds"].items(), key=lambda kv: -kv[1])
    return out


def render(rows, seen_sessions, days, now=None):
    now = now or datetime.now(timezone.utc)
    if not rows:
        return (f"failed runs: none ({seen_sessions} pi sessions scanned, "
                f"last {days}d, now {now.strftime('%Y-%m-%dT%H:%M:%SZ')})")
    lines = [f"failed runs: {len(rows)} turns in {len({r['session_id'] for r in rows})} "
             f"sessions ({seen_sessions} pi sessions scanned, last {days}d, "
             f"now {now.strftime('%Y-%m-%dT%H:%M:%SZ')})"]
    for g in group(rows):
        span = f"{g['first']}..{g['last']}"
        cwds = ", ".join(f"{c} ({n})" for c, n in g["cwds"][:2])
        lines.append(f"- {g['turns']}x [{','.join(g['stop_reasons'])}] {span} {cwds}")
        lines.append(f"    {g['error'][:MSG_LIMIT]}")
        lines.append(f"    sessions: {', '.join(g['sessions'][:4])}"
                     + (" …" if len(g["sessions"]) > 4 else ""))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="直近 N 日の pi session から失敗 turn を原因文付きで集計する")
    ap.add_argument("--days", type=int, default=7,
                    help="走査する過去日数（既定 7）")
    ap.add_argument("--sessions-dir", default=DEFAULT_SESSIONS_DIR,
                    help=f"pi session の置き場（既定 {DEFAULT_SESSIONS_DIR}）")
    ap.add_argument("--json", action="store_true", help="JSON で出す")
    a = ap.parse_args(argv)
    rows, seen = collect(a.sessions_dir, a.days)
    if a.json:
        print(json.dumps({"ok": True, "scanned_sessions": seen, "days": a.days,
                          "failed_turns": len(rows), "runs": rows,
                          "groups": group(rows)}, ensure_ascii=False, indent=1))
    else:
        print(render(rows, seen, a.days))
    return 0


if __name__ == "__main__":
    sys.exit(main())
