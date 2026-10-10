#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# ///
"""sync_automations — .agents/scheduled-tasks/*/automation.toml を orca
automations の実状態に upsert する。

automation.toml が git 上の desired state (SSOT)、この script が
`orca automations list` と突き合わせて create/edit する。登録そのものは
orca CLI に任せる (workspace/repo の解決・sourceContext の付与は orca 側の
責務なので、ここで再実装しない)。

  check (default)  drift を表示するだけ。変更しない
  apply            create / edit で実状態を manifest に寄せる

manifest schema:

  name           automation 名 (upsert の照合 key)
  provider       agent id (pi 等)
  enabled        bool
  timezone       IANA tz
  workspace_path 既存 workspace の path (~ 可。repo に username を書かない
                 ためここで展開する)。--workspace に渡し mode=existing
  repo_path      repo の path (~ 可)。--repo に渡し mode=new-per-run
                 (run ごとにその repo の新 worktree)。workspace_path と
                 両立しない。両方省略だと create 時に cwd から enclosing
                 worktree が bind されうるので、apply は Orca worktree 内
                 から実行しない
  reuse_session  existing workspace の前回 live session を使い回す
                 (orca --reuse-session。false は --fresh-session を明示)。
                 run ごとに新しい agent session が履歴に積まれるのを防ぐ。
                 repo_path 指定の new-per-run では無意味なので送らない
  prompt         {{workspace_path}} / {{repo_path}} を使うと展開後の
                 path に置換される
  trigger        "daily"|"weekdays"|"weekly"|"hourly" → time/day も使う。
                 それ以外は cron 5-field か RRULE 文字列をそのまま渡す
  precheck       run 前に実行するコマンド (exit!=0 で run を skip)。
                 precheck_timeout は秒 (orca 側 default 60 / max 600)

live 側との schedule 比較は daily (BYHOUR/BYMINUTE)・FREQ= 指定の
rrule 集合・cron (verbatim 格納なので文字列比較) を厳密に見る。
weekdays/weekly/hourly preset は orca 内部の変換規則を復元できないので
schedule drift は未判定 (prompt/provider/enabled/workspace の差分のみ
検出する)。なお orca の rrule parser は FREQ=HOURLY/DAILY/WEEKLY と
INTERVAL のみ対応する (MINUTELY は書けない) — 30分間隔等は cron を使う。
ただし INTERVAL は parse されても scheduler が発火判定に使わない実測
がある (2026-09-29、FREQ=DAILY;INTERVAL=3 が 3 日連続で発火)。
N 日おきは cron の DOM `*/N` で書くこと。

新しい trigger 形式を初めて使うときは parse 通過と発火判定は別物なので、
短周期の probe automation を別名で登録して実際に nextRunAt が進むかを
確認してから削除する。apply 後は `orca automations` で live の
nextRunAt を見て閉じる — manifest の upsert 成功は発火の保証にならない。

usage: sync_automations.py [check|apply] [name]
  name を指定するとその automation だけを対象にする。
  apply は全ての create/edit が成功したとき exit 0、check は drift が
  あれば exit 1。
"""

import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

TASKS_DIR = Path(__file__).resolve().parent.parent


def _orca_cmd():
    """orca-cli skill の解決手順。Linux で裸の `orca` は GNOME screen reader
    に解決されるので素通ししない。候補が起動に失敗しても次には進まない
    （別 build を暗黙に選ぶと別 Orca を叩きうる）。"""
    if os.environ.get("ORCA_CLI_COMMAND"):
        return os.environ["ORCA_CLI_COMMAND"]
    if os.environ.get("ORCA_DEV_REPO_ROOT"):
        return "orca-dev"
    if sys.platform != "darwin":
        return "orca-ide"
    return "orca"


ORCA = _orca_cmd()


def sh(args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError(f"{args[0]} {args[1]} failed: {r.stderr.strip()[:400]}")
    return r


def orca_json(args):
    d = json.loads(sh([ORCA, *args, "--json"]).stdout or "{}")
    if isinstance(d, dict) and d.get("ok") is False:
        raise RuntimeError(f"orca {' '.join(args)}: {d.get('error')}")
    res = d.get("result", d) if isinstance(d, dict) else d
    return res


def load_manifest(p):
    m = tomllib.loads(p.read_text(encoding="utf-8"))
    wp = m.get("workspace_path")
    rp = m.get("repo_path")
    if wp and rp:
        raise RuntimeError(
            f"{p.name}: workspace_path と repo_path は両立しない")
    wp = os.path.expanduser(wp) if wp else None
    rp = os.path.expanduser(rp) if rp else None
    prompt = m.get("prompt", "").strip()
    for key, val in (("workspace_path", wp), ("repo_path", rp)):
        if "{{" + key + "}}" in prompt and not val:
            raise RuntimeError(
                f"{p.name}: prompt の {{{{{key}}}}} に対応する {key} が無い")
    prompt = prompt.replace("{{workspace_path}}", wp or "")
    prompt = prompt.replace("{{repo_path}}", rp or "")
    return {
        "name": m["name"], "provider": m["provider"],
        "enabled": bool(m.get("enabled", True)),
        "timezone": m.get("timezone"),
        "workspace_path": wp, "repo_path": rp,
        "prompt": prompt,
        "trigger": m.get("trigger", "daily"),
        "time": m.get("time"), "day": m.get("day"),
        "precheck": m.get("precheck"),
        "precheck_timeout": m.get("precheck_timeout"),
        "reuse_session": bool(m.get("reuse_session", False)),
    }


def expected_flags(m, live=None):
    f = ["--trigger", m["trigger"]]
    if m.get("time"):
        f += ["--time", m["time"]]
    if m.get("day") is not None:
        f += ["--day", str(m["day"])]
    if m.get("timezone"):
        f += ["--timezone", m["timezone"]]
    if m.get("workspace_path"):
        f += ["--workspace", "path:" + m["workspace_path"],
               "--workspace-mode", "existing",
               "--reuse-session" if m["reuse_session"]
               else "--fresh-session"]
    elif m.get("repo_path"):
        f += ["--repo", "path:" + m["repo_path"],
               "--workspace-mode", "new-per-run"]
    if m.get("precheck"):
        f += ["--precheck", m["precheck"]]
        if m.get("precheck_timeout"):
            f += ["--precheck-timeout", str(m["precheck_timeout"])]
    elif live and (live.get("precheck") or {}).get("command"):
        # manifest から precheck を外した = 無いのが正解。edit は送った
        # field しか変えないので、live 残存を消すには空文字を明示する
        f += ["--precheck", ""]
    f += ["--provider", m["provider"],
          "--enabled" if m["enabled"] else "--disabled",
          "--prompt", m["prompt"]]
    return f


def norm_rrule(s):
    return set((s or "").split(";"))


def _rrule_parts(rr):
    # DTSTART/WKST は rrule のノイズキーとして除外し、INTERVAL/BYDAY 等の
    # 意味を持つキーは完全一致で比較する (部分集合だと 3日おきや平日限定が
    # 「daily」と in sync 判定されてしまう)
    return {p for p in norm_rrule(rr)
            if not p.startswith(("DTSTART", "WKST"))}


def schedule_drift(m, live):
    """daily・FREQ= 指定・cron は厳密比較。hourly/weekdays/weekly preset は
    orca 内部の変換規則を復元できないので未判定 (False) を返す。"""
    t = m["trigger"]
    parts = _rrule_parts(live.get("rrule") or "")
    if t == "daily":
        want = {"FREQ=DAILY"}
        if m.get("time"):
            h, mi = m["time"].split(":")
            want |= {f"BYHOUR={int(h)}", f"BYMINUTE={int(mi)}"}
        return want != parts
    if t.startswith("FREQ="):
        return _rrule_parts(t) != parts
    if t in ("hourly", "weekdays", "weekly"):
        return False
    # cron: live の rrule には入力が verbatim に入る ("*/30 * * * *")。
    # FREQ=/BYHOUR のような preset 分解は起きないので連続空白を潰した
    # 文字列比較で合う
    return " ".join(t.split()) != " ".join((live.get("rrule") or "").split())


def field_drifts(m, live):
    d = {}
    if live.get("agentId") != m["provider"]:
        d["provider"] = (live.get("agentId"), m["provider"])
    if bool(live.get("enabled")) != m["enabled"]:
        d["enabled"] = (live.get("enabled"), m["enabled"])
    if (live.get("prompt") or "").strip() != m["prompt"]:
        d["prompt"] = ("<differs>", "<manifest>")
    if m.get("timezone") and live.get("timezone") != m["timezone"]:
        d["timezone"] = (live.get("timezone"), m["timezone"])
    wp = m.get("workspace_path")
    rp = m.get("repo_path")
    if wp:
        wid = live.get("workspaceId") or ""
        if not wid.endswith("::" + wp):
            d["workspace"] = (wid, wp)
        if live.get("workspaceMode") != "existing":
            d["workspaceMode"] = (live.get("workspaceMode"), "existing")
        if bool(live.get("reuseSession")) != m["reuse_session"]:
            d["reuse_session"] = (live.get("reuseSession"),
                                  m["reuse_session"])
    elif rp:
        # repo-bound は workspaceId=null で runContext.path が manifest の
        # repo を指す。mode は new_per_run
        ctx_path = (live.get("runContext") or {}).get("path") or ""
        if live.get("workspaceId") or ctx_path != rp:
            d["target"] = (ctx_path or live.get("workspaceId"), rp)
        if live.get("workspaceMode") != "new_per_run":
            d["workspaceMode"] = (live.get("workspaceMode"), "new_per_run")
    # workspace_path/repo_path 両方無しの manifest は target drift を
    # 検査しない (create 時に cwd 依存で bind される orca 仕様上、
    # 「未指定が正解」の意味を持てないため)
    # manifest に precheck が無い = 無いのが正解 — live 残存も drift として
    # 検出する（外したのに残る precheck は run を skip し続ける）
    pc = live.get("precheck") or {}
    if (pc.get("command") or "") != (m.get("precheck") or ""):
        d["precheck"] = (pc.get("command"), m.get("precheck"))
    if m.get("precheck") and m.get("precheck_timeout") and \
            pc.get("timeoutSeconds") != m["precheck_timeout"]:
        d["precheck_timeout"] = (pc.get("timeoutSeconds"),
                                 m["precheck_timeout"])
    sd = schedule_drift(m, live)
    if sd:
        d["schedule"] = (live.get("rrule"), f"{m['trigger']} {m.get('time') or ''}")
    return d


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode not in ("check", "apply"):
        sys.exit("usage: sync_automations.py [check|apply] [name]")
    only = sys.argv[2] if len(sys.argv) > 2 else None

    live = {}
    res = orca_json(["automations", "list"])
    for a in (res or {}).get("automations", []):
        live[a.get("name")] = a

    rc = 0
    for toml in sorted(TASKS_DIR.glob("*/automation.toml")):
        m = load_manifest(toml)
        if only and m["name"] != only:
            continue
        ex = live.get(m["name"])
        rel = toml.relative_to(TASKS_DIR)
        if ex is None:
            print(f"{m['name']}: MISSING (would create from {rel})")
            if mode == "apply":
                orca_json(["automations", "create", "--name", m["name"],
                           *expected_flags(m)])
                print("  created")
            else:
                rc = 1
            continue
        drifts = field_drifts(m, ex)
        if not drifts:
            print(f"{m['name']}: in sync (id {ex.get('id')})")
            continue
        print(f"{m['name']}: DRIFT (id {ex.get('id')})")
        for k, (got, want) in drifts.items():
            print(f"  {k}: live={got!r} -> want={want!r}")
        if mode == "apply":
            # edit は分かった field だけでなく全 flag を送り冪等に寄せる
            orca_json(["automations", "edit", ex["id"],
                       *expected_flags(m, ex)])
            print("  edited")
        else:
            rc = 1
    if mode == "check" and rc:
        print("\n(dry-run: `sync_automations.py apply` で反映)")
    sys.exit(rc)


if __name__ == "__main__":
    main()
