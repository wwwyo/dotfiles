#!/usr/bin/env bash
# pr_triage.py の判定ロジックの検証（path 3分類・dispatch routing・
# hard gate・上限・state/lock）と、fixture CLI による Orca のエラー処理・
# dispatch 回復の検証。実際の gh / orca サービスへは接続しない。
set -euo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PT="$repo_dir/.agents/skills/pr-auto-merge/tools/pr_triage.py"
python3 "$repo_dir/.agents/skills/pr-auto-merge/tools/pr_triage_orca.test.py"
TEST_ROOT=$(mktemp -d)
trap 'rm -rf "$TEST_ROOT"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

# HOME を差し替えると mise shim 経由の python3 が real config を untrusted
# 扱いするので、元の config path を明示して shim を通す
export MISE_TRUSTED_CONFIG_PATHS="$HOME/.config/mise/config.toml:$HOME/.config/mise/conf.d:$repo_dir/mise.toml:$repo_dir/mise.local.toml"
export HOME="$TEST_ROOT/home"
mkdir -p "$HOME"
export PR_WATCH_STATE_DIR="$TEST_ROOT/state"
export PR_WATCH_ME_REPO="$TEST_ROOT/me"

# --- CLI smoke: schema / lock ---
out=$(python3 "$PT" schema)
printf '%s' "$out" | grep -q '"gate"' || fail "schema failed: $out"
out=$(python3 "$PT" lock acquire)
printf '%s' "$out" | grep -q '"acquired": true' || fail "lock acquire: $out"
out=$(python3 "$PT" lock acquire)
printf '%s' "$out" | grep -q '"acquired": false' || fail "re-acquire: $out"
python3 "$PT" lock release >/dev/null

python3 - "$PT" <<'EOF'
import importlib.util, json, sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("pt", sys.argv[1])
pt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pt)

def view(**kw):
    v = {"state": "OPEN", "mergeable": "MERGEABLE", "reviewDecision": "",
         "headRefOid": "sha1", "headRefName": "wwwyo/x", "baseRefName": "main",
         "author": {"login": "wwwyo", "is_bot": False}, "isDraft": False,
         "statusCheckRollup": [], "reviews": [], "comments": [], "commits": []}
    v.update(kw)
    return v

def thread(resolved=False, login="pullfrog[bot]"):
    return {"isResolved": resolved, "isOutdated": False,
            "comments": {"nodes": [{"author": {"login": login},
                                    "body": "fix this", "path": "a.py",
                                    "line": 3, "createdAt": "2026-09-30T00:00:00Z"}]}}

def cr_review(when, login="pullfrog[bot]"):
    return {"state": "CHANGES_REQUESTED", "author": {"login": login},
            "body": "please fix", "submittedAt": when, "id": f"R{when}"}

def check(name, status="COMPLETED", conc="SUCCESS", kind="CheckRun"):
    if kind == "CheckRun":
        return {"__typename": "CheckRun", "name": name, "status": status,
                "conclusion": conc, "isRequired": True}
    return {"__typename": "StatusContext", "context": name, "state": conc,
            "isRequired": True}

def facts(**kw):
    f = {"view": view(), "files": ["src/a.py", "tests/test_a.py"],
         "renamed_from": [], "threads": [], "required": [],
         "diff": ""}
    f.update(kw)
    return f

# ============================ classify_path ============================
c = pt.classify_path
# 常に hold
assert c(".github/CODEOWNERS") == "hold"        # workflows 以外の .github
assert c("AGENTS.md") == "hold" and c("docs/x/CLAUDE.md") == "hold"
assert c(".agents/skills/x/SKILL.md") == "hold"
assert c(".claude/skills/x") == "hold"          # symlink entry も agent 面
assert c(".env") == "hold" and c(".env.local") == "hold" and c("a/.envrc") == "hold"
assert c("LICENSE") == "hold" and c("LICENSE-MIT") == "hold"
assert c("LICENSES/foo.txt") == "hold"          # segment prefix
assert c("infra/main.tf") == "hold" and c("x.tfvars") == "hold"
assert c("api/schema/openapi.yaml") == "hold"
assert c("src/auth/login.ts") == "hold"         # security substring
assert c("billing/plan.rb") == "hold"
assert c("proto/v1/svc.proto") == "hold"
assert c("src/graphql/query.gql") == "hold"
assert c(".changeset/wild-donuts.md") == "hold" # release/publish 面
# 要判定
assert c("package.json") == "judge" and c("pnpm-lock.yaml") == "other"
assert c("mise.toml") == "judge" and c(".tool-versions") == "judge"
assert c("Dockerfile") == "judge" and c("docker-compose.yml") == "judge"
assert c("db/migrations/001.sql") == "judge" and c("schema.sql") == "judge"
assert c("flake.nix") == "judge" and c("nix/shell.nix") == "judge"
assert c("go.mod") == "judge" and c("Cargo.lock") == "other"
assert c("fly.toml") == "judge" and c("notebooks/x.ipynb") == "judge"
assert c("foo.wasm") == "judge"                 # 分類不能 → judge
assert c("assets/logo.svg") == "judge"          # 分類不能 → judge
# それ以外
assert c("src/foo.ts") == "other" and c("pkg/bar.go") == "other"
assert c("tests/test_foo.sh") == "other" and c("docs/guide.md") == "other"
assert c("wiki/page.md") == "other"
assert c("wiki/AGENTS.md") == "hold"
assert c("home/dot_zshrc") == "other" and c("home/Brewfile") == "other"
assert c("src/util.test.ts") == "other"
assert c("config/app.yaml") == "other"          # .github 外の yaml
assert c("scripts/tool") == "judge"             # 拡張子なし basename → 分類不能
assert c(".zshrc") == "other"
assert c("api/src/index.test.ts") == "other"
assert c("apps/api/src/index.test.ts") == "other"
assert c("src/auth/login.test.ts") == "other"
assert c("src/payment/checkout.spec.ts") == "other"
assert c("routes/__tests__/test_route.py") == "other"
assert c("graphql/tests/test_query.py") == "other"
assert c("apps/api/src/contract/shared.ts") == "hold"
assert c("routes/index.ts") == "hold" and c("graphql/query.ts") == "hold"
assert c(".github/workflows/test_ci.py") == "judge"
assert c(".github/workflows/pullfrog.yml") == "judge" # github-actions 依存置き場
assert c(".github/workflows/deploy-auth-checks.yml") == "hold" # substring hold は維持
assert c(".github/workflows/x.lock.yml") == "hold"    # 生成物は常に hold
assert c(".github/workflows/sub/x.yml") == "hold"     # subdir は実行対象外 → hold
assert c(".github/workflows/auth.test.yml") == "hold" # test 名でも substring hold
assert not pt.is_actions_workflow(".github/workflows/sub/x.yml")
assert not pt.is_actions_workflow(".github/workflows/x.lock.yml")
assert c(".agents/hooks/tests/test_auth.py") == "hold"
assert c("tests/.env") == "hold" and c("tests/main.tf") == "hold"
assert c("tests/LICENSE") == "hold"
assert c("db/migrations/test_schema.sql") == "judge"
# `test_`/`_test.` は basename の convention — 途中に test_ を含む本番
# コードは test にしない（hold 免除の抜け道になる）
assert c("api/latest_token.py") == "hold"
assert c("api/contest_handler.py") == "hold"
assert c("src/auth/latest_token.py") == "hold"
assert c("src/auth/contest_handler.py") == "hold"
assert c("src/test_utils.py") == "other" and c("src/x_test.py") == "other"
assert c("src/v1.test/handler.py") == "other"   # dir 名の .test は test でない

# ============================ classify_pr ============================
meta_w = {"author": {"login": "wwwyo", "is_bot": False}}
meta_bot = {"author": {"login": "dependabot[bot]", "is_bot": True}}

# hold path が1つ → 全体 hold（judge にも回さない）
r = pt.classify_pr(["src/a.py", ".env"], meta_w, "")
assert r["lane"] == "hold" and not r["bot_dep_only"]
# .github/workflows/ は judge 側。bot の workflow 更新は whitelist 枠
r = pt.classify_pr([".github/workflows/pullfrog.yml"], meta_bot, "")
assert r["lane"] == "judge" and r["bot_dep_only"]
r = pt.classify_pr([".github/workflows/x.yml", "package.json"],
                   meta_bot, "")
assert r["lane"] == "judge" and r["bot_dep_only"]
# workflow + 依存以外 → whitelist 対象外
r = pt.classify_pr([".github/workflows/x.yml", "docs/x.md"],
                   meta_bot, "")
assert r["lane"] == "judge" and not r["bot_dep_only"]
# 生成物の lock workflow は whitelist に入らない（hold）
r = pt.classify_pr([".github/workflows/x.lock.yml"], meta_bot, "")
assert r["lane"] == "hold" and not r["bot_dep_only"]
# rename 元の hold path（previous_filename）も分類対象 — lock.yml → yml
# rename は renamed_from に旧名が入り hold 側で止まる
r = pt.classify_pr([".github/workflows/build.yml"], meta_bot, "",
                   renamed_from=[".github/workflows/build.lock.yml"])
assert r["lane"] == "hold" and not r["bot_dep_only"]
assert ".github/workflows/build.lock.yml" in r["classes"]

# 既存テストの実行でも QA できるため、test ファイルの追加だけでは判定しない
r = pt.classify_pr(["src/a.py"], meta_w, "")
assert r["lane"] == "lane"
# test → prod の rename も実施した QA を judge が確認する
r = pt.classify_pr(["src/a.py"], meta_w, "",
                   renamed_from=["tests/test_a.py"])
assert r["lane"] == "lane"
# 逆方向（prod → test の rename）は prod が残らない → lane
r = pt.classify_pr(["tests/test_a.py"], meta_w, "",
                   renamed_from=["src/a.py"])
assert r["lane"] == "lane"
# test 付きなら lane
r = pt.classify_pr(["src/a.py", "tests/test_a.py"], meta_w, "")
assert r["lane"] == "lane"
# docs/config のみは production code 扱いしない → lane
r = pt.classify_pr(["docs/x.md", "config/y.yaml"], meta_w, "")
assert r["lane"] == "lane"
# wiki の通常ページ・index・log と rename も docs と同じ lane 候補
r = pt.classify_pr(["wiki/tech/page.md", "wiki/index.md", "wiki/log.md"],
                   meta_w, "", renamed_from=["wiki/tech/old.md"])
assert r["lane"] == "lane"
r = pt.classify_pr(["wiki/tech/page.md", "wiki/AGENTS.md"], meta_w, "")
assert r["lane"] == "hold"

# judge path → judge
r = pt.classify_pr(["package.json", "src/a.py", "tests/test_a.py"],
                   meta_w, "")
assert r["lane"] == "judge" and not r["bot_dep_only"]
# bot の依存更新のみ → bot_dep_only
r = pt.classify_pr(["package.json", "package-lock.json"], meta_bot, "")
assert r["lane"] == "judge" and r["bot_dep_only"]
# bot でも code を含む → bot_dep_only False
r = pt.classify_pr(["package.json", "src/a.py"], meta_bot, "")
assert r["lane"] == "judge" and not r["bot_dep_only"]
r = pt.classify_pr(["package.json", "src/a.py", "tests/a.test.py"],
                   meta_bot, "")
assert r["lane"] == "judge" and not r["bot_dep_only"]

# breaking シグナル: 「それ以外」も judge に引き上げ
m = dict(meta_w); m.update({"title": "feat!: drop old api", "body": "",
                            "commits": []})
r = pt.classify_pr(["src/a.py", "tests/test_a.py"], m, "")
assert r["lane"] == "judge"
m = dict(meta_w); m.update({"title": "feat: x", "body": "",
                            "commits": [{"messageHeadline": "feat: x",
                                         "messageBody": "BREAKING CHANGE: y"}]})
r = pt.classify_pr(["src/a.py", "tests/test_a.py"], m, "")
assert r["lane"] == "judge"
# version major bump
diff = '-  "version": "2.1.0"\n+  "version": "3.0.0"\n'
r = pt.classify_pr(["src/a.py", "tests/test_a.py"], meta_w, diff)
assert r["lane"] == "judge"
diff = '-  "version": "2.1.0"\n+  "version": "2.2.0"\n'
r = pt.classify_pr(["src/a.py", "tests/test_a.py"], meta_w, diff)
assert r["lane"] == "lane"
r = pt.classify_pr(["api/src/index.test.ts"], meta_w, "")
assert r["lane"] == "lane"
r = pt.classify_pr(["apps/api/src/contract/shared.ts",
                    "apps/api/src/index.test.ts"], meta_w, "")
assert r["lane"] == "hold" and \
    r["reasons"] == ["always-hold path: apps/api/src/contract/shared.ts"]

# ============================ unaddressed ============================
items = pt.unaddressed_items(view(), [])
assert items == []
items = pt.unaddressed_items(view(), [thread(resolved=False)])
assert len(items) == 1 and items[0]["kind"] == "thread"
items = pt.unaddressed_items(view(), [thread(resolved=True)])
assert items == []
# CR review: author 活動が無ければ unaddressed
v = view(reviews=[cr_review("2026-10-01T00:00:00Z")])
assert any(i["kind"] == "changes_requested"
           for i in pt.unaddressed_items(v, []))
# author が後に push/comment していれば解消済み扱い
v = view(reviews=[cr_review("2026-10-01T00:00:00Z")],
         commits=[{"committedDate": "2026-10-02T00:00:00Z"}])
assert pt.unaddressed_items(v, []) == []
v = view(reviews=[cr_review("2026-10-01T00:00:00Z")],
         comments=[{"author": {"login": "wwwyo"},
                    "createdAt": "2026-10-02T00:00:00Z"}])
assert pt.unaddressed_items(v, []) == []
# 他人の comment では解消しない
v = view(reviews=[cr_review("2026-10-01T00:00:00Z")],
         comments=[{"author": {"login": "pullfrog[bot]"},
                    "createdAt": "2026-10-02T00:00:00Z"}])
assert len(pt.unaddressed_items(v, [])) == 1
# REST reviews は id が integer — sig 生成が TypeError で死なないこと
v = view(reviews=[{"state": "CHANGES_REQUESTED", "id": 12345,
                   "author": {"login": "pullfrog[bot]"}, "body": "b",
                   "submittedAt": "2026-10-01T00:00:00Z"}])
items = pt.unaddressed_items(v, [])
assert items and items[0]["sig"] == "r:12345"

# ============================ checks / gate ============================
v = view(statusCheckRollup=[check("ci"), check("pullfrog-approval")])
checks = pt.check_rollup(v)
ok, st = pt.pullfrog_approval(checks)
assert ok and st == "SUCCESS"
v = view(statusCheckRollup=[check("ci"),
                            check("pullfrog-approval", conc="FAILURE")])
ok, st = pt.pullfrog_approval(pt.check_rollup(v))
assert not ok
v = view(statusCheckRollup=[check("ci", status="IN_PROGRESS",
                                  conc=None)])
st = pt.required_check_state(pt.check_rollup(v), ["ci"])
assert st["pending"] == ["ci"] and not st["failing"]
st = pt.required_check_state(pt.check_rollup(v), ["ci", "lint"])
assert "lint" in st["missing"]

# hard_gate: 判定済み + required 全 green + approval
v = view(statusCheckRollup=[check("ci"), check("pullfrog-approval")])
f = facts(view=v, required=["ci"])
ok, reasons = pt.hard_gate(f, judge={"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v)}, via="lane")
assert ok, reasons

# unaddressed thread → block
f = facts(view=v, required=["ci"], threads=[thread()])
ok, reasons = pt.hard_gate(f, via="lane")
assert not ok and any("unaddressed" in r for r in reasons)

# CHANGES_REQUESTED → block（thread が無くても）
v2 = view(reviewDecision="CHANGES_REQUESTED",
          statusCheckRollup=[check("ci"), check("pullfrog-approval")])
f = facts(view=v2, required=["ci"])
ok, reasons = pt.hard_gate(f, via="lane")
assert not ok and any("CHANGES_REQUESTED" in r for r in reasons)

# required failing / pending → block
v2 = view(statusCheckRollup=[check("ci", conc="FAILURE"),
                             check("pullfrog-approval")])
ok, _ = pt.hard_gate(facts(view=v2, required=["ci"]), via="lane")
assert not ok
v2 = view(statusCheckRollup=[check("ci", status="IN_PROGRESS", conc=None),
                             check("pullfrog-approval")])
ok, reasons = pt.hard_gate(facts(view=v2, required=["ci"]), via="lane")
assert not ok and any("pending" in r for r in reasons)

# mergeable でない → block
v2 = view(mergeable="CONFLICTING",
          statusCheckRollup=[check("ci"), check("pullfrog-approval")])
ok, _ = pt.hard_gate(facts(view=v2, required=["ci"]), via="lane")
assert not ok

# approval 無し → block（bot_dep+judge-ok 以外）
v2 = view(statusCheckRollup=[check("ci")])
f = facts(view=v2, required=["ci"])
ok, reasons = pt.hard_gate(f, via="lane")
assert not ok and any("pullfrog-approval" in r for r in reasons)

# hold path → judge ok があっても block
v = view(statusCheckRollup=[check("ci"), check("pullfrog-approval")])
f = facts(view=v, files=[".env"], required=["ci"])
ok, reasons = pt.hard_gate(f, judge={"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v)},
                           via="lane")
assert not ok and any("lane=hold" in r for r in reasons)
# workflow は judge ok + approval で merge 可（非 bot は approval 必須）
f = facts(view=v, files=[".github/workflows/pullfrog.yml"], required=["ci"])
ok, reasons = pt.hard_gate(f, judge={"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v)},
                           via="lane")
assert ok, reasons
# bot の workflow 更新は approval 免除（judge ok が必須）
vb = view(author={"login": "dependabot[bot]", "is_bot": True},
          statusCheckRollup=[check("ci")])
f = facts(view=vb, files=[".github/workflows/pullfrog.yml"], required=["ci"])
ok, reasons = pt.hard_gate(f, judge={"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(vb)},
                           via="lane")
assert ok, reasons
ok, reasons = pt.hard_gate(f, via="lane")
assert not ok and any("judge" in r for r in reasons)

v = view(statusCheckRollup=[check("ci"), check("pullfrog-approval")])
f = facts(view=v, files=["api/src/index.test.ts"], required=["ci"])
ok, reasons = pt.hard_gate(f, judge={"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v)}, via="lane")
assert ok, reasons
f = facts(view=v, files=["apps/api/src/contract/shared.ts",
                         "apps/api/src/index.test.ts"], required=["ci"])
ok, reasons = pt.hard_gate(f, judge={"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v)},
                           via="lane")
assert not ok and any("shared.ts" in r for r in reasons) and \
    not any("index.test.ts" in r for r in reasons)

# judge path: verdict が head に紐付いていない → block
v = view(statusCheckRollup=[check("ci"), check("pullfrog-approval")])
f = facts(view=v, files=["package.json"], required=["ci"])
ok, reasons = pt.hard_gate(f, judge={"sha": "other", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v)},
                           via="lane")
assert not ok and any("judge" in r for r in reasons)
# verdict ok@head + approval → pass
ok, reasons = pt.hard_gate(f, judge={"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v)},
                           via="lane")
assert ok, reasons
# verdict ng → block
ok, _ = pt.hard_gate(f, judge={"sha": "sha1", "verdict": "ng", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v)}, via="lane")
assert not ok

# bot_dep whitelist: judge-ok@head なら approval 無しで pass
vbot = view(author={"login": "dependabot[bot]", "is_bot": True},
            statusCheckRollup=[check("ci")])
f = facts(view=vbot, files=["package.json", "package-lock.json"],
          required=["ci"])
ok, reasons = pt.hard_gate(f, judge={"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(vbot)},
                           via="lane")
assert ok, reasons
# bot_dep でも judge 無しなら block（approval も無い）
ok, _ = pt.hard_gate(f, via="lane")
assert not ok

# 判定後に head が動いた PR は merge されない
ok, reasons = pt.hard_gate(facts(view=v), expect_sha="other")
assert not ok and any("head moved" in r for r in reasons)
# 削除された経路を使って approval / path の検証を迂回できない
v2 = view(statusCheckRollup=[check("ci")])
ok, reasons = pt.hard_gate(facts(view=v2, files=[".github/workflows/x"],
                                 required=["ci"]),
                           via="deep", expect_sha="sha1")
assert not ok and "unsupported merge route" in reasons[0], reasons

# ============================ dispatch routing ============================
wt = lambda **kw: dict({"worktreeId": "r::w1", "repo": "me",
                        "branch": "refs/heads/wwwyo/x", "path": "/p",
                        "liveTerminalCount": 0, "status": "inactive",
                        "agents": [], "linkedPR": None}, **kw)
pr = {"number": 7, "headRefName": "wwwyo/x",
      "author": {"login": "wwwyo", "is_bot": False}}
pr_other = dict(pr, author={"login": "someone"})
R = "wwwyo/me"
route = lambda ws, ts, p=pr: pt.route_dispatch(ws, ts, R, p)

# linkedPR 優先 → send
w = wt(linkedPR={"number": 7, "state": "open"})
w = dict(w, branch="refs/heads/other-branch")
terms = {"r::w1": [{"handle": "wt_t1", "agentIdentity": "pi",
                  "writable": True, "connected": True}]}
r = route([w], terms)
assert r["route"] == "send" and r["handle"] == "wt_t1"

# branch fallback → send
w = wt()
r = route([w], terms)
assert r["route"] == "send" and r["reason"].startswith("matched via branch")

# agent working → defer
w = wt(status="working")
r = route([w], {"r::w1": []})
assert r["route"] == "defer"
w = wt(agents=[{"state": "working", "agent": "pi"}])
r = route([w], {"r::w1": []})
assert r["route"] == "defer"

# Retired idle sessions receive no new work; an active legacy turn remains deferred.
legacy_terms = {"r::w1": [{"handle": "legacy", "agentIdentity": "devin",
                            "writable": True, "connected": True}]}
assert route([wt()], legacy_terms)["route"] == "revive"
assert route([wt(status="working")], legacy_terms)["route"] == "defer"

# agent 無し → revive
w = wt()
r = route([w], {"r::w1": []})
assert r["route"] == "revive"

# session 無し + eligible author → spawn
r = route([], {})
assert r["route"] == "spawn"

# session 無し + 非 eligible author → none
r = route([], {}, pr_other)
assert r["route"] == "none"
# session 有り + 非 eligible author でも none（dispatch しない）
w = wt()
r = route([w], terms, pr_other)
assert r["route"] == "none"

# linkedPR が merged → branch fallback に落ちる
w = wt(linkedPR={"number": 7, "state": "merged"})
r = route([w], terms)
assert r["route"] == "send" and "branch" in r["reason"]

# 別 repo の同 branch worktree は dispatch 対象にしない
w2 = wt(repo="dotfiles")
r = route([w2], terms)
assert r["route"] == "spawn"

# linkedPR が別 PR を指していても head branch を checkout 済みなら
# branch fallback でその worktree に送る（spawn はしない）
w = wt(linkedPR={"number": 9, "state": "open"})  # PR9 用の worktree
r = route([w], {"r::w1": []})                    # PR7 の head は w と同じ
assert r["route"] == "revive" and "branch" in r["reason"]

# ============================ dispatch caps ============================
st = {}
ds = pt.dispatch_state(st, "wwwyo/me", 7)
a, why, esc = pt.dispatch_allows(ds, "sha1")
assert a and not esc
# 同一 head 3回まで
for _ in range(3):
    pt.mark_dispatch_sent(st, "wwwyo/me", 7, "sha1", "s1")
ds = pt.dispatch_state(st, "wwwyo/me", 7)
a, why, esc = pt.dispatch_allows(ds, "sha1")
assert not a and esc
# 新しい sig でも head 同じなら cap に達する
ds["dispatches"][-1]["sig"] = "s2"
a, why, esc = pt.dispatch_allows(ds, "sha1")
assert not a and esc

# rounds: 異なる head 3つで打ち切り
st2 = {}
for h in ("h1", "h2", "h3"):
    pt.mark_dispatch_sent(st2, "wwwyo/me", 7, h, "s")
ds = pt.dispatch_state(st2, "wwwyo/me", 7)
a, why, esc = pt.dispatch_allows(ds, "h4")
assert not a and esc and "rounds" in why
# 既に dispatch した head への再送は rounds 消費しない
a, why, esc = pt.dispatch_allows(ds, "h1")
assert a  # 同 head 1回目なので許可（cap 2回目以降の余地）

# already_sent dedup
pt.mark_dispatch_sent(st2, "wwwyo/me", 7, "hX", "sigA")
ds = pt.dispatch_state(st2, "wwwyo/me", 7)
assert pt.dispatch_already_sent(ds, "hX", "sigA")
assert not pt.dispatch_already_sent(ds, "hX", "sigB")

# escalated flag → 一切送信しない
ds = pt.dispatch_state(st2, "wwwyo/me", 7)
ds["escalated"] = True
a, why, esc = pt.dispatch_allows(ds, "hZ")
assert not a and not esc

# ============================ sweep candidates ============================
st = {"merged": {"wwwyo/me#7": {"sha": "abc", "head_ref": "wwwyo/x"}}}
# live terminal 有り → 対象外
w = wt(liveTerminalCount=1, status="active")
assert pt.sweep_candidates(st, [w]) == []
# linkedPR merged + 全条件 → 候補
w = wt(linkedPR={"number": 7, "state": "merged"})
c = pt.sweep_candidates(st, [w])
assert len(c) == 1 and c[0]["worktree"] == "r::w1"
# branch 一致（linkedPR 無し）でも候補
w = wt()
c = pt.sweep_candidates(st, [w])
assert len(c) == 1
# 完了 agent は候補、作業中 agent は対象外
w = wt(agents=[{"state": "done", "agent": "pi"}])
assert len(pt.sweep_candidates(st, [w])) == 1
w = wt(agents=[{"state": "working", "agent": "pi"}])
assert pt.sweep_candidates(st, [w]) == []
# routine が merge していない PR の worktree → 対象外
# （linkedPR・branch とも merged PR7 と一致しない）
w = wt(linkedPR={"number": 8, "state": "merged"},
       branch="refs/heads/wwwyo/other")
assert pt.sweep_candidates(st, [w]) == []
# main worktree は消さない
w = wt(isMainWorktree=True, linkedPR={"number": 7, "state": "merged"})
assert pt.sweep_candidates(st, [w]) == []
# 永続的 skip が上限に達した候補は諦める（毎 tick session 起動を防ぐ）
st_x = {"merged": {"wwwyo/me#7": {"sha": "abc", "head_ref": "wwwyo/x",
                                   "sweep_skips": pt.SWEEP_MAX_TRIES}}}
w = wt(linkedPR={"number": 7, "state": "merged"})
assert pt.sweep_candidates(st_x, [w]) == []
st_x["merged"]["wwwyo/me#7"]["sweep_skips"] = pt.SWEEP_MAX_TRIES - 1
assert len(pt.sweep_candidates(st_x, [w])) == 1
# transient 判定 — ps との race のみ試行数に数えない。git timeout・
# dirty・rm 失敗は永続的で sweep_skips が進む
assert pt.sweep_skip_transient("worktree gone")
assert pt.sweep_skip_transient("terminal/agent live")
assert not pt.sweep_skip_transient("git -C /x status timed out")
assert not pt.sweep_skip_transient("dirty worktree")
assert not pt.sweep_skip_transient("orca worktree rm failed: x")

# ============================ state / compute_pr_decision ============================
st = {}
# unaddressed → dispatch action（linkedPR match + idle → send）
w = wt(linkedPR={"number": 7, "state": "open"})
f = facts(threads=[thread()])
# terms_cache に入れておかないと compute 内で本物の orca を呼びに行く
terms = {"r::w1": [{"handle": "wt_t1", "agentIdentity": "pi",
                  "writable": True, "connected": True}]}
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [w], terms, st)
acts = [a["type"] for a in e["actions"]]
assert acts == ["dispatch"] and e["actions"][0]["route"] == "send"

# 2回目（同 head+sig 既送）→ hold
pt.mark_dispatch_sent(st, "wwwyo/me", 7, f["view"]["headRefOid"],
                      pt.unaddressed_sig(
                          pt.unaddressed_items(f["view"], f["threads"])))
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [w], terms, st)
assert e["actions"][0]["type"] == "hold" and "already dispatched" in \
    e["actions"][0]["reason"]

# 全 green の通常 PR も QA・Blast Radius 判定を通る
v = view(statusCheckRollup=[check("ci"), check("pullfrog-approval")])
f = facts(view=v, required=["ci"])
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [], {}, {})
assert e["actions"][0]["type"] == "judge" and e["lane"] == "lane"

# wiki は一律 hold を外しても、current judge・approval・required CI を通る
f = facts(view=v, files=["wiki/tech/page.md", "wiki/index.md", "wiki/log.md"],
          required=["ci"])
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7}, f, [], {}, {})
assert e["actions"][0]["type"] == "judge" and not pt.hard_gate(f)[0]
j = {"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION,
     "context_hash": pt.pr_context_hash(v)}
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7}, f, [], {},
                           {"judge": {"wwwyo/me#7": j}})
assert e["actions"][0]["type"] == "merge" and pt.hard_gate(f, judge=j)[0]
for checks in [[check("ci")],
               [check("ci", conc="FAILURE"), check("pullfrog-approval")]]:
    changed_view = view(statusCheckRollup=checks)
    changed = facts(view=changed_view, files=f["files"], required=["ci"])
    changed_judge = dict(j, context_hash=pt.pr_context_hash(changed_view))
    e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                               changed, [], {},
                               {"judge": {"wwwyo/me#7": changed_judge}})
    assert e["actions"][0]["type"] == "hold"
    assert not pt.hard_gate(changed, judge=changed_judge)[0]

# 公開 CLI で保存した判定を plan と merge gate が使う。GitHub への書き込みは行わない。
import subprocess
for risk, qa, verdict, action in [
        ("高", "関連 E2E 成功", "ng", "hold"),
        ("中", "関連 API テスト成功", "ok", "merge"),
        ("中", "QA未実施", "ng", "hold"),
        ("低", "QA未実施: 文言のみ", "ok", "merge")]:
    candidate = view(body=f"## Blast Radius\n{risk}\n## QA\n{qa}",
                     statusCheckRollup=[check("ci"), check("pullfrog-approval")])
    run = subprocess.run([sys.executable, sys.argv[1], "judge-result",
                          "--repo", "wwwyo/me", "--number", "7", "--sha", "sha1",
                          "--context-hash", pt.pr_context_hash(candidate),
                          "--verdict", verdict, "--reason", f"{risk}: {qa}"],
                         capture_output=True, text=True, check=True)
    assert json.loads(run.stdout)["ok"]
    saved = pt.load_state()
    judged = saved["judge"]["wwwyo/me#7"]
    candidate_facts = facts(view=candidate, files=["src/a.py"], required=["ci"])
    decision = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                                      candidate_facts, [], {}, saved)
    assert decision["actions"][0]["type"] == action
    assert pt.hard_gate(candidate_facts, judge=judged)[0] == (action == "merge")
    # head が同じでも QA・base・CI の変更後は再判定する。
    for updated in [dict(candidate, body=candidate["body"] + "\n訂正"),
                    dict(candidate, baseRefName="release", baseRefOid="other-base"),
                    dict(candidate, statusCheckRollup=[check("ci", conc="FAILURE"),
                                                       check("pullfrog-approval")])]:
        changed = facts(view=updated, files=["src/a.py"], required=[])
        decision = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                                          changed, [], {}, saved)
        assert decision["actions"][0]["type"] == "judge"
        assert not pt.hard_gate(changed, judge=judged)[0]
pt.save_state({})

# judge path + verdict 無し → judge action
f = facts(view=v, files=["package.json"], required=["ci"])
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [], {}, {})
assert e["actions"][0]["type"] == "judge"
# verdict ok@head → merge action
st = {"judge": {"wwwyo/me#7": {"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v)}}}
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [], {}, st)
assert e["actions"][0]["type"] == "merge"
# verdict ng → hold
st = {"judge": {"wwwyo/me#7": {"sha": "sha1", "verdict": "ng", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v),
                               "reason": "x"}}}
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [], {}, st)
assert e["actions"][0]["type"] == "hold" and "judge ng" in \
    e["actions"][0]["reason"]

# 規約変更後は同一headでも旧ok/ngを再判定し、旧okでmergeしない
for verdict in ("ok", "ng"):
    old = {"sha": "sha1", "verdict": verdict,
           "policy_version": pt.JUDGE_POLICY_VERSION - 1, "reason": "old"}
    e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                              f, [], {}, {"judge": {"wwwyo/me#7": old}})
    assert e["actions"][0]["type"] == "judge"
    assert not pt.hard_gate(f, judge=old, via="lane")[0]

# approval 無し → hold
v2 = view(statusCheckRollup=[check("ci")])
f = facts(view=v2, required=["ci"])
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [], {}, {"judge": {"wwwyo/me#7": {"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v2)}}})
assert e["actions"][0]["type"] == "hold" and "pullfrog" in \
    e["actions"][0]["reason"]

# hold path → merge に到達しない
f = facts(view=v, files=[".env"], required=["ci"])
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [], {}, {})
assert e["actions"][0]["type"] == "hold" and "always-hold" in \
    e["actions"][0]["reason"]
# workflow は hold ではなく judge action が出る
f = facts(view=v, files=[".github/workflows/pullfrog.yml"], required=["ci"])
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [], {}, {})
assert e["actions"][0]["type"] == "judge", e["actions"]

f = facts(view=v, files=["api/src/index.test.ts"], required=["ci"])
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [], {}, {})
assert e["actions"][0]["type"] == "judge" and e["lane"] == "lane"
f = facts(view=v, files=["apps/api/src/contract/shared.ts",
                         "apps/api/src/index.test.ts"], required=["ci"])
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           f, [], {}, {})
assert e["actions"][0]["type"] == "hold" and \
    "shared.ts" in e["actions"][0]["reason"] and \
    "index.test.ts" not in e["actions"][0]["reason"]

from unittest import mock
from types import SimpleNamespace

# 競合は毎 tick の dispatch 対象。作業中は割り込まず、同じ障害は再送しない。
conflict = facts(view=view(mergeable="CONFLICTING", baseRefOid="base1"))
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           conflict, [w], terms, {})
assert e["actions"][0]["type"] == "dispatch"
st = {}
items = pt.dispatch_items("wwwyo/me", 7, conflict)
pt.mark_dispatch_sent(st, "wwwyo/me", 7, "sha1", pt.unaddressed_sig(items))
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           conflict, [w], terms, st)
assert e["actions"][0]["type"] == "hold"
conflict["view"]["baseRefOid"] = "base2"
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           conflict, [w], terms, st)
assert e["actions"][0]["type"] == "dispatch"
busy_w = dict(w, agents=[{"state": "working"}])
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                           conflict, [busy_w], terms, {})
assert e["actions"][0]["type"] == "hold", e

# 依存更新の CI 赤だけ修正依頼に回す。pending・通常 PR の赤・workflow 変更は除外。
bot = {"login": "dependabot[bot]", "is_bot": True}
dep = facts(view=view(author=bot, statusCheckRollup=[check("ci", conc="FAILURE")]),
            files=["package.json", "bun.lock"], required=["ci"])
e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7}, dep, [], {}, {})
assert e["actions"][0]["type"] == "dispatch" and e["actions"][0]["route"] == "spawn"
# required が未設定でも実際に失敗した CI を対象にする。
dep["required"] = []
assert pt.dispatch_items("wwwyo/me", 7, dep)[0]["kind"] == "dependency_ci"
dep["view"]["statusCheckRollup"] = [check("ci", status="IN_PROGRESS", conc="")]
assert not pt.dispatch_items("wwwyo/me", 7, dep)
dep["view"]["statusCheckRollup"] = [check("pullfrog-approval", conc="FAILURE")]
assert not pt.dispatch_items("wwwyo/me", 7, dep)
dep["view"]["statusCheckRollup"] = [check("ci", conc="FAILURE")]
dep["files"].append(".github/workflows/ci.yml")
assert not pt.dispatch_items("wwwyo/me", 7, dep)
dep["view"]["author"] = {"login": "wwwyo"}
assert not pt.dispatch_items("wwwyo/me", 7, dep)

# 同時に指摘と競合があっても1回の依頼にまとめ、修正範囲を伝える。
conflict["threads"] = [thread()]
items = pt.dispatch_items("wwwyo/me", 7, conflict)
assert {it["kind"] for it in items} == {"thread", "conflict"}
msg = pt.build_dispatch_message("wwwyo/me", conflict["view"], items)
assert "repair.md" in msg and "cooldown" in msg and "fix this" in msg

# plan 後に競合が解消された/PR が閉じたなら live 再検証で送信しない。
for fresh in [facts(), facts(view=view(state="CLOSED", mergeable="CONFLICTING"))]:
    with mock.patch.object(pt, "load_state", return_value={}), \
            mock.patch.object(pt, "pr_facts", return_value=fresh), \
            mock.patch.object(pt, "send_prompt") as send, \
            mock.patch.object(pt, "worktree_ps") as ps, \
            mock.patch.object(pt, "emit") as emit:
        pt._cmd_dispatch(SimpleNamespace(repo="wwwyo/me", number=7))
        send.assert_not_called()
        ps.assert_not_called()
        assert emit.call_args.args[0]["dispatched"] is False

# judge-input は判定材料に head の check 群を含める（fail の確認に使う）
with mock.patch.object(pt, "pr_view",
                       return_value=view(statusCheckRollup=[
                           check("ci", conc="FAILURE")])),         mock.patch.object(pt, "pr_files",
                          return_value=(["package.json"], [])),         mock.patch.object(pt, "pr_diff", return_value="d"),         mock.patch.object(pt, "emit") as emit:
    pt._cmd_judge_input(SimpleNamespace(repo="wwwyo/me", number=7))
    out = emit.call_args.args[0]
    assert out["checks"][0]["name"] == "ci" and         out["checks"][0]["conclusion"] == "FAILURE"

# policy version を跨いだ再判定でも repair whitelist の属性は保持する。
# 追従コードを含む head は bot_dep_only を満たさず、失効すると approval
# （bot PR には付かない）待ちで固定されるため
prev = {"sha": "sha1", "verdict": "repair", "reason": "x",
        "policy_version": pt.JUDGE_POLICY_VERSION - 1,
        "dependency_repair": True}
saved = {}
with mock.patch.object(pt, "load_state",
                       return_value={"judge": {"wwwyo/me#7": prev}}),         mock.patch.object(pt, "save_state",
                          side_effect=lambda s: saved.update(s)),         mock.patch.object(pt, "pr_facts",
                          side_effect=pt.ApiError("no gh in test")),         mock.patch.object(pt, "emit"):
    pt._cmd_judge_result(SimpleNamespace(repo="wwwyo/me", number=7,
                                         sha="sha1", verdict="ok",
                                         context_hash=pt.pr_context_hash(view()),
                                         reason="r"))
rec = saved["judge"]["wwwyo/me#7"]
assert rec["verdict"] == "ok" and rec["dependency_repair"] is True
assert rec["policy_version"] == pt.JUDGE_POLICY_VERSION
cls = pt.dependency_repair_classification(
    {"lane": "lane", "reasons": [], "classes": {}},
    view(author={"login": "dependabot[bot]", "is_bot": True}), rec)
assert cls["dependency_repair"] is True and cls["lane"] == "judge"

# action がなければ日が変わっても session を起こさず lock を解放する。
with mock.patch.object(pt, "list_open_prs", return_value=[]), \
        mock.patch.object(pt, "worktree_ps", return_value=[]), \
        mock.patch.object(pt, "_merge_events", return_value=set()), \
        mock.patch.object(pt, "save_state"), \
        mock.patch.object(pt, "_lock_release") as release, \
        mock.patch.object(pt, "emit") as emit:
    try:
        pt._gate(SimpleNamespace(), {}, "run1")
        raise AssertionError("empty tick did not skip")
    except SystemExit as e:
        assert e.code == 1
    release.assert_called_once_with("run1")
    assert emit.call_args.args[0]["run"] is False
assert "deep" not in json.loads(pt.PLAN_FILE.read_text())
assert "deep-done" not in pt.SCHEMA

boom = mock.Mock(side_effect=AssertionError("must not fetch"))
f = {"view": view(statusCheckRollup=[check("ci"),
                                      check("pullfrog-approval")]),
     "files": None, "threads": [], "required": ["ci"],
     "diff": None}
with mock.patch.object(
        pt, "pr_files",
        return_value=(["apps/api/src/contract/shared.ts",
                       "apps/api/src/index.test.ts"], [])) as pf, \
        mock.patch.object(pt, "pr_diff", boom):
    pt.ensure_facts("wwwyo/me", 7, f)
    assert f["files"] == ["apps/api/src/contract/shared.ts",
                          "apps/api/src/index.test.ts"]
    assert f["diff"] is None
    pf.assert_called_once()
    ok, reasons = pt.hard_gate(f, judge={"sha": "sha1", "verdict": "ok", "policy_version": pt.JUDGE_POLICY_VERSION, "context_hash": pt.pr_context_hash(v)},
                               via="lane")
    assert not ok and any("shared.ts" in r for r in reasons) and \
        not any("index.test.ts" in r for r in reasons)
    e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                               f, [], {}, {})
    assert e["actions"][0]["type"] == "hold" and \
        "shared.ts" in e["actions"][0]["reason"]

f = {"view": view(), "files": None, "threads": [], "required": [],
     "diff": None}
with mock.patch.object(pt, "pr_files",
                       return_value=(["package.json"], [])) as pf, \
        mock.patch.object(pt, "pr_diff", return_value="d") as pd:
    pt.ensure_facts("wwwyo/me", 7, f)
assert f["files"] == ["package.json"] and \
    f["diff"] == "d"
pd.assert_called_once_with("wwwyo/me", 7)

f = {"view": view(), "files": None, "threads": [], "required": [],
     "diff": None}
with mock.patch.object(pt, "pr_files",
                       return_value=(["api/src/index.test.ts"], [])) as pf, \
        mock.patch.object(pt, "pr_diff", return_value="d2") as pd:
    pt.ensure_facts("wwwyo/me", 7, f)
assert f["files"] == ["api/src/index.test.ts"] and \
    f["diff"] == "d2"
pd.assert_called_once_with("wwwyo/me", 7)

f = {"view": view(), "files": None, "threads": [], "required": [],
     "diff": None}
with mock.patch.object(pt, "pr_files", return_value=(["package.json"], [])), \
        mock.patch.object(pt, "pr_diff",
                          side_effect=pt.ApiError("boom")):
    try:
        pt.ensure_facts("wwwyo/me", 7, f)
        raise SystemExit("ensure_facts swallowed ApiError")
    except pt.ApiError:
        pass
assert f["diff"] is None

f = {"view": view(), "files": ["src/a.py"], "threads": [], "required": [],
     "diff": "injected"}
with mock.patch.object(pt, "pr_files", boom), \
        mock.patch.object(pt, "pr_diff", boom):
    pt.ensure_facts("wwwyo/me", 7, f)
assert f["files"] == ["src/a.py"] and \
    f["diff"] == "injected"

# lockfile の差分量・間接 major は判定に影響せず、実行する workflow は残す。
lock_diff = 'diff --git a/bun.lock b/bun.lock\n' + ('+x\n' * 30000)
manifest_diff = 'diff --git a/package.json b/package.json\n+"x": "2.0.0"\n'
assert pt.review_diff(lock_diff + manifest_diff) == manifest_diff
assert pt.review_diff(manifest_diff * 3000) == manifest_diff * 3000
for name in pt.LOCKFILE_BASENAMES:
    assert pt.classify_path('apps/api/' + name) == 'other', name
assert pt.classify_path('.github/workflows/skillctrl.lock.yml') == 'hold'
assert pt.review_diff('diff --git a/a.py b/bun.lock\n-removed code\n')
assert pt.review_diff('diff --git "a/space dir/bun.lock" "b/space dir/bun.lock"\n+x\n') == ''
assert pt.classify_pr(['package.json', 'mise.lock'], meta_bot, '')['bot_dep_only']
assert pt.classify_pr(['bun.lock'], meta_bot, '')['lane'] == 'judge'
lock_major = 'diff --git a/mise.lock b/mise.lock\n-version = "1.0"\n+version = "2.0"\n'
assert pt.classify_pr(['docs/readme.md', 'mise.lock'], meta_w, lock_major)['lane'] == 'lane'

# 旧規則の verdict は同じ head でも再判定し、merge gate も通さない。
old = {'sha': 'sha1', 'verdict': 'ng', 'reason': 'truncated=true'}
f = facts(view=vbot, files=['package.json', 'bun.lock'])
e = pt.compute_pr_decision({'repo': 'wwwyo/me', 'number': 7}, f, [], {},
                           {'judge': {'wwwyo/me#7': old}})
assert e['actions'][0]['type'] == 'judge'
old['verdict'] = 'ok'
assert not pt.hard_gate(f, judge=old)[0]
with mock.patch.object(pt, 'pr_view', return_value=view()), \
        mock.patch.object(pt, 'pr_files', return_value=(['bun.lock', 'package.json'], [])), \
        mock.patch.object(pt, 'pr_diff', return_value=lock_diff + manifest_diff), \
        mock.patch.object(pt, 'emit') as output:
    pt._cmd_judge_input(SimpleNamespace(repo='wwwyo/me', number=7))
    result = output.call_args.args[0]
    assert result['diff'] == manifest_diff and not result['truncated']
    assert result['ignored_files'] == ['bun.lock']

# CI green の major 移行も repair で修正へ回し、新 head の全差分を再判定する。
repair_args = SimpleNamespace(repo='wwwyo/me', number=7, sha='sha1',
                              context_hash=pt.pr_context_hash(vbot), verdict='repair', reason='src/a.py: removed API; replace and test')
repair_state = {}
with mock.patch.object(pt, 'load_state', return_value=repair_state), \
        mock.patch.object(pt, 'save_state'), mock.patch.object(pt, 'append_event'), \
        mock.patch.object(pt, 'emit'), mock.patch.object(pt, 'pr_view', return_value=vbot), \
        mock.patch.object(pt, 'pr_files', return_value=(['package.json', 'bun.lock'], [])):
    pt.cmd_judge_result(repair_args)
j = repair_state['judge']['wwwyo/me#7']
assert j['verdict'] == 'repair' and j['dependency_repair']
f = facts(view=vbot, files=['package.json', 'bun.lock'], required=['ci'])
items = pt.dispatch_items('wwwyo/me', 7, f, repair_state)
assert [i['kind'] for i in items] == ['dependency_migration']
assert 'repair.md' in pt.build_dispatch_message('wwwyo/me', vbot, items)
e = pt.compute_pr_decision({'repo': 'wwwyo/me', 'number': 7}, f, [w], terms, repair_state)
assert e['actions'][0]['type'] == 'dispatch'
assert not pt.hard_gate(f, judge=j)[0]

# head 更新後は旧 repair の再送も旧 verdict の流用もせず、追従コードを judge に戻す。
repaired_view = dict(vbot, headRefOid='sha2')
f = facts(view=repaired_view, files=['package.json', 'src/a.py', 'tests/test_a.py'],
          required=['ci'])
assert not pt.dispatch_items('wwwyo/me', 7, f, repair_state)
e = pt.compute_pr_decision({'repo': 'wwwyo/me', 'number': 7}, f, [], {}, repair_state)
assert e['actions'][0]['type'] == 'judge'
assert e['actions'][0]['whitelist_hint'] == 'bot_dep_repair'
assert not pt.hard_gate(f, judge=j)[0]
with mock.patch.object(pt, 'load_state', return_value=repair_state), \
        mock.patch.object(pt, 'save_state'), mock.patch.object(pt, 'append_event'), \
        mock.patch.object(pt, 'pr_facts', side_effect=pt.ApiError('no gh in test')), \
        mock.patch.object(pt, 'emit'):
    pt.cmd_judge_result(SimpleNamespace(repo='wwwyo/me', number=7, sha='sha2',
                                       context_hash=pt.pr_context_hash(repaired_view), verdict='ok', reason='migration verified'))
j = repair_state['judge']['wwwyo/me#7']
e = pt.compute_pr_decision({'repo': 'wwwyo/me', 'number': 7}, f, [], {}, repair_state)
assert e['actions'][0]['type'] == 'merge' and not e['bot_dep_only']
assert pt.hard_gate(f, judge=j)[0]
for bad in [facts(view=dict(repaired_view, headRefOid='sha3'), files=f['files'], required=['ci']),
            facts(view=dict(repaired_view, statusCheckRollup=[check('ci', conc='FAILURE')]),
                  files=f['files'], required=['ci']),
            facts(view=repaired_view, files=f['files'], threads=[thread()], required=['ci']),
            facts(view=repaired_view, files=['package.json', '.env'])]:
    assert not pt.hard_gate(bad, judge=j)[0]

# 最初の repair は bot の現 head・依存-only・理由付きに限定し、保護 path を除外する。
for fresh_view, files, reason in [
        (dict(vbot, headRefOid='other'), ['package.json'], 'migration'),
        (dict(vbot, state='MERGED'), ['package.json'], 'migration'),
        (view(), ['package.json'], 'migration'),
        (vbot, ['package.json', 'src/a.py'], 'migration'),
        (vbot, ['.github/package.json'], 'migration'),
        (vbot, ['package.json'], '')]:
    with mock.patch.object(pt, 'load_state', return_value={}), \
            mock.patch.object(pt, 'save_state') as saved, \
            mock.patch.object(pt, 'emit'), \
            mock.patch.object(pt, 'pr_view', return_value=fresh_view), \
            mock.patch.object(pt, 'pr_files', return_value=(files, [])):
        try:
            pt.cmd_judge_result(SimpleNamespace(repo='wwwyo/me', number=7, sha='sha1',
                                               context_hash=pt.pr_context_hash(vbot), verdict='repair', reason=reason))
            raise AssertionError('invalid repair accepted')
        except SystemExit:
            pass
        saved.assert_not_called()

# workflow のみの bot PR も repair verdict を受理する（bot_dep と同じ集合）
with mock.patch.object(pt, 'load_state', return_value={}), \
        mock.patch.object(pt, 'save_state') as saved, \
        mock.patch.object(pt, 'append_event'), mock.patch.object(pt, 'emit'), \
        mock.patch.object(pt, 'pr_view', return_value=vbot), \
        mock.patch.object(pt, 'pr_files',
                          return_value=(['.github/workflows/pullfrog.yml'], [])):
    pt.cmd_judge_result(SimpleNamespace(repo='wwwyo/me', number=7, sha='sha1',
                                       context_hash=pt.pr_context_hash(vbot), verdict='repair', reason='v7 migration'))
    st = saved.call_args[0][0]
    assert st['judge']['wwwyo/me#7']['dependency_repair']

# local session 全件照合で routine 外の merge も発見する。
done = wt(hostId='local', workspaceStatus='completed', liveTerminalCount=2,
          agents=[{'state': 'done'}], linkedPR={'number': 8, 'state': 'open'})
remote = wt(hostId='remote', worktreeId='remote::w')
with mock.patch.object(pt, 'terminal_list', return_value=[{'handle': 't'}]) as tl, \
        mock.patch.object(pt, 'sh', return_value=SimpleNamespace(stdout='git@github.com:wwwyo/me.git\n')), \
        mock.patch.object(pt, 'gh_json', return_value={
            'number': 8, 'state': 'MERGED', 'headRefName': 'wwwyo/x',
            'headRefOid': 'abc', 'mergedAt': '2026-10-03T00:00:00Z'}), \
        mock.patch.object(pt, 'append_event'):
    state = {}
    assert pt.local_session_audit(state, [done, remote], {}) == {'worktrees': 1, 'sessions': 1}
    tl.assert_called_once_with('r::w1')
    assert state['merged']['wwwyo/me#8']['via'] == 'external'
assert len(pt.sweep_candidates(state, [done])) == 1
assert not pt.sweep_candidates(state, [dict(done, isActive=True)])
assert not pt.sweep_candidates(state, [dict(done, childWorktreeIds=['child'])])
assert not pt.sweep_candidates(state, [dict(done, workspaceStatus='in-progress')])
assert pt.sweep_sessions_ready(done, [{'agentIdentity': 'codex'}, {'connected': True, 'preview': '$'}])
assert not pt.sweep_sessions_ready(done, [{'connected': True, 'preview': 'building...'}])
assert not pt.sweep_sessions_ready(dict(done, agents=[{'state': 'working'}]), [])

# close が失敗したら worktree は削除しない。
with mock.patch.object(pt, 'load_state', return_value=state), \
        mock.patch.object(pt, 'worktree_ps', return_value=[done]), \
        mock.patch.object(pt, 'local_session_audit', return_value={}), \
        mock.patch.object(pt, 'terminal_list', return_value=[]), \
        mock.patch.object(pt, 'sh', side_effect=[SimpleNamespace(stdout=''), SimpleNamespace(stdout='abc'), SimpleNamespace(stdout='wwwyo/x')]), \
        mock.patch.object(pt, 'gh_json', return_value={'state': 'MERGED', 'headRefOid': 'abc', 'headRefName': 'wwwyo/x'}), \
        mock.patch.object(pt, 'orca_json', side_effect=pt.ApiError('close unverifiable')) as oc, \
        mock.patch.object(pt, 'append_event'), \
        mock.patch.object(pt, 'save_state'), \
        mock.patch.object(pt, 'emit') as output:
    pt._cmd_sweep(SimpleNamespace(only=None, dry_run=False))
    assert oc.call_args.args[0][:2] == ['terminal', 'close']
    assert oc.call_count == 1 and not output.call_args.args[0]['removed']

# skip 理由は sweep_skipped として jsonl に残るが、同じ worktree+理由の
# 連続は初回だけ（live terminal が tick ごとに残るケースで jsonl を埋めない）
sweep_st = {"merged": {"wwwyo/me#8": {"sha": "abc", "head_ref": "wwwyo/x"}}}
cand = wt(linkedPR={"number": 8, "state": "merged"}, workspaceStatus="completed")
so = lambda s: SimpleNamespace(stdout=s)

def run_sweep(sh_outs, dry_run=False):
    with mock.patch.object(pt, 'load_state', return_value=sweep_st), \
            mock.patch.object(pt, 'worktree_ps', return_value=[cand]), \
            mock.patch.object(pt, 'local_session_audit', return_value={}), \
            mock.patch.object(pt, 'terminal_list', return_value=[]), \
            mock.patch.object(pt, 'sh', side_effect=[so(x) for x in sh_outs]), \
            mock.patch.object(pt, 'gh_json', return_value={
                'state': 'MERGED', 'headRefOid': 'abc',
                'headRefName': 'wwwyo/x'}), \
            mock.patch.object(pt, 'save_state'), mock.patch.object(pt, 'emit'), \
            mock.patch.object(pt, 'append_event') as ev:
        pt._cmd_sweep(SimpleNamespace(only=None, dry_run=dry_run))
        return [(c.args[0], c.kwargs.get('reason'))
                for c in ev.call_args_list]

assert run_sweep([' M f']) == [('sweep_skipped', 'dirty worktree')]
assert run_sweep([' M f']) == []                    # 同じ理由は再記録しない
assert run_sweep(['', 'abc', 'other']) == \
    [('sweep_skipped', 'branch changed')]
# 永続的 skip が上限に達すると sweep_giveup も残る
sweep_st["merged"]["wwwyo/me#8"]["sweep_skips"] = pt.SWEEP_MAX_TRIES - 1
assert run_sweep([' M f']) == [('sweep_skipped', 'dirty worktree'),
                              ('sweep_giveup', 'dirty worktree')]
# dry-run はイベントを記録しない
sweep_st["merged"]["wwwyo/me#8"]["sweep_skips"] = 0
assert run_sweep([' M f'], dry_run=True) == []

# mise tool pin の bot PR は approval が無くても judge 後に merge へ進む。
mise_files = ['home/dot_config/mise/config.toml', 'home/dot_config/mise/mise.lock']
v = view(author={'login': 'app/renovate', 'is_bot': True},
         statusCheckRollup=[check('ci')])
f = facts(view=v, files=mise_files, required=['ci'])
e = pt.compute_pr_decision({'repo': 'wwwyo/me', 'number': 7}, f, [], {}, {})
assert e['actions'][0]['type'] == 'judge'
assert e['actions'][0]['whitelist_hint'] == 'bot_dep'
j = {'sha': 'sha1', 'verdict': 'ok', 'policy_version': pt.JUDGE_POLICY_VERSION, 'context_hash': pt.pr_context_hash(v)}
e = pt.compute_pr_decision({'repo': 'wwwyo/me', 'number': 7}, f, [], {},
                           {'judge': {'wwwyo/me#7': j}})
assert e['actions'][0]['type'] == 'merge'
assert pt.hard_gate(f, judge=j)[0]
assert not pt.hard_gate(f, judge=dict(j, sha='old'))[0]
assert not pt.hard_gate(dict(f, threads=[thread()]), judge=j)[0]
bad_ci = view(**dict(v, statusCheckRollup=[check('ci', conc='FAILURE')]))
assert not pt.hard_gate(dict(f, view=bad_ci), judge=j)[0]
assert any(i['kind'] == 'dependency_ci' for i in
           pt.dispatch_items('wwwyo/me', 7, dict(f, view=bad_ci), {}))
for manifest in ['home/dot_config/mise/config.toml', '.config/mise/config.toml']:
    assert pt.classify_path(manifest) == 'judge'
for files in [['config.toml'], ['config/app.toml'], mise_files + ['config/app.toml']]:
    cls = pt.classify_pr(files, v, '')
    assert not cls['bot_dep_only']
    assert not pt.hard_gate(dict(f, files=files), judge=j)[0]
human = view(statusCheckRollup=[check('ci')])
assert not pt.hard_gate(dict(f, view=human), judge=j)[0]

# ============================ dep auto-ok（minor/patch・devDep） ============================
# spec 分類はタイトルの自己申告ではなく実 spec の差だけを見る
assert pt.dep_bump_kind("^1.2.3", "^1.2.4") == "patch"
assert pt.dep_bump_kind("^1.2.3", "^1.3.0") == "minor"
assert pt.dep_bump_kind("^1.2.3", "^2.0.0") == "major"
assert pt.dep_bump_kind("v1.0.0", "v2.0.0") == "major"
assert pt.dep_bump_kind("2.0.0", "1.9.0") == "unknown"      # downgrade
assert pt.dep_bump_kind("^1.2.3", "^1.2.3") == "unknown"    # 同 version
assert pt.dep_bump_kind("^1.2.3", "~1.2.4") == "unknown"    # prefix 変更
assert pt.dep_bump_kind("1.2.3", "1.2.4-beta.1") == "unknown"
assert pt.dep_bump_kind("*", "^1.0.0") == "unknown"
assert pt.dep_bump_kind("latest", "5.0.0") == "unknown"
assert pt.dep_bump_kind("workspace:*", "workspace:^1.0.0") == "unknown"
assert pt.dep_bump_kind(">=1.0.0", ">=2.0.0") == "unknown"
# 0.x 台の minor 更新は breaking がありうるので major に格上げ
assert pt.dep_bump_kind("^0.2.3", "^0.3.0") == "major"
assert pt.dep_bump_kind("^0.2.3", "^0.2.4") == "patch"
# ^0.0.x は =0.0.x 同値なので patch 更新も互換境界を跨ぐ
assert pt.dep_bump_kind("^0.0.3", "^0.0.4") == "major"
assert pt.dep_bump_kind("0.2.3", "1.0.0") == "major"

def pkg(deps=None, dev=None, **kw):
    d = {"name": "x", "version": "1.0.0"}
    if deps is not None:
        d["dependencies"] = deps
    if dev is not None:
        d["devDependencies"] = dev
    d.update(kw)
    return json.dumps(d)

# minor runtime + devDep major の実差分から種別を出す
base_pkg = pkg(deps={"react": "^18.2.0"}, dev={"prettier": "^3.0.0"})
head_pkg = pkg(deps={"react": "^18.3.0"}, dev={"prettier": "^4.0.0"})
ups = pt.package_json_updates(base_pkg, head_pkg)
assert {(u["name"], u["section"]): u["kind"] for u in ups} == \
    {("react", "dependencies"): "minor",
     ("prettier", "devDependencies"): "major"}
# 依存 section 以外の top-level 変更・依存の追加/削除・parse 失敗は判定不能
assert pt.package_json_updates(base_pkg, head_pkg) is not None
assert pt.package_json_updates(
    base_pkg, pkg(deps={"react": "^18.3.0"}, dev={"prettier": "^4.0.0"},
                  scripts={"build": "x"})) is None
assert pt.package_json_updates(
    pkg(deps={"a": "^1.0.0"}), pkg(deps={"a": "^1.0.0", "b": "^2.0.0"})) is None
assert pt.package_json_updates(
    pkg(deps={"a": "^1.0.0", "b": "^1.0.0"}), pkg(deps={"a": "^1.0.0"})) is None
assert pt.package_json_updates("not json", base_pkg) is None

# dep_auto_ok: base/head の manifest 内容を ref 指定で取る
dep_view = view(author={"login": "dependabot[bot]", "is_bot": True},
                baseRefOid="base1", headRefOid="sha1",
                statusCheckRollup=[check("ci")])
def dep_facts(**kw):
    kw.setdefault("view", dep_view)
    return facts(**kw)

def refs(base_map, head_map):
    def fetch(repo, path, ref):
        return (base_map if ref == "base1" else head_map)[path]
    return fetch

def auto_ok(f, base_map, head_map):
    with mock.patch.object(pt, "file_at_ref",
                           side_effect=refs(base_map, head_map)):
        return pt.dep_auto_ok("wwwyo/me", f)

minor_b = {"package.json": pkg(deps={"react": "^18.2.0"})}
minor_h = {"package.json": pkg(deps={"react": "^18.3.0"})}
patch_b = {"package.json": pkg(deps={"react": "^18.2.0"})}
patch_h = {"package.json": pkg(deps={"react": "^18.2.1"})}
devmaj_b = {"package.json": pkg(dev={"@types/node": "^22.0.0"})}
devmaj_h = {"package.json": pkg(dev={"@types/node": "^24.0.0"})}
maj_b = {"package.json": pkg(deps={"react": "^18.2.0"})}
maj_h = {"package.json": pkg(deps={"react": "^19.0.0"})}
group_b = {"package.json": pkg(deps={"react": "^18.2.0", "axios": "^1.6.0"})}
group_h = {"package.json": pkg(deps={"react": "^19.0.0", "axios": "^1.7.0"})}
unk_b = {"package.json": pkg(deps={"x": "*"}, dev={"y": "^1.0.0"})}
unk_h = {"package.json": pkg(deps={"x": "^2.0.0"}, dev={"y": "^1.1.0"})}

files_pkg = ["package.json", "bun.lock"]
# minor / patch / devDep major → 自動 ok 対象
for b, h in [(minor_b, minor_h), (patch_b, patch_h), (devmaj_b, devmaj_h)]:
    r = auto_ok(dep_facts(files=files_pkg), b, h)
    assert r["eligible"], r
    assert r["updates"] and not r["reasons"]
# runtime major → judge 経路
r = auto_ok(dep_facts(files=files_pkg), maj_b, maj_h)
assert not r["eligible"] and any("runtime major" in x for x in r["reasons"])
# runtime の 0.x minor 更新も breaking がありうるので judge 経路
zeromin_b = {"package.json": pkg(deps={"lib": "^0.2.3"})}
zeromin_h = {"package.json": pkg(deps={"lib": "^0.3.0"})}
r = auto_ok(dep_facts(files=files_pkg), zeromin_b, zeromin_h)
assert not r["eligible"] and any("major" in x for x in r["reasons"])
# runtime の 0.0.x patch 更新も同様に judge 経路
r = auto_ok(dep_facts(files=files_pkg),
            {"package.json": pkg(deps={"lib": "^0.0.3"})},
            {"package.json": pkg(deps={"lib": "^0.0.4"})})
assert not r["eligible"] and any("major" in x for x in r["reasons"])
# devDep の 0.x minor は自動 ok（devDep は major でも対象）
r = auto_ok(dep_facts(files=files_pkg),
            {"package.json": pkg(dev={"lib": "^0.2.3"})},
            {"package.json": pkg(dev={"lib": "^0.3.0"})})
assert r["eligible"], r
# peerDependencies の更新は consumer の依存解決に影響するので judge 経路
peer_b = {"package.json": pkg(peerDependencies={"react": "^18.2.0"})}
peer_h = {"package.json": pkg(peerDependencies={"react": "^18.3.0"})}
r = auto_ok(dep_facts(files=files_pkg), peer_b, peer_h)
assert not r["eligible"] and any("peerDependencies" in x for x in r["reasons"])
# grouped: runtime major が1件でも混ざれば全体が judge 経路
r = auto_ok(dep_facts(files=files_pkg), group_b, group_h)
assert not r["eligible"] and any("react" in x for x in r["reasons"])
# 確定できない spec → judge 経路
r = auto_ok(dep_facts(files=files_pkg), unk_b, unk_h)
assert not r["eligible"] and any("unresolved version spec" in x for x in r["reasons"])
# rename・依存以外の manifest・workflow・lockfile のみ・読めない manifest は自動 ok にしない
r = pt.dep_auto_ok("wwwyo/me",
                   dep_facts(files=files_pkg, renamed_from=["old.json"]))
assert not r["eligible"] and "renamed" in r["reasons"][0]
r = pt.dep_auto_ok("wwwyo/me", dep_facts(files=["go.mod", "go.sum"]))
assert not r["eligible"] and "unclassifiable" in r["reasons"][0]
r = pt.dep_auto_ok("wwwyo/me",
                   dep_facts(files=[".github/workflows/ci.yml"]))
assert not r["eligible"]
# package.json と対応しない lockfile（他 ecosystem・別 dir・lockfile のみ）は
# 未マッピングとして自動 ok にしない
r = pt.dep_auto_ok("wwwyo/me", dep_facts(files=["package.json", "go.sum"]))
assert not r["eligible"] and "unmapped lockfile" in r["reasons"][0]
r = pt.dep_auto_ok("wwwyo/me",
                   dep_facts(files=["package.json", "sub/bun.lock"]))
assert not r["eligible"] and "unmapped lockfile" in r["reasons"][0]
r = pt.dep_auto_ok("wwwyo/me", dep_facts(files=["bun.lock"]))
assert not r["eligible"] and "unmapped lockfile" in r["reasons"][0]
with mock.patch.object(pt, "file_at_ref",
                       side_effect=pt.ApiError("gone")):
    r = pt.dep_auto_ok("wwwyo/me", dep_facts(files=files_pkg))
assert not r["eligible"] and "unreadable" in r["reasons"][0]

# mise の開発 tool pin は Renovate/Dependabot とも devDependencies 相当。
# 0.x minor、major、beta pin の更新でも judge を挟まず merge 候補になる。
mise_base = '''[tools]
"aqua:openai/codex" = "0.159.2"
"npm:vercel" = "60.1.3"
"npm:cf" = "1.0.0-beta.6"
python = "3.14.7"
[settings]
minimum_release_age = "7d"
'''
mise_head = mise_base.replace('0.159.2', '0.160.0').replace('60.1.3', '62.0.0') \
    .replace('beta.6', 'beta.12').replace('3.14.7', '3.14.8')
for manifest in ['home/dot_config/mise/config.toml', '.config/mise/config.toml',
                 'mise.toml', '.mise.toml']:
    lock = str(Path(manifest).with_name('mise.lock'))
    for author in [{'login': 'app/renovate', 'is_bot': True},
                   {'login': 'dependabot[bot]', 'is_bot': True}]:
        f = dep_facts(files=[lock, manifest],
                      view=dict(dep_view, author=author), required=['ci'])
        with mock.patch.object(pt, 'file_at_ref',
                               side_effect=refs({manifest: mise_base},
                                                {manifest: mise_head})):
            e = pt.compute_pr_decision({'repo': 'wwwyo/dotfiles', 'number': 49},
                                       f, [], {}, {})
            assert e['actions'][0]['type'] == 'merge', e
            assert e['dep_auto_ok'] and len(e['actions'][0]['dep_updates']) == 4
            assert pt.hard_gate(f, via='lane')[0]
            f['view']['statusCheckRollup'] = [check('ci', conc='FAILURE')]
            assert not pt.hard_gate(f, via='lane')[0]

# tool 追加/削除・設定/installer option変更・未知pin・downgrade は自動 ok にしない。
for head in [mise_head + '\n[env]\nFOO = "bar"\n',
             mise_head.replace('7d', '0d'),
             mise_head.replace('python = "3.14.8"', 'python = "3.14.8"\nrust = "1.99.0"'),
             mise_head.replace('python = "3.14.8"\n', ''),
             mise_head.replace('3.14.8', 'latest'),
             mise_head.replace('3.14.8', '3.14'),
             mise_head.replace('3.14.8', '3.14.6'),
             mise_head.replace('beta.12', 'beta.5')]:
    r = auto_ok(dep_facts(files=['mise.toml', 'mise.lock']),
                {'mise.toml': mise_base}, {'mise.toml': head})
    assert not r['eligible'], r
table_base = '[tools]\n"ubi:dbt-labs/dbt-cli" = {version="0.40.24", exe="dbt"}\n'
table_head = table_base.replace('0.40.24', '0.41.0')
r = auto_ok(dep_facts(files=['mise.toml']),
            {'mise.toml': table_base}, {'mise.toml': table_head})
assert r['eligible'], r
r = auto_ok(dep_facts(files=['mise.toml']), {'mise.toml': table_base},
            {'mise.toml': table_head.replace('exe="dbt"', 'exe="other"')})
assert not r['eligible'], r
for files in [['mise.lock'], ['mise.toml', 'sub/mise.lock'],
              ['config.toml'], ['mise.toml', 'src/app.py']]:
    r = auto_ok(dep_facts(files=files),
                {'mise.toml': mise_base}, {'mise.toml': mise_head})
    assert not r['eligible'], r
assert pt.mise_tool_updates('not toml [', mise_head) is None

# ref の取得は GET。gh api の -f が既定 POST を選ばないようにする。
with mock.patch.object(pt, 'gh', return_value=type('Response', (), {'stdout': mise_base})()) as api:
    assert pt.file_at_ref('wwwyo/dotfiles', 'mise.toml', 'base') == mise_base
    assert api.call_args.args[0][:3] == ['api', '-X', 'GET']
    assert 'ref=base' in api.call_args.args[0]

# automation prompt は skill の同実行 merge を打ち消さない。
import tomllib
repo_root = Path(sys.argv[1]).resolve().parents[4]
automation = tomllib.loads((repo_root / '.agents/scheduled-tasks/pr-auto-merge/automation.toml').read_text())
assert 'merge_ready: true' in automation['prompt']
assert 'ok でも merge action は追加せず' not in automation['prompt']

# 現行 head に紐付く ng/repair verdict は自動 ok を上書きしない（fail-closed）
j_ng = {"sha": "sha1", "verdict": "ng",
        "policy_version": pt.JUDGE_POLICY_VERSION,
        "context_hash": pt.pr_context_hash(dep_view)}
assert pt.dep_auto_ok_eligible({"eligible": True}, j_ng, "sha1", dep_view) is False
assert pt.dep_auto_ok_eligible(
    {"eligible": True}, dict(j_ng, verdict="repair"), "sha1", dep_view) is False
# 文脈（head・本文・CI 等）が変われば旧 ng は外れて自動 ok に戻る
assert pt.dep_auto_ok_eligible(
    {"eligible": True}, j_ng, "sha2", dep_view) is True
assert pt.dep_auto_ok_eligible(
    {"eligible": True},
    dict(j_ng, verdict="ok"), "sha1", dep_view) is True
assert pt.dep_auto_ok_eligible({"eligible": False}, {}, "sha1", dep_view) is False
assert pt.dep_auto_ok_eligible(None, {}, "sha1", dep_view) is False
assert pt.dep_auto_ok_eligible(
    {"eligible": True}, dict(j_ng, policy_version=pt.JUDGE_POLICY_VERSION - 1),
    "sha1", dep_view) is True

# gate: 自動 ok 対象は judge action を出さず merge action が出る
with mock.patch.object(pt, "file_at_ref", side_effect=refs(minor_b, minor_h)):
    e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                               dep_facts(files=files_pkg, required=["ci"]),
                               [], {}, {})
    assert e["actions"][0]["type"] == "merge" and e["dep_auto_ok"]
    assert e["actions"][0]["dep_auto_ok"] and e["actions"][0]["dep_updates"]
    # merge 直前の hard gate も同じ基準を live で引き直す
    f = dep_facts(files=files_pkg, required=["ci"])
    ok, reasons = pt.hard_gate(f, via="lane")
    assert ok, reasons
    assert f["dep_auto_ok"]["eligible"]
# devDep major も同じく judge 無しで merge 候補
with mock.patch.object(pt, "file_at_ref", side_effect=refs(devmaj_b, devmaj_h)):
    e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                               dep_facts(files=files_pkg, required=["ci"]),
                               [], {}, {})
    assert e["actions"][0]["type"] == "merge"
# runtime major → judge action（理由に更新が出る）、ok 登録で merge 候補
with mock.patch.object(pt, "file_at_ref", side_effect=refs(maj_b, maj_h)):
    e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                               dep_facts(files=files_pkg, required=["ci"]),
                               [], {}, {})
    assert e["actions"][0]["type"] == "judge" and \
        any("runtime major" in x for x in e["actions"][0]["reasons"])
    j_ok = {"sha": "sha1", "verdict": "ok",
            "policy_version": pt.JUDGE_POLICY_VERSION,
            "context_hash": pt.pr_context_hash(dep_view)}
    st = {"judge": {"wwwyo/me#7": j_ok}}
    e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                               dep_facts(files=files_pkg, required=["ci"]),
                               [], {}, st)
    assert e["actions"][0]["type"] == "merge" and not e["actions"][0]["dep_auto_ok"]
    f = dep_facts(files=files_pkg, required=["ci"])
    assert pt.hard_gate(f, judge=j_ok, via="lane")[0]
# grouped で runtime major が混ざる → judge
with mock.patch.object(pt, "file_at_ref", side_effect=refs(group_b, group_h)):
    e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                               dep_facts(files=files_pkg, required=["ci"]),
                               [], {}, {})
    assert e["actions"][0]["type"] == "judge"
# 未知 version は自動 ok しない
with mock.patch.object(pt, "file_at_ref", side_effect=refs(unk_b, unk_h)):
    e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7},
                               dep_facts(files=files_pkg, required=["ci"]),
                               [], {}, {})
    assert e["actions"][0]["type"] == "judge"
# head が major 化して動いた PR は、gate 時の自動 ok を持ち越さず merge で弾く
moved_view = dict(dep_view, headRefOid="sha2")
f = dep_facts(view=moved_view, files=files_pkg, required=["ci"])
with mock.patch.object(pt, "file_at_ref",
                       side_effect=refs(maj_b, maj_h)):
    # head=sha2 だが期待 sha は sha1 → まず head moved で弾く
    ok, reasons = pt.hard_gate(f, via="lane", expect_sha="sha1")
    assert not ok and any("head moved" in r for r in reasons)
    # 同じ head で再評価しても runtime major は自動 ok にならない
    ok, reasons = pt.hard_gate(f, via="lane")
    assert not ok and any("judge ok or dependency auto-ok" in r for r in reasons)
# 自動 ok でも残る hard gate（required CI・unaddressed・always-hold）は緩めない
with mock.patch.object(pt, "file_at_ref", side_effect=refs(minor_b, minor_h)):
    f = dep_facts(files=files_pkg, required=["ci"],
                  view=dict(dep_view, statusCheckRollup=[
                      check("ci", conc="FAILURE")]))
    ok, reasons = pt.hard_gate(f, via="lane")
    assert not ok and any("failing" in r for r in reasons)
    f = dep_facts(files=files_pkg, required=["ci"], threads=[thread()])
    assert not pt.hard_gate(f, via="lane")[0]
    f = dep_facts(files=["package.json", ".env"], required=["ci"])
    with mock.patch.object(pt, "file_at_ref", boom):
        ok, reasons = pt.hard_gate(f, via="lane")
    assert not ok and any("lane=hold" in r for r in reasons)
    e = pt.compute_pr_decision(
        {"repo": "wwwyo/me", "number": 7},
        dep_facts(files=files_pkg, required=["ci"], threads=[thread()]),
        [w], terms, {})
    assert e["actions"][0]["type"] == "dispatch"
# 判定後に状態が変わった verdict（context 不一致）は auto ok でも使われず、
# judge verdict のみの PR は gate が再判定を要求する
with mock.patch.object(pt, "file_at_ref", side_effect=refs(maj_b, maj_h)):
    changed = dict(dep_view, body="updated body")
    stale_j = {"sha": "sha1", "verdict": "ok",
               "policy_version": pt.JUDGE_POLICY_VERSION,
               "context_hash": pt.pr_context_hash(dep_view)}
    f = dep_facts(view=changed, files=files_pkg, required=["ci"])
    e = pt.compute_pr_decision({"repo": "wwwyo/me", "number": 7}, f, [], {},
                               {"judge": {"wwwyo/me#7": stale_j}})
    assert e["actions"][0]["type"] == "judge"
    assert not pt.hard_gate(f, judge=stale_j, via="lane")[0]

# judge-result: ok 登録後に live hard gate が通れば merge_ready で同じ実行内の
# merge を案内する。ng/repair・gate 不通・判定後の状態変化は merge_ready=false
ok_view = dict(dep_view, statusCheckRollup=[check("ci"),
                                            check("pullfrog-approval")])
ok_facts = facts(view=ok_view, files=["src/a.py"], required=["ci"])
saved = {}
with mock.patch.object(pt, "load_state", return_value={}), \
        mock.patch.object(pt, "save_state",
                          side_effect=lambda s: saved.update(s)), \
        mock.patch.object(pt, "append_event"), \
        mock.patch.object(pt, "pr_facts", return_value=ok_facts), \
        mock.patch.object(pt, "emit") as emit:
    pt.cmd_judge_result(SimpleNamespace(
        repo="wwwyo/me", number=7, sha="sha1",
        context_hash=pt.pr_context_hash(ok_view),
        verdict="ok", reason="ok"))
out = emit.call_args.args[0]
assert out["merge_ready"] is True and "blocked" not in out
for verdict, facts_now in [
        ("ng", ok_facts),
        ("ok", facts(view=dict(ok_view, statusCheckRollup=[
            check("ci", conc="FAILURE"), check("pullfrog-approval")]),
            files=["src/a.py"], required=["ci"])),
        ("ok", facts(view=dict(ok_view, headRefOid="sha9"),
                     files=["src/a.py"], required=["ci"]))]:
    with mock.patch.object(pt, "load_state", return_value={}), \
            mock.patch.object(pt, "save_state"), \
            mock.patch.object(pt, "append_event"), \
            mock.patch.object(pt, "pr_facts", return_value=facts_now), \
            mock.patch.object(pt, "emit") as emit:
        pt.cmd_judge_result(SimpleNamespace(
            repo="wwwyo/me", number=7, sha="sha1",
            context_hash=pt.pr_context_hash(ok_view),
            verdict=verdict, reason="r"))
    out = emit.call_args.args[0]
    assert out["ok"] and out["merge_ready"] is False, (verdict, out)
# merge_ready の判定に失敗しても verdict 登録自体は成功する（fail-closed）
with mock.patch.object(pt, "load_state", return_value={}), \
        mock.patch.object(pt, "save_state"), \
        mock.patch.object(pt, "append_event"), \
        mock.patch.object(pt, "pr_facts",
                          side_effect=pt.ApiError("gh down")), \
        mock.patch.object(pt, "emit") as emit:
    pt.cmd_judge_result(SimpleNamespace(
        repo="wwwyo/me", number=7, sha="sha1",
        context_hash=pt.pr_context_hash(dep_view),
        verdict="ok", reason="r"))
out = emit.call_args.args[0]
assert out["ok"] and out["merge_ready"] is False and out["blocked"]

# 補足ログは長文・改行を保持し、実績や判定 state を変更しない。
import subprocess
note_file = pt.STATE_DIR / "note.json"
note_file.parent.mkdir(parents=True, exist_ok=True)
message = "判定根拠\n" + "長い検証記録" * 80
note = {"message": message, "repo": "wwwyo/me", "pr": 7, "sha": "sha1",
        "sources": ["https://github.com/wwwyo/me/pull/7"],
        "details": {"command": "build", "exit_code": 0}}
note_file.write_text(json.dumps(note))
state_before = pt.load_state()
result = subprocess.run([sys.executable, sys.argv[1], "log", "--input", str(note_file)],
                        text=True, capture_output=True)
assert result.returncode == 0, result.stdout + result.stderr
record = json.loads(result.stdout)["record"]
assert record["event"] == "note" and record["message"] == message
assert record["sources"] == note["sources"] and record["details"] == note["details"]
assert pt.load_state() == state_before
result = subprocess.run([sys.executable, sys.argv[1], "events", "--event", "note",
                         "--repo", "wwwyo/me", "--number", "7", "--limit", "1"],
                        text=True, capture_output=True)
assert result.returncode == 0
assert json.loads(result.stdout)["events"] == [record]
records_before = pt.read_events()
for bad in [{"message": message, "event": "merge"}, {"message": message, "ts": "old"},
            {"message": ""}, {"message": message, "pr": True},
            {"message": message, "sources": "not-an-array"}]:
    note_file.write_text(json.dumps(bad))
    result = subprocess.run([sys.executable, sys.argv[1], "log", "--input", str(note_file)],
                            text=True, capture_output=True)
    assert result.returncode != 0
    assert not json.loads(result.stdout)["ok"]
assert pt.read_events() == records_before
assert pt.load_state() == state_before

# 判定の長い理由も jsonl で切り捨てず読み戻せる。
pt.cmd_judge_result(SimpleNamespace(repo="wwwyo/me", number=7, sha="sha1",
                                   context_hash=pt.pr_context_hash(view()),
                                   verdict="ng", reason=message))
assert pt.read_events()[-1]["reason"] == message

# ============================ message / lock / state ============================
msg = pt.build_dispatch_message(
    "wwwyo/me", view(url="https://x", title="t", number=7),
    pt.unaddressed_items(view(), [thread()]))
assert "pullfrog" in msg and "a.py:3" in msg and "fix this" in msg

# lock: acquire → busy → release → acquire
assert pt._lock_acquire(60)
assert not pt._lock_acquire(60)
pt._lock_release()
assert pt._lock_acquire(60)
pt._lock_release()
# stale lock: ts を過去にすれば回収される
import time
pt._lock_acquire(60)
info = pt._lock_info()
info["ts"] = time.time() - 7200
(pt.LOCK_DIR / "info.json").write_text(json.dumps(info))
assert pt._lock_acquire(60)   # stale 回収して再取得
pt._lock_release()

# state save/load roundtrip
st = {"prs": {"wwwyo/me#7": {"dispatches": [], "rounds": []}}}
pt.save_state(st)
assert pt.load_state() == st

print("ok")
EOF

echo "OK: pr_triage classify/route/gate"
