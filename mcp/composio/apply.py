#!/usr/bin/env python3
"""Composio tool router session を sessions/<name>.json の宣言に合わせる。

  mise exec -- python3 mcp/composio/apply.py marketing          # 差分を表示（変更しない）
  mise exec -- python3 mcp/composio/apply.py marketing --apply  # PATCH して再確認

key は環境変数 COMPOSIO_API_KEY（global mise の setup 用 key）を読む。
宣言に無い設定（search・multi_execute・workbench・manage_connections）は常に無効で送る。
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

API = "https://backend.composio.dev/api/v3.1/tool_router/session"
HERE = Path(__file__).resolve().parent


def request(method, session_id, body=None):
    key = os.environ.get("COMPOSIO_API_KEY")
    if not key:
        sys.exit("COMPOSIO_API_KEY が無い（mise exec -- で実行する）")
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        f"{API}/{session_id}",
        data=data,
        method=method,
        headers={"x-api-key": key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        sys.exit(f"{method} {e.code}: {e.read().decode(errors='replace')}")


def desired_body(spec):
    toolkits = spec["toolkits"]
    return {
        "toolkits": {"enable": sorted(toolkits)},
        "auth_configs": {k: v["auth_config"] for k, v in toolkits.items() if v.get("auth_config")},
        "tools": {k: {"enable": sorted(v["tools"])} for k, v in toolkits.items()},
        "search": {"enable": False},
        "execute": {"enable_multi_execute": False},
        "workbench": {"enable": False},
        "manage_connections": {"enable": False},
    }


def pick(obj, *keys):
    """GET の応答は enable/enabled の揺れがあるので両方を見る。"""
    for k in keys:
        if isinstance(obj, dict) and k in obj:
            return obj[k]
    return None


def current_state(session):
    cfg = session.get("config", session)
    toolkits = pick(pick(cfg, "toolkits") or {}, "enabled", "enable") or []
    tools_cfg = pick(cfg, "tools") or {}
    tools = {k: sorted(pick(v, "enabled", "enable") or []) for k, v in tools_cfg.items()}
    flags = {
        "search": pick(pick(cfg, "search") or {}, "enabled", "enable"),
        "multi_execute": pick(pick(cfg, "execute") or {}, "enable_multi_execute"),
        "workbench": pick(pick(cfg, "workbench") or {}, "enabled", "enable"),
        "manage_connections": pick(pick(cfg, "manage_connections") or {}, "enabled", "enable"),
    }
    auth_configs = pick(cfg, "auth_configs") or {}
    return {"toolkits": sorted(toolkits), "tools": tools, "auth_configs": dict(sorted(auth_configs.items())), "flags": flags}


def desired_state(spec):
    return {
        "toolkits": sorted(spec["toolkits"]),
        "tools": {k: sorted(v["tools"]) for k, v in spec["toolkits"].items()},
        "auth_configs": dict(sorted((k, v["auth_config"]) for k, v in spec["toolkits"].items() if v.get("auth_config"))),
        "flags": {"search": False, "multi_execute": False, "workbench": False, "manage_connections": False},
    }


def diff(cur, want):
    lines = []
    for key in ("toolkits", "tools", "auth_configs", "flags"):
        if cur[key] != want[key]:
            lines.append(f"{key}:\n  current: {json.dumps(cur[key], ensure_ascii=False)}\n  desired: {json.dumps(want[key], ensure_ascii=False)}")
    return lines


def main():
    p = argparse.ArgumentParser()
    p.add_argument("name", help="sessions/<name>.json の name")
    p.add_argument("--apply", action="store_true", help="差分があれば PATCH する")
    args = p.parse_args()

    spec = json.loads((HERE / "sessions" / f"{args.name}.json").read_text())
    sid = spec["session_id"]
    want = desired_state(spec)

    d = diff(current_state(request("GET", sid)), want)
    if not d:
        print(f"{args.name}: 宣言どおり")
        return
    print("\n".join(d))
    if not args.apply:
        sys.exit(1)

    request("PATCH", sid, desired_body(spec))
    d = diff(current_state(request("GET", sid)), want)
    if d:
        print("PATCH 後も差分が残った:\n" + "\n".join(d))
        sys.exit(1)
    print(f"{args.name}: 適用した。portal 側は `cf mcp servers sync composio` で tool を再同期する")


if __name__ == "__main__":
    main()
