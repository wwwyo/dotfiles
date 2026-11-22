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

manifest schema (project automation と bot automation の 2 種類):

  name           automation 名 (upsert の照合 key)
  provider       agent id (pi 等)。project automation の必須 key。bot とは
                 両立しない
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
                 repo_path 指定の new-per-run では無意味なので送らない。
                 extra_agent_args とは両立しない (orca 側制約) — 同時に指定
                 すると load_manifest で error にする
  extra_agent_args  fresh run の agent 起動引数に追加する文字列
                 (例 "--model sonnet")。automation-local で model pin する
                 経路。host の default args (bypass 等) の後に付く。空文字
                 "" で clear (live 残存を消す)。reuse_session とは両立不可
  prompt         {{workspace_path}} / {{repo_path}} を使うと展開後の
                 path に置換される
  trigger        "daily"|"weekdays"|"weekly"|"hourly" → time/day も使う。
                 それ以外は cron 5-field か RRULE 文字列をそのまま渡す
  precheck       run 前に実行するコマンド (exit!=0 で run を skip)。
                 precheck_timeout は秒 (orca 側 default 60 / max 600)

bot automation (`orca automations create --bot`) の key。bot は自分のフォルダ
(~/.orca/bots/<name>) で走り、provider・workspace・repo を持たない:

  bot            bot 名 (`orca bot list` の name)。これがあると bot automation
                 になり、provider / workspace_path / repo_path /
                 reuse_session / extra_agent_args は load_manifest で error
  agent          bot の既定 agent 以外で走らせるときの agent id (pi 等)。
                 省略で bot の agent。model / effort も同様に任意で、どれも
                 runs_in = "new" が必須 (orca 側制約)
  runs_in        "new" (default。run ごとに新しい会話) | "chat" | "chat:<id>"
  results_to     "chat" (default) | "thread" | "none" | "channel:<ch>" |
                 "linear:<issue>"
  workdir        prompt の {{workdir}} を展開するためだけの path (~ 可)。
                 orca には送らない — bot は cwd を選べないので、別 repo で
                 作業させるときは prompt で移動を指示する
  enabled / timezone / trigger / time / day / precheck / prompt は共通

orca automations edit は project ↔ bot の種類を変えられない。同名で種類が
違う live を見つけたら check は KIND MISMATCH を出し、apply は新しい種類で
create してから旧を remove する (remove は旧の run history も消す)。

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

pi task の同期前には dev-env/references/orca.md の launcher 確認を行う。
この script は GUI の model/thinking を検査・配備しない。

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


BOT_FORBIDDEN = ("provider", "workspace_path", "repo_path", "reuse_session",
                 "extra_agent_args")


def load_bot_manifest(p, m):
    bad = [k for k in BOT_FORBIDDEN if k in m]
    if bad:
        raise RuntimeError(
            f"{p.parent.name}/{p.name}: bot automation では {', '.join(bad)} "
            "を使えない (bot は自分のフォルダで走る)")
    runs_in = m.get("runs_in", "new")
    if not (runs_in in ("new", "chat") or runs_in.startswith("chat:")):
        raise RuntimeError(f"{p.name}: runs_in が不正 ({runs_in!r})")
    over = [k for k in ("agent", "model", "effort") if m.get(k)]
    if over and runs_in != "new":
        raise RuntimeError(
            f"{p.name}: {', '.join(over)} は runs_in = \"new\" でしか使えない "
            "(orca 側制約)")
    wd = m.get("workdir")
    wd = os.path.expanduser(wd) if wd else None
    prompt = m.get("prompt", "").strip()
    if "{{workdir}}" in prompt and not wd:
        raise RuntimeError(f"{p.name}: prompt の {{{{workdir}}}} に対応する workdir が無い")
    for key in ("workspace_path", "repo_path"):
        if "{{" + key + "}}" in prompt:
            raise RuntimeError(
                f"{p.name}: bot automation の prompt では {{{{{key}}}}} ではなく "
                "{{workdir}} を使う")
    return {
        "name": m["name"], "bot": m["bot"],
        "agent": m.get("agent"), "model": m.get("model"),
        "effort": m.get("effort"),
        "runs_in": runs_in, "results_to": m.get("results_to", "chat"),
        "enabled": bool(m.get("enabled", True)),
        "timezone": m.get("timezone"),
        "prompt": prompt.replace("{{workdir}}", wd or ""),
        "trigger": m.get("trigger", "daily"),
        "time": m.get("time"), "day": m.get("day"),
        "precheck": m.get("precheck"),
        "precheck_timeout": m.get("precheck_timeout"),
    }


def load_manifest(p):
    m = tomllib.loads(p.read_text(encoding="utf-8"))
    if m.get("bot"):
        return load_bot_manifest(p, m)
    for k in ("agent", "model", "effort", "runs_in", "results_to", "workdir"):
        if k in m:
            raise RuntimeError(
                f"{p.parent.name}/{p.name}: {k} は bot automation 専用の key")
    if not m.get("provider"):
        raise RuntimeError(f"{p.parent.name}/{p.name}: provider が無い")
    wp = m.get("workspace_path")
    rp = m.get("repo_path")
    if wp and rp:
        raise RuntimeError(
            f"{p.name}: workspace_path と repo_path は両立しない")
    wp = os.path.expanduser(wp) if wp else None
    rp = os.path.expanduser(rp) if rp else None
    reuse = bool(m.get("reuse_session", False))
    if reuse and m.get("extra_agent_args"):
        raise RuntimeError(
            f"{p.name}: extra_agent_args は reuse_session と両立しない "
            "(orca 側制約) — model pin なら reuse を外す")
    eaa = m.get("extra_agent_args")
    if eaa is not None and not isinstance(eaa, str):
        # check で素通りして apply の文字列結合で TypeError にならないよう
        # 読み込み時に型を検証する
        raise RuntimeError(
            f"{p.name}: extra_agent_args は文字列 (例 \"--model ...\") "
            f"でなければいけない (got {type(eaa).__name__})")
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
        "extra_agent_args": m.get("extra_agent_args"),
    }


def _schedule_flags(m):
    f = ["--trigger", m["trigger"]]
    if m.get("time"):
        f += ["--time", m["time"]]
    if m.get("day") is not None:
        f += ["--day", str(m["day"])]
    if m.get("timezone"):
        f += ["--timezone", m["timezone"]]
    return f


def _precheck_flags(m, live):
    f = []
    if m.get("precheck"):
        f += ["--precheck", m["precheck"]]
        if m.get("precheck_timeout"):
            f += ["--precheck-timeout", str(m["precheck_timeout"])]
    elif live and (live.get("precheck") or {}).get("command"):
        # manifest から precheck を外した = 無いのが正解。edit は送った
        # field しか変えないので、live 残存を消すには空文字を明示する
        f += ["--precheck", ""]
    return f


def bot_flags(m, live=None):
    """bot automation の create (live=None) / edit 用 flag。--bot は create
    だけが受け付ける (edit で bot は変えられない)。"""
    f = _schedule_flags(m)
    if live is None:
        f += ["--bot", m["bot"]]
    f += ["--runs-in", m["runs_in"], "--results-to", m["results_to"]]
    if m.get("agent"):
        # 同じ agent を再指定すると、その agent の既定に戻ったうえで
        # model/effort が付く。manifest から外した model/effort もこれで消える
        f += ["--agent", m["agent"]]
    elif live is not None and _bot_setup(live):
        # manifest に agent が無い = bot の agent が正解。live の上書きを外す
        f += ["--agent", "bot"]
    if m.get("model"):
        f += ["--model", m["model"]]
    if m.get("effort"):
        f += ["--effort", m["effort"]]
    f += _precheck_flags(m, live)
    f += ["--enabled" if m["enabled"] else "--disabled",
          "--prompt", m["prompt"]]
    return f


def expected_flags(m, live=None):
    if m.get("bot"):
        return bot_flags(m, live)
    f = _schedule_flags(m)
    if m.get("workspace_path"):
        f += ["--workspace", "path:" + m["workspace_path"],
               "--workspace-mode", "existing",
               "--reuse-session" if m["reuse_session"]
               else "--fresh-session"]
    elif m.get("repo_path"):
        f += ["--repo", "path:" + m["repo_path"],
               "--workspace-mode", "new-per-run"]
    f += _precheck_flags(m, live)
    if m.get("extra_agent_args"):
        f += ["--extra-agent-args=" + m["extra_agent_args"]]
    elif live and (live.get("extraAgentArgs") or ""):
        # manifest から外した = 無いのが正解。edit は送った field しか
        # 変えないので、live 残存を消すには空文字を明示する
        f += ["--extra-agent-args="]
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


def _bot_setup(live):
    return (live.get("bot") or {}).get("agentSetup") or {}


def _bot_launch(live):
    """live の agent 上書き (agentSetup) → (agent, model, effort)。
    実物: {"agent": "pi", "launch": {"model": ..., "options": {"effort": ...}}}"""
    s = _bot_setup(live)
    launch = s.get("launch") or {}
    return (s.get("agent"), launch.get("model"),
            (launch.get("options") or {}).get("effort"))


def is_bot(live):
    return bool(live.get("bot"))


def _common_drifts(m, live):
    d = {}
    if bool(live.get("enabled")) != m["enabled"]:
        d["enabled"] = (live.get("enabled"), m["enabled"])
    if (live.get("prompt") or "").strip() != m["prompt"]:
        d["prompt"] = ("<differs>", "<manifest>")
    if m.get("timezone") and live.get("timezone") != m["timezone"]:
        d["timezone"] = (live.get("timezone"), m["timezone"])
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


def bot_drifts(m, live, bot_id):
    d = _common_drifts(m, live)
    b = live.get("bot") or {}
    if b.get("botId") != bot_id:
        # edit で bot は変えられないので、apply は作り直しで寄せる
        d["bot"] = (b.get("botId"), f"{m['bot']} ({bot_id})")
    if b.get("runsIn") != m["runs_in"]:
        d["runs_in"] = (b.get("runsIn"), m["runs_in"])
    if b.get("resultsTo") != m["results_to"]:
        d["results_to"] = (b.get("resultsTo"), m["results_to"])
    got = _bot_launch(live)
    for k, g, w in zip(("agent", "model", "effort"), got,
                       (m.get("agent"), m.get("model"), m.get("effort"))):
        if (g or None) != (w or None):
            d[k] = (g, w)
    return d


def field_drifts(m, live):
    d = _common_drifts(m, live)
    if live.get("agentId") != m["provider"]:
        d["provider"] = (live.get("agentId"), m["provider"])
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
    if (live.get("extraAgentArgs") or "") != (m.get("extra_agent_args") or ""):
        # manifest が無い = 無いのが正解。live 残存も drift として検出する
        d["extra_agent_args"] = (live.get("extraAgentArgs"),
                                 m.get("extra_agent_args"))
    return d


def bot_ids():
    res = orca_json(["bot", "list"])
    return {b["name"]: b["id"] for b in (res or {}).get("bots", [])}


def create(m):
    orca_json(["automations", "create", "--name", m["name"],
               *expected_flags(m)])


def remove(live):
    orca_json(["automations", "remove", live["id"]])


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if mode not in ("check", "apply"):
        sys.exit("usage: sync_automations.py [check|apply] [name]")
    only = sys.argv[2] if len(sys.argv) > 2 else None

    live = {}
    res = orca_json(["automations", "list"])
    for a in (res or {}).get("automations", []):
        live.setdefault(a.get("name"), []).append(a)

    manifests = []
    for toml in sorted(TASKS_DIR.glob("*/automation.toml")):
        m = load_manifest(toml)
        if not only or m["name"] == only:
            manifests.append((toml, m))
    bots = bot_ids() if any(m.get("bot") for _, m in manifests) else {}

    rc = 0
    for toml, m in manifests:
        rel = toml.relative_to(TASKS_DIR)
        want_bot = bool(m.get("bot"))
        bot_id = None
        if want_bot:
            bot_id = bots.get(m["bot"])
            if not bot_id:
                print(f"{m['name']}: ERROR bot {m['bot']!r} が無い "
                      f"(orca bot list: {sorted(bots)})")
                rc = 1
                continue
        same = [a for a in live.get(m["name"], []) if is_bot(a) == want_bot]
        other = [a for a in live.get(m["name"], []) if is_bot(a) != want_bot]
        # 同じ bot を指すものを優先 (bot 変更の作り直し途中で 2 つ並ぶ場合)
        same.sort(key=lambda a: (a.get("bot") or {}).get("botId") != bot_id)
        ex = same[0] if same else None
        kind = "bot" if want_bot else "project"
        if other:
            # orca automations edit は種類を変えられない。新しい種類を先に
            # create し、成功してから旧を消す (create 失敗で旧も失わない)
            ids = ", ".join(a["id"] for a in other)
            print(f"{m['name']}: KIND MISMATCH (live は "
                  f"{'bot' if is_bot(other[0]) else 'project'} automation "
                  f"{ids}、manifest は {kind})")
        if ex is None:
            print(f"{m['name']}: MISSING {kind} automation "
                  f"(would create from {rel})")
            if mode == "apply":
                create(m)
                print("  created")
            else:
                rc = 1
        else:
            drifts = (bot_drifts(m, ex, bot_id) if want_bot
                      else field_drifts(m, ex))
            if not drifts:
                print(f"{m['name']}: in sync (id {ex.get('id')})")
            else:
                print(f"{m['name']}: DRIFT (id {ex.get('id')})")
                for k, (got, want) in drifts.items():
                    print(f"  {k}: live={got!r} -> want={want!r}")
                if mode != "apply":
                    rc = 1
                elif "bot" in drifts:
                    create(m)
                    remove(ex)
                    print(f"  recreated on bot {m['bot']} (removed {ex['id']})")
                else:
                    if want_bot and (
                            ("model" in drifts and not m.get("model")) or
                            ("effort" in drifts and not m.get("effort"))):
                        # 同じ --agent の再指定は live の model/effort を残す
                        # (実測)。外すには一度 bot の agent に戻す
                        orca_json(["automations", "edit", ex["id"],
                                   "--agent", "bot"])
                        ex = {**ex, "bot": {**ex["bot"], "agentSetup": None}}
                    # edit は分かった field だけでなく全 flag を送り冪等に寄せる
                    orca_json(["automations", "edit", ex["id"],
                               *expected_flags(m, ex)])
                    print("  edited")
        if other:
            if mode == "apply":
                for a in other:
                    remove(a)
                    print(f"  removed old {a['id']}")
            else:
                rc = 1
    if mode == "check" and rc:
        print("\n(dry-run: `sync_automations.py apply` で反映)")
    sys.exit(rc)


if __name__ == "__main__":
    main()
