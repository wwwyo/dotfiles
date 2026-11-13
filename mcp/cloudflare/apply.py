#!/usr/bin/env python3
"""Cloudflare MCP portal・MCP server・それらの Access app を宣言（このディレクトリの JSON）に合わせる。

  python3 mcp/cloudflare/apply.py                      # 差分を表示（変更しない。差分ありで exit 1）
  python3 mcp/cloudflare/apply.py --apply              # 差分のある resource を更新し、再取得して一致を確認
  python3 mcp/cloudflare/apply.py --apply --rotate-credentials context7
                                                       # credential_env の値で server の credential を差し替える
  python3 mcp/cloudflare/apply.py --import             # 現状を宣言ファイルへ書き出す（初回・取り込み用）

`cf` CLI（OAuth ログイン済み）を sandbox 外で呼ぶ。stdlib だけで動く。

- portal の update（PUT）は省いた項目を既定値に戻すので、宣言の全項目を毎回送る
- server の update は auth_credentials を省くと既存の credential を保持する。credential は宣言に書かず、
  `credential_env`（mise の環境変数名）を `--rotate-credentials <id>` で指定したときだけ送る
- server の hostname・auth_type、OAuth（manual）の client 設定は update で変えられないので比較だけ行う
  （変えるときは server を作り直す）
- Access policy の条件（include/exclude/require）は比較だけ行う。宣言中の `<account_id>` と `<owner_email>`
  は `cf auth whoami` の値に置き換えて比較する（public repo にメールを書かない）
- OAuth upstream の「サーバーの認証」（ダッシュボードの server 画面のボタン）は API・cf に無く自動化できない
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
OAUTH_NOTE = (
    "auth_type が oauth の server は、作成・再作成後にダッシュボードの server 画面で「サーバーの認証」を押す"
    "必要がある（cf・API に相当操作が無く自動化できない）"
)

# ---------------------------------------------------------------- cf

def cf(*args, body=None):
    cmd = ["cf", *args]
    tmp = None
    if body is not None:
        fd, tmp = tempfile.mkstemp(suffix=".json")  # 0600。credential を argv に載せない
        with os.fdopen(fd, "w") as f:
            json.dump(body, f, ensure_ascii=False)
        cmd += ["--body", f"@{tmp}"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
    finally:
        if tmp:
            os.unlink(tmp)
    if res.returncode != 0:
        sys.exit(f"{' '.join(args[:4])} が失敗した:\n{res.stderr.strip() or res.stdout.strip()}")
    return json.loads(res.stdout) if res.stdout.strip() else None


def whoami():
    w = cf("auth", "whoami")
    return {"<owner_email>": w["email"], "<account_id>": w["accounts"][0]["id"]}


def substitute(obj, table):
    if isinstance(obj, str):
        return table.get(obj, obj)
    if isinstance(obj, list):
        return [substitute(x, table) for x in obj]
    if isinstance(obj, dict):
        return {k: substitute(v, table) for k, v in obj.items()}
    return obj


def mask(obj, table):
    return substitute(obj, {v: k for k, v in table.items()})

# ---------------------------------------------------------------- 正規化（API の応答 → 宣言と同じ形）

def overrides(items, enabled_key="enabled", alias_key="alias", desc_key="description"):
    """既定（有効・alias なし）から外れた tool / prompt だけを name → 設定 で返す。"""
    out = {}
    for t in items or []:
        o = {}
        if t.get(enabled_key) is False:
            o["enabled"] = False
        if t.get(alias_key):
            o["alias"] = t[alias_key]
        if t.get(desc_key):
            o["description"] = t[desc_key]
        if o:
            out[t["name"]] = o
    return dict(sorted(out.items()))


def norm_server(s):
    d = {
        "id": s["id"],
        "name": s["name"],
        "description": s.get("description") or None,
        "hostname": s["hostname"],
        "auth_type": s["auth_type"],
        "secure_web_gateway": s["secure_web_gateway"],
        "is_shared_oauth_callback_enabled": s.get("is_shared_oauth_callback_enabled", False),
        "tool_overrides": overrides(s.get("updated_tools")),
        "prompt_overrides": overrides(s.get("updated_prompts")),
    }
    summary = s.get("auth_config_summary")
    if summary and summary.get("auth_mode") == "manual":
        d["oauth_manual"] = {"config": summary.get("config"), "registration_info": summary.get("registration_info")}
    return d


def norm_portal(p):
    return {
        "id": p["id"],
        "name": p["name"],
        "description": p.get("description") or None,
        "hostname": p["hostname"],
        "secure_web_gateway": p["secure_web_gateway"],
        "code_mode": p["code_mode"],
        "servers": sorted(
            (
                {
                    "server_id": s["server_id"],
                    "on_behalf": s["on_behalf"],
                    "default_disabled": s.get("default_disabled", False),
                    "tool_overrides": overrides(s.get("updated_tools"), "portal_enabled", "portal_alias", "portal_description"),
                    "prompt_overrides": overrides(s.get("updated_prompts"), "portal_enabled", "portal_alias", "portal_description"),
                }
                for s in p.get("servers", [])
            ),
            key=lambda s: s["server_id"],
        ),
    }


APP_FIELDS = [
    "name", "type", "domain", "destinations", "allowed_idps", "auto_redirect_to_identity",
    "session_duration", "http_only_cookie_attribute", "cors_headers", "oauth_configuration",
]
RULE_FIELDS = ["decision", "include", "exclude", "require"]


def norm_policy(p):
    d = {"id": p["id"], "name": p["name"], "reusable": p.get("reusable", False)}
    if not d["reusable"]:  # reusable の条件は access/policies/ 側で持つ
        d.update({k: p.get(k, []) for k in RULE_FIELDS})
    return d


def norm_app(a):
    d = {"id": a["id"]}
    d.update({k: a[k] for k in APP_FIELDS if k in a and a[k] is not None})
    d["policies"] = [norm_policy(p) for p in sorted(a.get("policies", []), key=lambda p: p.get("precedence", 0))]
    return d


def norm_reusable(p):
    return {"id": p["id"], "name": p["name"], **{k: p.get(k, []) for k in RULE_FIELDS}}

# ---------------------------------------------------------------- 取得

def is_mcp_app(a):
    return a.get("type") in ("mcp", "mcp_portal")


def fetch():
    apps = [a for a in cf("zero-trust", "access", "applications", "list") if is_mcp_app(a)]
    used = {p["id"] for a in apps for p in a.get("policies", []) if p.get("reusable")}
    return {
        "servers": {s["id"]: s for s in cf("mcp", "servers", "list")},
        "portals": {p["id"]: cf("mcp", "portals", "read", p["id"]) for p in cf("mcp", "portals", "list")},
        "apps": {a["id"]: a for a in apps},
        "policies": {p["id"]: p for p in cf("zero-trust", "access", "policies", "list") if p["id"] in used},
    }


def app_file_key(d):
    """server 用 app は server ID、portal 用 app は portal-<hostname の先頭ラベル>。"""
    for dest in d.get("destinations", []):
        if dest.get("mcp_server_id"):
            return dest["mcp_server_id"]
    return "portal-" + (d.get("domain") or d["name"]).split(".")[0]


KINDS = {
    # kind: (宣言ディレクトリ, 正規化, ファイル名を決める関数)
    "servers": ("servers", norm_server, lambda d: d["id"]),
    "portals": ("portals", norm_portal, lambda d: d["id"]),
    "apps": ("access/apps", norm_app, app_file_key),
    "policies": ("access/policies", norm_reusable, lambda d: d["name"]),
}


def slug(s):
    out = "".join(c.lower() if c.isalnum() else "-" for c in s).strip("-")
    return "-".join(p for p in out.split("-") if p) or "app"


def load_declared():
    declared = {}
    for kind, (sub, _, _) in KINDS.items():
        declared[kind] = {}
        for f in sorted((HERE / sub).glob("*.json")):
            d = json.loads(f.read_text())
            d.pop("_comment", None)
            extra = {k: d.pop(k) for k in ("credential_env",) if k in d}
            declared[kind][d["id"]] = (f, d, extra)
    return declared

# ---------------------------------------------------------------- 差分

def diff_fields(cur, want):
    keys = [k for k in want if k != "id"] + [k for k in cur if k not in want and k != "id"]
    return [k for k in keys if cur.get(k) != want.get(k)]


def show(label, cur, want, fields):
    lines = [f"{label}:"]
    for k in fields:
        lines.append(f"  {k}:\n    current: {json.dumps(cur.get(k), ensure_ascii=False)}\n    desired: {json.dumps(want.get(k), ensure_ascii=False)}")
    return "\n".join(lines)


SERVER_FIXED = {"hostname", "auth_type", "oauth_manual"}  # update で変えられない


def compute(state, declared, table):
    """(表示行, 適用できる差分のリスト, 適用できない差分のリスト) を返す。"""
    out, actionable, manual = [], [], []
    for kind, (_, norm, _) in KINDS.items():
        cur_all = {rid: norm(obj) for rid, obj in state[kind].items()}
        for rid, (path, want, _) in declared[kind].items():
            want_s = substitute(want, table)
            label = f"{kind}/{path.stem}"
            if rid not in cur_all:
                out.append(f"{label}: Cloudflare に無い（作成は手動。手順は dev-env の mcp-portal を参照）")
                if kind == "servers" and want.get("auth_type") == "oauth":
                    out.append(f"  {OAUTH_NOTE}")
                manual.append((kind, rid, None))
                continue
            cur = cur_all[rid]
            fields = diff_fields(cur, want_s)
            if not fields:
                continue
            out.append(show(label, mask(cur, table), want, fields))
            fixed = set()
            if kind == "servers":
                fixed = SERVER_FIXED & set(fields)
            elif kind == "policies":
                fixed = set(fields)
            elif kind == "apps":
                fixed = {f for f in fields if f == "policies" and policy_rules_differ(cur, want_s)}
            if fixed:
                out.append(f"  ↑ {', '.join(sorted(fixed))} は apply で変えない（作り直すか、ダッシュボード・cf で直接直す）")
                manual.append((kind, rid, fixed))
            if set(fields) - fixed:
                actionable.append((kind, rid))
        for rid in sorted(set(cur_all) - set(declared[kind])):
            out.append(f"{kind}/{slug(KINDS[kind][2](cur_all[rid]))}（{rid}）: 宣言に無い（`--import` で取り込むか、不要なら手動で消す）")
            manual.append((kind, rid, None))
    return out, actionable, manual


def policy_rules_differ(cur, want):
    strip = lambda ps: [{k: v for k, v in p.items() if k in RULE_FIELDS} for p in ps]
    ids = lambda ps: [p["id"] for p in ps]
    return ids(cur["policies"]) == ids(want["policies"]) and strip(cur["policies"]) != strip(want["policies"])

# ---------------------------------------------------------------- 適用

def tool_list(ov):
    return [{"name": n, **({"enabled": True} | o)} for n, o in ov.items()]


def update_server(want, extra, rotate):
    body = {
        "name": want["name"],
        "description": want.get("description") or "",
        "secure_web_gateway": want["secure_web_gateway"],
        "is_shared_oauth_callback_enabled": want["is_shared_oauth_callback_enabled"],
        "updated_tools": tool_list(want["tool_overrides"]),
        "updated_prompts": tool_list(want["prompt_overrides"]),
    }
    if rotate:
        env = extra.get("credential_env")
        if not env:
            sys.exit(f"servers/{want['id']}: credential_env が宣言に無いので credential を差し替えられない")
        value = os.environ.get(env)
        if not value:
            sys.exit(f"servers/{want['id']}: 環境変数 {env} が無い（mise exec -- で実行する）")
        body["auth_credentials"] = value
    cf("mcp", "servers", "update", want["id"], body=body)


def update_portal(want):
    body = {
        "name": want["name"],
        "description": want.get("description") or "",
        "hostname": want["hostname"],
        "secure_web_gateway": want["secure_web_gateway"],
        "code_mode": want["code_mode"],
        "servers": [
            {
                "server_id": s["server_id"],
                "on_behalf": s["on_behalf"],
                "default_disabled": s["default_disabled"],
                "updated_tools": tool_list(s["tool_overrides"]),
                "updated_prompts": tool_list(s["prompt_overrides"]),
            }
            for s in want["servers"]
        ],
    }
    cf("mcp", "portals", "update", want["id"], body=body)


READONLY_APP = {"id", "uid", "aud", "created_at", "updated_at", "policies"}


def update_app(cur_raw, want):
    """Access app の PUT は全体置換なので、現状の全項目に宣言の項目を重ねて送る。"""
    body = {k: v for k, v in cur_raw.items() if k not in READONLY_APP}
    body.update({k: want[k] for k in APP_FIELDS if k in want})
    body["policies"] = [{"id": p["id"], "precedence": i + 1} for i, p in enumerate(want["policies"])]
    cf("zero-trust", "access", "applications", "update", want["id"], body=body)


def apply(state, declared, actionable, rotate):
    for kind, rid in actionable:
        _, want, extra = declared[kind][rid]
        if kind == "servers":
            update_server(want, extra, rid in rotate)
        elif kind == "portals":
            update_portal(want)
        elif kind == "apps":
            update_app(state["apps"][rid], want)
        print(f"{kind}/{declared[kind][rid][0].stem}: 更新した")
    for rid in rotate:
        if ("servers", rid) not in actionable:
            _, want, extra = declared["servers"][rid]
            update_server(want, extra, True)
            print(f"servers/{rid}: credential を差し替えた")

# ---------------------------------------------------------------- import

def do_import(state, table):
    existing = load_declared()
    for kind, (sub, norm, key) in KINDS.items():
        (HERE / sub).mkdir(parents=True, exist_ok=True)
        for rid, obj in state[kind].items():
            d = mask(norm(obj), table)
            prev = existing[kind].get(rid)
            if prev:
                path, _, extra = prev
                comment = json.loads(path.read_text()).get("_comment")
            else:
                path, extra, comment = HERE / sub / f"{slug(key(d))}.json", {}, None
            out = ({"_comment": comment} if comment else {}) | d | extra
            path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n")
            print(f"wrote {path.relative_to(HERE)}")

# ---------------------------------------------------------------- main

def status_notes(state):
    notes = []
    for s in state["servers"].values():
        if s.get("status") != "ready":
            notes.append(f"  servers/{s['id']}: status={s.get('status')} {s.get('error') or ''}".rstrip())
    return notes


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--apply", action="store_true", help="差分のある resource を更新する")
    p.add_argument("--rotate-credentials", nargs="+", default=[], metavar="SERVER_ID",
                   help="credential_env の値でその server の credential を送り直す（--apply と併用）")
    p.add_argument("--import", dest="do_import", action="store_true", help="現状を宣言ファイルへ書き出す")
    args = p.parse_args()
    if args.rotate_credentials and not args.apply:
        sys.exit("--rotate-credentials は --apply と一緒に使う")

    table = whoami()
    state = fetch()
    if args.do_import:
        do_import(state, table)
        return

    declared = load_declared()
    notes = status_notes(state)
    if notes:
        print("server の同期状態（宣言の比較対象外）:\n" + "\n".join(notes))

    out, actionable, manual = compute(state, declared, table)
    if not out and not args.rotate_credentials:
        print("宣言どおり（差分なし）")
        return
    print("\n".join(out))
    if not args.apply:
        sys.exit(1)

    apply(state, declared, actionable, set(args.rotate_credentials))
    state = fetch()
    out, actionable, manual2 = compute(state, declared, table)
    if actionable:
        print("更新後も差分が残った:\n" + "\n".join(out))
        sys.exit(1)
    if manual2:
        print("apply で直せない差分が残っている（上の ↑ の項目）")
        sys.exit(1)
    print("宣言どおりになった")


if __name__ == "__main__":
    main()
