#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# ///
"""pr_triage — pr-merge-lane routine の triage tool。

orca automation `pr-auto-merge`（30分間隔）の precheck と、起動された
executor session から呼ばれる。全 subcommand は JSON を stdout に出す。

  gate          precheck 入口。事実収集 + 全 action 決定 + plan 書き出し。
                action あり → exit 0（run lock は保持したまま
                session へ引き継ぐ）。なし → lock 解放して exit 1。
                API 失敗 → lock 解放して exit 2（fail-closed）
  plan          現在の tick plan を返す（session はこれだけを見る）
  dispatch      1 PR 分の dispatch を実行（send / revive / spawn の解決、
                上限管理、delivery 検証、jsonl 記録まで script がやる）
  escalate      上限到達 PR へ escalation コメントを投稿して打ち切る
  judge-input   diff・PR 本文・CI を LLM judge へ渡す形で出す
  judge-result  judge の判定を head SHA・context_hash・policy_version に紐付けて記録する
  merge         merge の唯一の発行経路。発行直前に hard gate を全件引き直す
  sweep         routine が merge した PR の worktree を条件付き削除する
  lock          run lock の acquire/release/status（session 終了時に release）
  log           executor の根拠・確認・引き継ぎを jsonl に追記する
  events        当日（または指定日）の pr-watch.jsonl イベントを返す
  schema        subcommand の入出力スキーマを返す

判定の所在: path 3分類・unaddressed 判定・dispatch routing・hard gate・
上限・worktree 削除条件は全部このファイルにあり、executor session は
script の決定を実行するだけ。merge 候補の QA・Blast Radius の意味判定は LLM judge に
渡る（judge の判定は head SHA・context_hash・policy_version に紐付けて記録され、
merge 発行権は持たない）が、bot の依存更新のみの PR で全更新が
minor/patch・devDependencies（major 含む）と base/head の実 manifest 差分から
確定できるものは script が自動 ok とし、judge を介さず merge 候補にする。
runtime dependency の major・確定不能な更新・依存以外の差分を含む PR は
従来どおり judge 経路。

lock は mkdir lock。PRD には flock とあるが、fcntl.flock の fd は process
寿命に紐づくため、precheck(gate) → executor session と process を跨ぐ
この形には使えない（session_eval.py と同じ結論）。mkdir の atomicity で
single-runner が保たれ、stale は TTL 超の info.json で判定して取り直す。

副作用の内訳: この script が持つのは merge・worktree rm・dispatch 送信・
escalate コメント・state/plan/jsonl の書き込み。PR へのレビューコメント・
pr-watch.md の記述は executor session が行う。
"""

import argparse
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
    JST = ZoneInfo("Asia/Tokyo")
except Exception:
    # tzdata の無い環境向け fallback（JST は DST なし固定）
    JST = timezone(timedelta(hours=9))

OWNER = "wwwyo"
STATE_DIR = Path(os.environ.get("PR_WATCH_STATE_DIR",
                                Path.home() / ".local" / "state" / "pr-watch"))
STATE_FILE = STATE_DIR / "state.json"
LOCK_DIR = STATE_DIR / "run.lockdir"
PLAN_FILE = STATE_DIR / "current-plan.json"
LOCK_TTL_S = int(os.environ.get("PR_WATCH_LOCK_TTL_S", 2 * 3600))
ME_REPO = Path(os.environ.get(
    "PR_WATCH_ME_REPO", Path.home() / "src" / "github.com" / "wwwyo" / "me"))

DISPATCH_MAX_PER_HEAD = 3   # 同一 (PR, head SHA) への送信上限
DISPATCH_MAX_ROUNDS = 3     # 往復ラウンド（dispatch を送った異なる head 数）上限
DISPATCH_STALE_TICKS = 6    # 送信後に指摘が動かないままの tick 数上限（~3h）
SWEEP_MAX_TRIES = 6         # sweep が永続的理由で skip し続ける回数上限（~3h）
# 一時的な理由は ps 再取得との race 窓の 2 つだけ。git の timeout は
# race ではなく再現する失敗（path が wedged・repo 破損等）なので
# 永続的理由として数える — 数えないと毎 tick session が起きる
SWEEP_TRANSIENT_REASONS = ("worktree gone", "terminal/agent live")
THREADS_PAGE = 50           # reviewThreads の page size
MAX_PAGES = 20              # ページング暴走の止血帯
PR_ENUM_LIMIT = 100         # search の page size。total > limit*pages は fail-closed
JUDGE_POLICY_VERSION = 9   # bot 依存更新の minor/patch/devDep は script 自動 ok
DISPATCH_MSG_MAX = 3500     # terminal send へ送る指摘一覧の上限 chars
SEND_WAIT_S = 30            # --wait-submit の観測秒
TUI_IDLE_TIMEOUT_MS = 300_000

BOTS = ("dependabot[bot]", "renovate[bot]", "github-actions[bot]",
        "pullfrog[bot]")


def _orca_cmd():
    """sync_automations.py と同じ解決順。Linux で裸の `orca` は GNOME
    screen reader になるので素通ししない。"""
    if os.environ.get("ORCA_CLI_COMMAND"):
        return os.environ["ORCA_CLI_COMMAND"]
    if os.environ.get("ORCA_DEV_REPO_ROOT"):
        return "orca-dev"
    if sys.platform != "darwin":
        return "orca-ide"
    return "orca"


ORCA = _orca_cmd()


def emit(obj):
    print(json.dumps(obj, ensure_ascii=False, indent=1))


def fail(msg, code=1, **kw):
    emit({"ok": False, "error": msg, **kw})
    sys.exit(code)


class ApiError(Exception):
    """gh/orca/API 層の失敗。cmd_* 境界で fail() に変換する。"""


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def _today_jst():
    return datetime.now(JST).strftime("%Y-%m-%d")


def jsonl_path(date=None):
    return ME_REPO / "daily" / (date or _today_jst()) / "pr-watch.jsonl"


def append_event(event, **kw):
    """pr-watch.jsonl へ1行追記。merge record / dispatch / hold / 削除・
    sweep skip / escalate / エラーの実績エントリで、日次 report と監査の材料。"""
    p = jsonl_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"ts": _iso(_now()), "event": event, **kw}
    with p.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def read_events(date=None):
    try:
        text = jsonl_path(date).read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    out = []
    for line in text.splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                out.append({"event": "unparseable", "raw": line[:200]})
    return out


# ---------- state ----------

def load_state():
    """無いファイルは {}。破損は escalate・送信上限の記録を黙って
    消すことになるので、空にせず fail-closed に倒す。"""
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (json.JSONDecodeError, OSError) as e:
        raise ApiError(f"state.json unreadable: {e}")


def save_state(st):
    """state.json の read-modify-write。fcntl.flock を取れる場所はここ —
    run 全体を覆う lock は mkdir lock (LOCK_DIR) で、こちらは同一 host 内の
    RMW 競合だけを潰す短命のクリティカルセクション。"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    lockf = STATE_DIR / "state.lock"
    with lockf.open("w") as lf:
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(st, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, STATE_FILE)
        fcntl.flock(lf.fileno(), fcntl.LOCK_UN)


# ---------- subprocess wrappers ----------

def sh(args, timeout=120):
    try:
        r = subprocess.run(args, capture_output=True, text=True,
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        raise ApiError(f"{args[0]} {args[1] if len(args) > 1 else ''} "
                       f"timed out ({timeout}s)")
    if r.returncode != 0:
        raise ApiError(f"{args[0]} {args[1] if len(args) > 1 else ''} "
                       f"failed({r.returncode}): {r.stderr.strip()[:400]}")
    return r


def gh(args, timeout=120):
    return sh(["gh", *args], timeout=timeout)


def gh_json(args, timeout=120):
    return json.loads(gh(args, timeout=timeout).stdout or "null")


def orca_json(args, timeout=120):
    d = json.loads(sh([ORCA, *args, "--json"], timeout=timeout).stdout or "{}")
    if isinstance(d, dict) and d.get("ok") is False:
        raise ApiError(f"orca {' '.join(args)}: {d.get('error')}")
    return d.get("result", d) if isinstance(d, dict) else d


# ---------- GitHub fetch ----------

def list_open_prs():
    """owner:wwwyo の open PR を全件列挙する。search API は 1000 件 hard
    cap があり、total_count と一致しなければ取り切れていない → fail-closed
    （先頭だけで判定して 51件目以降を見落とすのと同じ失敗を防ぐ）。"""
    items, total = [], None
    for page in range(1, MAX_PAGES + 1):
        d = gh_json(["api", "-X", "GET", "search/issues",
                     "-f", f"q=is:pr is:open owner:{OWNER}",
                     "-f", f"per_page={PR_ENUM_LIMIT}",
                     "-f", f"page={page}"])
        if total is None:
            total = d.get("total_count", 0)
        items.extend(d.get("items") or [])
        if len(items) >= (total or 0):
            break
    if len(items) < (total or 0):
        raise ApiError(f"PR enumeration truncated: got {len(items)} of "
                       f"total_count={total} (search cap)")
    prs = []
    for it in items:
        repo = (it.get("repository_url") or "").rsplit("/", 2)
        name = "/".join(repo[-2:]) if len(repo) >= 2 else None
        if not name:
            continue
        prs.append({"repo": name, "number": it.get("number"),
                    "title": it.get("title"), "url": it.get("html_url"),
                    "author": (it.get("user") or {}).get("login"),
                    "author_type": (it.get("user") or {}).get("type")})
    return prs


def pr_view(repo, number):
    # reviews は gh 内蔵の件数上限で切られ得るので --json からは外し、
    # 必要な経路では pr_reviews() で取り直す（古い CHANGES_REQUESTED が
    # 落ちると unaddressed が消えて fail-open になるため暗黙の上限を使わない）
    return gh_json(["pr", "view", str(number), "--repo", repo, "--json",
                    "number,title,body,author,isDraft,state,mergeable,"
                    "reviewDecision,headRefOid,headRefName,"
                    "baseRefName,baseRefOid,url,comments,commits,"
                    "statusCheckRollup"])


def pr_reviews(repo, number):
    """reviews を REST で全件取る。GraphQL view の reviews 相当の形に
    寄せて返す（unaddressed 判定と author 最終活動に使う）。
    id は REST の integer ではなく node_id を使う — 旧 gh pr view の
    reviews[].id は GraphQL の文字列 id で、sig 生成が文字列連結に
    依存しているため integer のままだと TypeError になる。"""
    out = gh(["api", "-X", "GET",
              f"repos/{repo}/pulls/{number}/reviews",
              "-f", "per_page=100", "--paginate",
              "--jq", '.[] | {id:.node_id,state,'
                      'submittedAt:.submitted_at,body,'
                      'author:{login:.user.login}}'], timeout=180)
    return [json.loads(ln) for ln in out.stdout.splitlines() if ln.strip()]


def pr_files(repo, number):
    """files は `gh pr view --json files` が 100 件で切るので REST で全件
    取る。--paginate はページ毎に別 JSON 配列を出すため --jq で各行に
    潰して受け取る。path 分類は抜けがあると hold/judge 見落とし →
    lane merge の方向に倒れうるので全件必須。

    戻り値は (現存 path 一覧, rename 元 path 一覧)。rename 元は分かれて
    返す必要がある — hold/judge の path 分類には union を掛けて
    `.env` → `config.ts` や `x.lock.yml` → `x.yml` の rename 抜けを塞ぐ
    が、merge 後に存在しない path は test 欠落ルールの「test に触れた」
    証拠に使えない（`tests/x.py` → `src/x.py` の rename 1 件で prod と
    tests が両立してしまう）。"""
    out = gh(["api", "-X", "GET", f"repos/{repo}/pulls/{number}/files",
              "-f", "per_page=100", "--paginate",
              "--jq", '.[] | {f:.filename, p:.previous_filename}'],
             timeout=180)
    files, renamed_from = [], []
    for ln in out.stdout.splitlines():
        if not ln.strip():
            continue
        d = json.loads(ln)
        files.append(d["f"])
        if d.get("p"):
            renamed_from.append(d["p"])
    return files, renamed_from


THREADS_QUERY = """\
query($owner:String!,$name:String!,$num:Int!,$cursor:String){
repository(owner:$owner,name:$name){pullRequest(number:$num){
reviewThreads(first:%d, after:$cursor){
nodes{isResolved isOutdated
comments(first:50){nodes{author{login} body createdAt path line}}}
pageInfo{hasNextPage endCursor}}}}}""" % THREADS_PAGE


def pr_threads(repo, number):
    """reviewThreads を全ページ取る。first:50 の先頭だけで判定すると
    51件目以降の未解消 thread を見落とすので hasNextPage を追い切る。"""
    owner, name = repo.split("/", 1)
    nodes, cursor = [], None
    for _ in range(MAX_PAGES):
        args = ["api", "graphql", "-f", f"query={THREADS_QUERY}",
                "-F", f"owner={owner}", "-F", f"name={name}",
                "-F", f"num={int(number)}"]
        if cursor:
            args += ["-F", f"cursor={cursor}"]
        d = gh_json(args)
        rt = (((d or {}).get("data") or {}).get("repository") or {}) \
            .get("pullRequest", {}).get("reviewThreads") or {}
        nodes.extend(rt.get("nodes") or [])
        pi = rt.get("pageInfo") or {}
        if not pi.get("hasNextPage"):
            return nodes
        cursor = pi.get("endCursor")
        if not cursor:
            raise ApiError(f"{repo}#{number}: reviewThreads cursor empty")
    raise ApiError(f"{repo}#{number}: reviewThreads exceeded "
                   f"MAX_PAGES={MAX_PAGES}")


def required_contexts(repo, base):
    """base branch の required status check contexts。protection 無しは
    []（CI が無い repo ではこの条件自体が無い）。404 以外の失敗は上位へ。
    private repo で Pro 無しだと protection API 自体が 403 を返すが、
    その tier では required check を設定できないので [] が実態と一致する
    — このメッセージ限定で空に倒す。他の 403（rate limit 等）は上位へ。"""
    try:
        d = gh_json(["api",
                     f"repos/{repo}/branches/{base}/protection/"
                     "required_status_checks"], timeout=60)
    except ApiError as e:
        if any(m in str(e) for m in
               ("404", "Not Found", "Upgrade to GitHub Pro")):
            return []
        raise
    ctxs = list(d.get("contexts") or [])
    for c in (d.get("checks") or []):  # 新形式 checks[]={context,app_id}
        if isinstance(c, dict) and c.get("context"):
            ctxs.append(c["context"])
    return sorted(set(ctxs))


TEST_DIR_RE = re.compile(
    r"(^|/)(tests?|__tests__|spec|e2e|testdata|fixtures?)(/|$)",
    re.IGNORECASE)
# ファイル名の convention は basename のみで判定する — `test_` を path 全体に
# 掛けると `latest_token.py`・`contest_handler.py` 等の本番コードが test に
# 誤判定され、hold 免除の抜け道になる
TEST_FILE_RE = re.compile(
    r"\.test\.|\.spec\.|_test\.|^test_.*\.py$|Tests?\.(cs|fs)$",
    re.IGNORECASE)


def is_test_path(path):
    base = path.rsplit("/", 1)[-1]
    return bool(TEST_DIR_RE.search(path) or TEST_FILE_RE.search(base))


def pr_diff(repo, number):
    return gh(["pr", "diff", str(number), "--repo", repo], timeout=180).stdout


# ---------- path 3分類 ----------

# 常に hold — lane・LLM judge とも対象外（PRD「path の3分類」）。
# 内容の良し悪しに関わらず本人の判断に残すポリシー領域。
# .claude/.codex/.pi/.cursor: PRD には「symlink なので tracked file として
# 現れず対象外」とあるが、実際には .claude/agents/reviewer.md のような実
# ファイルと .claude/skills/* の symlink entry が git に乗っている。
# symlink の retarget も agent の振る舞いを変えるので hold 側に入れる。
# .github/workflows/ はこの集合の例外 — dependabot の github-actions
# ecosystem が更新する依存の置き場で、judge 側に回す（is_actions_workflow
# と classify_path のコメント参照）。
HOLD_SEGMENTS = {".github", ".agents", ".claude", ".codex", ".pi",
                 ".cursor", "terraform", ".changeset"}
HOLD_API_SEGMENTS = {"api", "routes", "graphql"}
HOLD_SEGMENT_PREFIXES = ("license", "licence", "notice", "copying",
                         ".release-please")
HOLD_BASENAMES = {"agents.md", "claude.md", "profile.md"}
HOLD_BASENAME_PREFIXES = (".env", "license", "licence", "notice", "copying",
                          "openapi", ".release-please", "release-please",
                          ".releaserc", ".goreleaser")
HOLD_SUFFIXES = (".tf", ".tfvars", ".tfstate", ".proto", ".graphql", ".gql")
# 金銭・セキュリティ関連: path 名の substring 一致。`auth` は `author` や
# `AUTHORS` も拾うが、そちらも機械 merge しない側で害がないので substring
# のままにする（誤検出は hold 側=安全側にしか倒れない）
HOLD_SUBSTRINGS = ("auth", "billing", "payment", "stripe", "checkout",
                   "invoice", "crypto", "permission", "security", "secret")

# 要判定 — LLM judge が内容を見る path。terraform はここに入れず hold 側。
JUDGE_SEGMENTS = {"migrations", "migration", "migrate", "alembic",
                  "prisma", "drizzle", "deploy", "deployment", "docker",
                  "containers", "helm", "k8s", "kubernetes", "cdk",
                  "cloudformation", ".circleci", ".buildkite", "nix"}
JUDGE_BASENAMES = {
    # bot 以外が触る依存 manifest・lockfile
    "package.json", "package-lock.json", "npm-shrinkwrap.json",
    "bun.lock", "bun.lockb", "yarn.lock", "pnpm-lock.yaml",
    "cargo.toml", "cargo.lock", "go.mod", "go.sum",
    "pyproject.toml", "poetry.lock", "uv.lock", "pdm.lock",
    "requirements.txt", "gemfile", "gemfile.lock",
    "composer.json", "composer.lock",
    "mise.toml", ".mise.toml", ".tool-versions", "renovate.json",
    ".nvmrc", ".node-version", ".python-version", ".ruby-version",
    "flake.nix", "flake.lock", "default.nix", "shell.nix",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    "compose.yml", "compose.yaml", "fly.toml", "vercel.json",
    "netlify.toml", "serverless.yml", ".gitlab-ci.yml",
    "jenkinsfile", ".dockerignore", "schema.prisma",
}
JUDGE_BASENAME_PREFIXES = ("dockerfile", "requirements", "jenkinsfile")
JUDGE_SUFFIXES = (".sql", ".nix", ".ipynb")

# bot 依存更新 whitelist の判定に使う「依存 manifest・lockfile」集合
DEP_MANIFEST_BASENAMES = {
    "package.json", "package-lock.json", "npm-shrinkwrap.json",
    "bun.lock", "bun.lockb", "yarn.lock", "pnpm-lock.yaml",
    "cargo.toml", "cargo.lock", "go.mod", "go.sum",
    "pyproject.toml", "poetry.lock", "uv.lock", "pdm.lock",
    "requirements.txt", "gemfile", "gemfile.lock",
    "composer.json", "composer.lock",
    "mise.toml", ".mise.toml", ".tool-versions", "renovate.json",
    ".nvmrc", ".node-version", ".python-version", ".ruby-version",
    "flake.nix", "flake.lock", "default.nix", "shell.nix",
}

MISE_CONFIG_PATHS = {
    ".config/mise/config.toml", "home/dot_config/mise/config.toml",
}

LOCKFILE_BASENAMES = {
    "package-lock.json", "npm-shrinkwrap.json", "bun.lock", "bun.lockb",
    "yarn.lock", "pnpm-lock.yaml", "pnpm-lock.yml", "cargo.lock", "go.sum",
    "poetry.lock", "uv.lock", "pdm.lock", "pipfile.lock", "gemfile.lock",
    "composer.lock", "flake.lock", "mise.lock", "deno.lock",
    "packages.lock.json", "gradle.lockfile", "package.resolved",
    ".terraform.lock.hcl",
}


def is_lockfile(path):
    """依存解決・tool pin の生成 lockfile か。workflow の *.lock.yml は含めない。"""
    return _basename(path.lower()) in LOCKFILE_BASENAMES


def is_dependency_file(path):
    """依存 manifest・tool pin・生成 lockfile の既知の path か。"""
    low = path.lower()
    # config.toml 全体を許可すると、無関係な設定も bot 依存枠に入ってしまう。
    return is_lockfile(low) or _basename(low) in DEP_MANIFEST_BASENAMES or \
        low in MISE_CONFIG_PATHS


def _in_workflows_dir(segs):
    """`.github/workflows/` 直下の file か。subdir 配下は GitHub が
    workflow として実行しないので workflows 扱いしない。"""
    return len(segs) == 3 and segs[:2] == [".github", "workflows"]


def is_actions_workflow(path):
    """GitHub Actions の workflow 定義か。dependabot の github-actions
    ecosystem が更新する依存の置き場なので、bot_dep の whitelist 集合には
    これを加える。生成物の `*.lock.yml`（skillctrl.lock.yml 等）は含めない
    — 生成元との整合が path だけでは保てず hold 側に残す。
    dep-CI repair の `is_dependency_file` には含めない: workflow 自体の変更が
    CI 失敗の原因になりうるため。"""
    segs = _segments(path.lower())
    return _in_workflows_dir(segs) and \
        _suffix(segs[-1]) in (".yml", ".yaml") and \
        not segs[-1].endswith((".lock.yml", ".lock.yaml"))


def review_diff(diff):
    """lockfile の section を除いた全差分。サイズで切らずに返す。"""
    lines = []
    ignored = False
    for line in (diff or "").splitlines(keepends=True):
        if line.startswith("diff --git "):
            try:
                paths = shlex.split(line)[2:]
            except ValueError:
                paths = []
            # rename で code が lockfile 名になっても削除側の内容は確認する。
            ignored = len(paths) == 2 and all(is_lockfile(p) for p in paths)
        if not ignored:
            lines.append(line)
    return "".join(lines)


def pr_context_hash(pr):
    context = {"title": pr.get("title") or "", "body": pr.get("body") or "",
               "base": pr.get("baseRefName"), "base_sha": pr.get("baseRefOid"),
               "checks": sorted(check_rollup(pr),
                                key=lambda c: json.dumps(c, sort_keys=True))}
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()


def current_judge(judge, head, pr):
    """本文・base・check 結果が変わった後に旧判定を使わない。"""
    return judge.get("sha") == head and \
        judge.get("policy_version") == JUDGE_POLICY_VERSION and \
        judge.get("context_hash") == pr_context_hash(pr)


def dependency_repair_classification(cls, pr, judge):
    """依存追従の全差分を judge に戻し、確認済み修正の whitelist を維持する。"""
    if cls["lane"] != "hold" and _is_bot(pr.get("author")) and \
            judge.get("dependency_repair") and \
            judge.get("policy_version") == JUDGE_POLICY_VERSION:
        return dict(cls, lane="judge", dependency_repair=True)
    return cls

# 「それ以外」= 機械的に安全側と分かる path（application code・docs・
# tests・repo 内 config）。この集合にも hold/judge にも入らない拡張子は
# 「分類不能」として judge に倒す（PRD: 分類不能は安全側で judge に倒す）
CODE_SUFFIXES = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts",
    ".go", ".rs", ".rb", ".java", ".kt", ".kts", ".swift", ".c", ".h",
    ".cc", ".cpp", ".hpp", ".cs", ".fs", ".lua", ".sh", ".bash", ".zsh",
    ".fish", ".pl", ".pm", ".ex", ".exs", ".erl", ".hrl", ".clj", ".scala",
    ".hs", ".ml", ".mli", ".r", ".jl", ".nim", ".zig", ".v", ".dart",
    ".groovy", ".php", ".vue", ".svelte", ".astro",
)
DOC_SUFFIXES = (".md", ".mdx", ".txt", ".rst", ".adoc", ".org")
CONF_SUFFIXES = (
    ".json", ".json5", ".jsonc", ".toml", ".yaml", ".yml", ".xml", ".ini",
    ".cfg", ".conf", ".config", ".plist", ".editorconfig", ".gitignore",
    ".gitattributes", ".gitmodules", ".ignore", ".duti", ".csv", ".tsv",
    ".css", ".scss", ".sass", ".less", ".html", ".htm",
)
OTHER_SUFFIXES = CODE_SUFFIXES + DOC_SUFFIXES + CONF_SUFFIXES
# 拡張子の無い既知の repo config basename
OTHER_BASENAMES = {
    "brewfile", "makefile", "rakefile", "justfile", "procfile",
    ".zshrc", ".zprofile", ".zshenv", ".bashrc", ".bash_profile",
    ".profile", ".gitconfig", ".zsh", ".bash",
    "readme", "changelog", "contributing", "codeowners", ".mailmap",
    ".editorconfig", ".prettierrc", ".eslintrc", ".stylelintrc",
    ".markdownlintrc", ".shellcheckrc", ".gitkeep", ".keep",
}


def _segments(path):
    return [s for s in path.split("/") if s]


def _basename(path):
    return path.rsplit("/", 1)[-1]


def _suffix(base):
    """拡張子。`.env` や `.zshrc` のような leading-dot file では ""。"""
    stem, dot, suf = base.rpartition(".")
    return "." + suf if dot and stem else ""


def classify_path(path):
    """1 file path の3分類。戻り値は "hold" | "judge" | "other"。
    未知の拡張子・basename は "judge"（分類不能は安全側）。"""
    if not path or "\x00" in path:
        return "judge"
    low = path.strip().lower()
    segs = _segments(low)
    base = segs[-1] if segs else low
    suffix = _suffix(base)
    test_path = is_test_path(low)

    if is_lockfile(low):
        return "other"

    # 常に hold
    # .github/workflows/ 直下（*.lock.yml を除く）は `.github` セグメントの
    # hold からだけ外して judge に回す — workflow の中身は judge が見る。
    # auth 等の substring・basename による hold は引き続き適用する
    in_workflows = _in_workflows_dir(segs) and \
        not base.endswith((".lock.yml", ".lock.yaml"))
    if any(s in HOLD_SEGMENTS for s in segs
           if not (in_workflows and s == ".github")):
        return "hold"
    if any(s.startswith(HOLD_SEGMENT_PREFIXES) for s in segs):
        return "hold"
    if base in HOLD_BASENAMES or base.startswith(HOLD_BASENAME_PREFIXES):
        return "hold"
    if suffix in HOLD_SUFFIXES or low.endswith(".terraform.lock.hcl"):
        return "hold"
    if not test_path and any(s in HOLD_API_SEGMENTS for s in segs):
        return "hold"
    # workflow 名に test convention（*.test.* 等）が付いていても substring の
    # hold は外さない — `auth.test.yml` は test file ではなく workflow 名
    if (in_workflows or not test_path) and \
            any(k in low for k in HOLD_SUBSTRINGS):
        return "hold"

    # 要判定
    if is_dependency_file(low):
        return "judge"
    if any(s in JUDGE_SEGMENTS for s in segs):
        return "judge"
    if base in JUDGE_BASENAMES or base.startswith(JUDGE_BASENAME_PREFIXES):
        return "judge"
    if suffix in JUDGE_SUFFIXES:
        return "judge"
    if _in_workflows_dir(segs):
        return "judge"

    # それ以外（既知の良性 path）
    if test_path:
        return "other"
    if suffix in OTHER_SUFFIXES or base in OTHER_BASENAMES:
        return "other"
    if not suffix and (low.endswith("rc") or base.startswith(".")):
        # 拡張子なし dotfile（.zshrc 等の rc / .* file）は repo config 側
        return "other"

    # 分類不能 → judge
    return "judge"


BREAKING_TEXT_RE = re.compile(r"BREAKING[ -]CHANGE")
BREAKING_MARKER_RE = re.compile(r"\b[a-zA-Z]+(?:\([^)]*\))?!:")
VERSION_FIELD_RE = re.compile(
    r'^([-+])\s*"?(?:version|"version")"?\s*[:=]\s*["\']?v?(\d+)\.',
    re.MULTILINE)


def breaking_signals(pr, diff):
    """機械的に検出可能な breaking シグナル。検出で「それ以外」を
    要判定扱いに引き上げる（PRD）。返り値は見つかったシグナルの一覧。"""
    sigs = []
    text = "\n".join([pr.get("title") or "", pr.get("body") or ""])
    for c in (pr.get("commits") or []):
        text += "\n" + ((c.get("messageHeadline") or "") + "\n" +
                        (c.get("messageBody") or ""))
    if BREAKING_TEXT_RE.search(text):
        sigs.append("breaking-change-note")
    if BREAKING_MARKER_RE.search(text):
        sigs.append("conventional-bang")
    if diff:
        minus, plus = [], []
        for m in VERSION_FIELD_RE.finditer(diff):
            (minus if m.group(1) == "-" else plus).append(int(m.group(2)))
        if plus and minus and max(plus) > max(minus):
            # version フィールドの major bump（2.x→3.x）。minor/patch は拾わない
            sigs.append("version-major-bump")
    return sigs


def _is_bot(a):
    login = (a or {}).get("login") or ""
    return bool((a or {}).get("is_bot")) or \
        login.endswith("[bot]") or login in BOTS


def classify_pr(files, meta, diff, renamed_from=()):
    """PR 単位の lane 分類。

    files は現存 path、renamed_from は rename で消えた旧 path
    （pr_files の戻り値）。hold/judge の path 分類と bot_dep の whitelist
    は両方の union に掛ける — rename 元の hold path を見ないと rename で
    ポリシー領域を抜ける PR を通す。

    戻り値: {"lane": "hold"|"judge"|"lane", "reasons": [...],
             "classes": {path: class}, "bot_dep_only": bool}
    """
    touched = list(files) + list(renamed_from)
    classes = {f: classify_path(f) for f in touched}
    holds = [f for f, c in classes.items() if c == "hold"]
    judges = [f for f, c in classes.items() if c == "judge"]

    # 1. 常に hold の path が1つでも → どの経路でも merge しない
    if holds:
        return {"lane": "hold", "reasons":
                [f"always-hold path: {f}" for f in holds[:10]],
                "classes": classes, "bot_dep_only": False}

    # テストファイルの追加ではなく、実施した QA を judge が確認する。
    # breaking シグナル → 「それ以外」も judge に引き上げ
    sigs = breaking_signals(meta, review_diff(diff))
    reasons = [f"breaking signal: {s}" for s in sigs]
    if sigs and not judges:
        judges = ["<breaking signal>"]

    # github-actions ecosystem の更新先（.github/workflows/）も依存置き場
    # として whitelist に含める — pullfrog は bot PR を review しないので
    # 含めないと judge ok 後も approval 不在で永久に止まる
    bot_dep_only = _is_bot(meta.get("author")) and bool(touched) and all(
        is_dependency_file(f) or is_actions_workflow(f) for f in touched)
    if bot_dep_only and not judges:
        judges = ["<dependency lockfiles only>"]
    if judges:
        # bot の依存更新のみ → whitelist 判定用フラグ
        reasons += [f"judgment-required path: {f}" for f in judges[:10]]
        return {"lane": "judge", "reasons": reasons, "classes": classes,
                "bot_dep_only": bot_dep_only}

    return {"lane": "lane", "reasons": [], "classes": classes,
            "bot_dep_only": False}


# ---------- bot 依存更新の script 自動 ok ----------

# 自動 ok の判定対象は package.json の依存 section だけ。それ以外の manifest
# （go.mod・mise.toml 等）と workflow には dev/runtime の区分や更新種別を
# 確定できる基準が無いので judge に残す
DEP_SECTIONS = ("dependencies", "devDependencies",
                "peerDependencies", "optionalDependencies")
DEV_DEP_SECTIONS = ("devDependencies",)
DEP_SPEC_RE = re.compile(
    r"^([~^]?)v?(\d+)\.(\d+)\.(\d+)((?:[-+][0-9A-Za-z.\-]+)?)$")


def file_at_ref(repo, path, ref):
    """repo の ref 時点の file 内容を raw で取る。無ければ ApiError。"""
    return gh(["api", "-H", "Accept: application/vnd.github.raw",
               f"repos/{repo}/contents/{path}",
               "-f", f"ref={ref}"], timeout=60).stdout


def _parse_dep_spec(spec):
    """`^1.2.3`・`1.2.3` 形式の単純 semver spec を (prefix, (a,b,c), suffix)
    に分解する。range・protocol・タグなど確定できない形は None。"""
    if not isinstance(spec, str):
        return None
    m = DEP_SPEC_RE.match(spec.strip())
    if not m:
        return None
    return (m.group(1),
            (int(m.group(2)), int(m.group(3)), int(m.group(4))),
            m.group(5))


def dep_bump_kind(old, new):
    """依存 spec の更新を major/minor/patch に分類する。prefix（^/~）の
    変更・suffix 変更・downgrade・range/protocol/タグ等の確定できない
    形は "unknown" — タイトルの自己申告ではなく実 spec の差だけを見る。"""
    o, n = _parse_dep_spec(old), _parse_dep_spec(new)
    if o is None or n is None or o[0] != n[0] or o[2] != n[2]:
        return "unknown"
    if n[1] <= o[1]:
        return "unknown"  # 同 version の記法差・downgrade は確定不能
    if n[1][0] != o[1][0]:
        return "major"
    if n[1][1] != o[1][1]:
        return "minor"
    return "patch"


def package_json_updates(base_text, head_text):
    """base/head の package.json の実差分から依存更新を全件出す。

    戻り値: [{"name","section","from","to","kind"}, ...] または None。
    None = 判定不能（parse 失敗・依存 section 以外の top-level key の
    変更・依存の追加/削除・section が dict でない）。依存以外の差分を
    含む PR を自動 ok にしないため、dep section 以外の変更も None にする。"""
    try:
        base, head = json.loads(base_text), json.loads(head_text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(base, dict) or not isinstance(head, dict):
        return None
    changed = [k for k in set(base) | set(head)
               if base.get(k) != head.get(k)]
    if any(k not in DEP_SECTIONS for k in changed):
        return None
    updates = []
    for sec in DEP_SECTIONS:
        b, h = base.get(sec) or {}, head.get(sec) or {}
        if not isinstance(b, dict) or not isinstance(h, dict) or \
                set(b) != set(h):
            return None
        for name in sorted(b):
            if b[name] == h[name]:
                continue
            updates.append({"name": name, "section": sec,
                            "from": b[name], "to": h[name],
                            "kind": dep_bump_kind(b[name], h[name])})
    return updates


def dep_auto_ok(repo, facts):
    """bot 依存更新のみの PR が script 側の自動 ok 対象かを、base/head の
    実 manifest 差分から判定する。LLM judge を介さず ok とみなせるのは
    全更新が minor/patch または devDependencies（major 含む）と確定できた
    場合だけ — runtime major・確定不能・依存以外の差分を含むものは
    eligible=False で従来の judge 経路に残す。grouped PR は manifest の
    直接更新を全件見る（1件でも対象外なら全体が対象外）。

    戻り値: {"eligible": bool, "updates": [...], "reasons": [...]}"""
    out = {"eligible": False, "updates": [], "reasons": []}
    v = facts["view"]
    if facts.get("renamed_from"):
        # rename 元と head 側 path の対応が取れないと base の正しい参照を
        # 組めないので判定不能
        out["reasons"].append("dependency file renamed")
        return out
    updates = []
    for path in facts.get("files") or []:
        if is_lockfile(path):
            continue  # lockfile は内容判定の対象外（manifest の写像）
        if _basename(path.lower()) != "package.json":
            out["reasons"].append(f"unclassifiable manifest: {path}")
            return out
        try:
            base = file_at_ref(repo, path, v.get("baseRefOid"))
            head = file_at_ref(repo, path, v.get("headRefOid"))
        except ApiError as e:
            out["reasons"].append(f"manifest unreadable: {path} ({e})")
            return out
        ups = package_json_updates(base, head)
        if ups is None:
            out["reasons"].append(
                f"non-dependency or unparsable change: {path}")
            return out
        updates += [dict(u, file=path) for u in ups]
    if not updates:
        # lockfile のみ等、更新種別を確定できる manifest が無い
        out["reasons"].append("no dependency updates found")
        return out
    out["updates"] = updates
    for u in updates:
        spec = f"{u['name']} {u['from']} -> {u['to']}"
        if u["kind"] == "unknown":
            out["reasons"].append(f"unresolved version spec: {spec}")
        elif u["kind"] == "major" and u["section"] not in DEV_DEP_SECTIONS:
            out["reasons"].append(f"runtime major update: {spec}")
    out["eligible"] = not out["reasons"]
    return out


def dep_auto_ok_eligible(dep_auto, judge, head, pr):
    """script 自動 ok が実際に ok 相当になるか。現在 head・判定材料に
    紐付いた ng/repair の judge verdict があるときは自動 ok で上書き
    しない（fail-closed — 文脈が変われば verdict は外れて自動 ok に戻る）。"""
    if not (dep_auto and dep_auto["eligible"]):
        return False
    j = judge or {}
    if current_judge(j, head, pr) and j.get("verdict") in ("ng", "repair"):
        return False
    return True


# ---------- unaddressed review ----------

def author_last_activity(pr):
    """author の最終活動（push・返信）。thread resolve の時刻は API から
    取れないので、head commit の committedDate と author の
    comment/review の最新を使う。"""
    author = (pr.get("author") or {}).get("login")
    latest = None
    for c in (pr.get("commits") or []):
        t = _ts(c.get("committedDate"))
        if t and (latest is None or t > latest):
            latest = t
    for c in (pr.get("comments") or []):
        if (c.get("author") or {}).get("login") != author:
            continue
        t = _ts(c.get("createdAt"))
        if t and (latest is None or t > latest):
            latest = t
    for rv in (pr.get("reviews") or []):
        if (rv.get("author") or {}).get("login") != author:
            continue
        t = _ts(rv.get("submittedAt"))
        if t and (latest is None or t > latest):
            latest = t
    return latest


def unaddressed_items(pr, threads):
    """未解消 thread + 最終活動より新しい CHANGES_REQUESTED。
    返り値は dispatch メッセージと dedup 署名に使う item dict の list。
    thread dict 全体が署名に入るので、未解消 thread への返信追加や
    isOutdated の反転は新しい署名 = 再 dispatch 対象になる（isOutdated は
    未解消として残す側に倒す — 古い diff 上の指摘でも未解消なら安全側）。"""
    items = []
    for t in threads:
        if t.get("isResolved"):
            continue
        cs = ((t.get("comments") or {}).get("nodes")) or []
        first = cs[0] if cs else {}
        items.append({
            "kind": "thread",
            "author": ((first.get("author") or {}).get("login")),
            "path": first.get("path") or "",
            "line": first.get("line"),
            "body": (first.get("body") or "")[:600],
            "sig": "t:" + hashlib.sha1(
                json.dumps(t, sort_keys=True).encode()).hexdigest()[:12],
        })
    last_act = author_last_activity(pr)
    for rv in (pr.get("reviews") or []):
        if rv.get("state") != "CHANGES_REQUESTED":
            continue
        sub = _ts(rv.get("submittedAt"))
        if sub and last_act and sub <= last_act:
            continue  # 既に author の活動で応答済み
        items.append({
            "kind": "changes_requested",
            "author": ((rv.get("author") or {}).get("login")),
            "path": "", "line": None,
            "body": (rv.get("body") or "")[:600],
            "sig": "r:" + str(rv.get("id") or hashlib.sha1(
                json.dumps(rv, sort_keys=True,
                           default=str).encode()).hexdigest()[:12]),
            "submittedAt": rv.get("submittedAt"),
        })
    return items


def unaddressed_sig(items):
    return hashlib.sha1("|".join(sorted(i["sig"] for i in items))
                        .encode()).hexdigest()[:16]


def dispatch_items(repo, number, facts, state=None):
    """レビュー指摘と、author session で調査・修正する障害をまとめる。"""
    v = facts["view"]
    if (v.get("state") or "").upper() != "OPEN":
        return []
    items = unaddressed_items(v, facts["threads"])
    judge = ((state or {}).get("judge") or {}).get(pr_key(repo, number)) or {}
    if current_judge(judge, v.get("headRefOid"), v) and \
            judge.get("verdict") == "repair" and judge.get("dependency_repair"):
        items.append({"kind": "dependency_migration", "body": judge["reason"],
                      "sig": "dependency_migration:" + judge["sha"] + ":" +
                      hashlib.sha1(judge["reason"].encode()).hexdigest()[:16]})
    if (v.get("mergeable") or "").upper() == "CONFLICTING":
        items.append({"kind": "conflict", "body":
                      "PR の base との機械的な競合解消を試みる。",
                      "sig": "conflict:" + str(v.get("baseRefOid") or "")})
    chk = required_check_state(check_rollup(v), facts["required"])
    failing = sorted(set(chk["failing"] + chk["nonrequired_failing"])
                     - {"pullfrog-approval"})
    if failing and _is_bot(v.get("author")):
        if facts.get("files") is None:
            facts["files"], facts["renamed_from"] = pr_files(repo, number)
        # bot が触った CI 全般ではなく、依存 manifest の更新だけを対象にする。
        # rename 元も含める（dep 以外が rename に関わるなら dep-only ではない）
        files = (facts["files"] or []) + (facts.get("renamed_from") or [])
        if files and all(is_dependency_file(p) for p in files):
            items.append({"kind": "dependency_ci", "body":
                          "依存更新の CI 失敗を調査する: " + ", ".join(failing),
                          "sig": "dependency_ci:" + "|".join(failing)})
    return items


# ---------- checks ----------

def check_rollup(pr):
    """statusCheckRollup を均一な check dict に正規化する。
    statusCheckRollup は head commit スコープなので、この集合は
    「現在 head の check 群」として扱える。"""
    checks = []
    for c in (pr.get("statusCheckRollup") or []):
        if c.get("__typename") == "CheckRun":
            checks.append({
                "name": c.get("name"), "kind": "CheckRun",
                "status": (c.get("status") or "").upper(),
                "conclusion": (c.get("conclusion") or "").upper(),
                "required": c.get("isRequired"),
                "url": c.get("detailsUrl"),
            })
        elif c.get("__typename") == "StatusContext":
            checks.append({
                "name": c.get("context"), "kind": "StatusContext",
                "status": (c.get("state") or "").upper(),
                "conclusion": (c.get("state") or "").upper(),
                "required": c.get("isRequired"),
                "url": c.get("targetUrl"),
            })
    return checks


def pullfrog_approval(checks):
    """pullfrog-approval が現在 head で success か。（check が無い・
    pending・failure は全て False）"""
    for c in checks:
        if c["name"] == "pullfrog-approval":
            return (c["status"] == "COMPLETED" and
                    c["conclusion"] == "SUCCESS"), \
                c["conclusion"] or c["status"]
    return False, None


def required_check_state(checks, required):
    """required context の状態集約。missing = protection にあるのに
    head に check が無い（pending 相当=安全側）。nonrequired_failing は
    ブロックしないが merge record に残す（PRD §CI）。"""
    by_name = {c["name"]: c for c in checks}
    failing, pending, missing, ok = [], [], [], []
    for ctx in required:
        c = by_name.get(ctx)
        if c is None:
            missing.append(ctx)
            continue
        st = c["status"]
        conc = c["conclusion"]
        if st == "COMPLETED":
            if conc in ("SUCCESS", "NEUTRAL", "SKIPPED"):
                ok.append(ctx)
            else:
                failing.append(ctx)
        elif st in ("SUCCESS", "NEUTRAL", "SKIPPED"):
            ok.append(ctx)
        elif st in ("FAILURE", "ERROR", "CANCELLED", "ACTION_REQUIRED",
                    "STARTUP_FAILURE", "TIMED_OUT"):
            failing.append(ctx)
        else:  # PENDING/QUEUED/IN_PROGRESS/EXPECTED/WAITING
            pending.append(ctx)
    req = set(required)
    nonreq_fail = [c["name"] for c in checks
                   if c["name"] not in req
                   and c["name"] != "pullfrog-approval"
                   and c["conclusion"] in
                   ("FAILURE", "ERROR", "CANCELLED", "TIMED_OUT",
                    "STARTUP_FAILURE", "ACTION_REQUIRED")]
    return {"failing": failing, "pending": pending, "missing": missing,
            "ok": ok, "nonrequired_failing": nonreq_fail}


# ---------- hard gate ----------

def hard_gate(facts, judge=None, via="lane", expect_sha=None):
    """merge 発行直前の再検証。全件を fresh facts から判定する。

    facts: {"view": pr_view, "files": [...], "renamed_from": [...],
            "threads": [...], "required": [...],
            "diff": str|None}
    judge: {"sha":..,"verdict":..}|None — state に記録された judge 判定
    via: "lane" のみ。pullfrog-approval + path 分類 + judge verdict を要求。

    戻り値: (ok, reasons)。reasons は NG 理由（ok 時は空）。"""
    if via != "lane":
        return False, ["unsupported merge route: " + str(via)]
    pr = facts["view"]
    r = []
    if (pr.get("state") or "").upper() != "OPEN":
        return False, [f"state is {pr.get('state')}"]
    head = pr.get("headRefOid")
    if expect_sha and head and head != expect_sha:
        return False, [f"head moved: expected {expect_sha[:8]}, "
                       f"now {head[:8]}"]
    mergeable = (pr.get("mergeable") or "").upper()
    if mergeable != "MERGEABLE":
        r.append(f"mergeable={mergeable or 'UNKNOWN'}")
    rd = (pr.get("reviewDecision") or "").upper()
    if rd == "CHANGES_REQUESTED":
        r.append("reviewDecision=CHANGES_REQUESTED")
    items = unaddressed_items(pr, facts["threads"])
    if items:
        r.append(f"unaddressed reviews: {len(items)}")
    roll = check_rollup(pr)
    chk = required_check_state(roll, facts["required"])
    if chk["failing"]:
        r.append(f"required check failing: {','.join(chk['failing'])}")
    if chk["pending"] or chk["missing"]:
        r.append(f"required check pending/missing: "
                 f"{','.join(chk['pending'] + chk['missing'])}")

    if via == "lane":
        # author は不変だが、merge が唯一の発行経路である以上 hard gate
        # が全条件を再検証する（PRD の hard gate 定義に author 条件を含む）
        if not _author_eligible(pr):
            r.append("author not eligible for lane")
        # files/diff は遅延取得 — merge 時も diff を見るので
        # version-major-bump 等の breaking signal が gate 時分類と
        # 同じ材料で再評価される
        ensure_facts(facts.get("repo") or "", pr.get("number"), facts)
        cls = dependency_repair_classification(
            classify_pr(facts["files"], pr, facts.get("diff"),
                        facts.get("renamed_from") or ()),
            pr, judge or {})
        facts["cls"] = cls  # merge 側の event 記録が同じ分類を再利用する
        if cls["lane"] == "hold":
            r += ["lane=hold: " + x for x in cls["reasons"]]
        j = judge or {}
        jok = j.get("verdict") == "ok" and current_judge(j, head, pr)
        # script 自動 ok は gate と同じ基準を merge 直前の live facts から
        # 引き直す — gate 時の判定を持ち越さない
        dep_auto = dep_auto_ok(facts.get("repo") or "", facts) \
            if cls.get("bot_dep_only") else None
        facts["dep_auto_ok"] = dep_auto  # merge の event 記録が再利用する
        auto_ok = dep_auto_ok_eligible(dep_auto, j, head, pr)
        if not (jok or auto_ok):
            r.append("no QA/Blast Radius judge ok or dependency auto-ok "
                     "bound to current head and evidence")
        # bot 依存更新・確認済み追従の whitelist 経路は pullfrog-approval を要求しない
        # （pullfrog は非 collaborator の bot PR を review しないため check が
        # 付かない）。script 自動 ok と有効な judge ok の両方で免除が効く。
        # それ以外の lane merge は全て approval 必須。
        need_app = not ((cls["bot_dep_only"] or
                         cls.get("dependency_repair")) and (jok or auto_ok))
        ok_app, app_state = pullfrog_approval(roll)
        if need_app and not ok_app:
            r.append(f"pullfrog-approval not success"
                     f" ({app_state or 'absent'})")
    return (not r), r


# ---------- Orca ----------

def worktree_ps():
    res = orca_json(["worktree", "ps"])
    if res.get("truncated"):
        raise ApiError("Orca worktree inventory incomplete")
    return (res or {}).get("worktrees") or []


def terminal_list(wtid):
    res = orca_json(["terminal", "list", "--worktree", wtid])
    if res.get("truncated"):
        raise ApiError("Orca terminal inventory incomplete")
    return (res or {}).get("terminals") or []


def _short_branch(b):
    return b.removeprefix("refs/heads/") if b else b


def find_worktree(worktrees, repo, number, head_ref):
    """dispatch routing: linkedPR.number → branch == headRef の順。
    戻り値 (worktree, how)。見つからなければ (None, None)。"""
    repo_name = repo.split("/")[-1]
    cands = [w for w in worktrees if w.get("repo") == repo_name]
    for w in cands:
        lp = w.get("linkedPR") or {}
        if lp.get("number") == number and (lp.get("state") or "") == "open":
            return w, "linkedPR"
    if head_ref:
        for w in cands:
            if _short_branch(w.get("branch")) == head_ref:
                return w, "branch"
    return None, None


def agent_terminal(terminals):
    """agent TUI と思われる terminal（agentIdentity 付き・writable）を返す。
    複数なら先頭の1つ — dual send を避けるため必ず単一 handle。"""
    cands = [t for t in terminals
             if t.get("agentIdentity") and t.get("writable", True)
             and t.get("connected", True)]
    return cands[0] if cands else None


def agent_busy(worktree, terminals):
    """author が作業中なら dispatch しない（次 tick に回す）。
    status=working または agents[].state==working。"""
    if (worktree.get("status") or "") == "working":
        return True
    return any(a.get("state") == "working"
               for a in (worktree.get("agents") or []))


def _author_eligible(pr):
    """dispatch/spawn の author 条件: wwwyo または bot のみ。
    それ以外の author の PR には dispatch も spawn もしない（PRD）。"""
    a = pr.get("author") or {}
    return (a.get("login") or "") == OWNER or _is_bot(a)


def route_dispatch(worktrees, terminals_by_wt, repo, pr):
    """dispatch のルーティング決定（純粋判定部）。pr は pr_view の dict
    （author・number・headRefName を使う）。

    戻り値: {"route": "send"|"revive"|"spawn"|"defer"|"none",
             "worktree": w|None, "handle": h|None, "reason": str}
    """
    if not _author_eligible(pr):
        return {"route": "none", "worktree": None, "handle": None,
                "reason": "author not eligible for dispatch/spawn"}

    head = pr.get("headRefName")
    w, how = find_worktree(worktrees, repo, pr.get("number"), head)
    if w is None:
        # head branch を checkout 済みの worktree は branch fallback で
        # 上で拾えているはず — ここに来た時点で同 repo に head branch 占有は
        # 無いので spawn してよい
        return {"route": "spawn", "worktree": None, "handle": None,
                "reason": "no session; author eligible for spawn"}

    terms = terminals_by_wt.get(w.get("worktreeId"), [])
    if agent_busy(w, terms):
        return {"route": "defer", "worktree": w, "handle": None,
                "reason": "agent working"}

    t = agent_terminal(terms)
    if t:
        return {"route": "send", "worktree": w, "handle": t["handle"],
                "reason": f"matched via {how}; agent idle/done"}
    return {"route": "revive", "worktree": w, "handle": None,
            "reason": f"matched via {how}; no agent terminal"}


# ---------- dispatch state ----------

def pr_key(repo, number):
    return f"{repo}#{number}"


def dispatch_state(state, repo, number):
    """write path 用: entry を作って返す。"""
    prs = state.setdefault("prs", {})
    return prs.setdefault(pr_key(repo, number),
                          {"dispatches": [], "rounds": [], "escalated": False})


def get_dispatch_state(state, repo, number):
    """read path 用: entry が無ければ default を返すが state には書かない
    （setdefault すると列挙した全 PR の空 entry が state.json に残り続ける）。"""
    return (state.get("prs") or {}).get(pr_key(repo, number)) or \
        {"dispatches": [], "rounds": [], "escalated": False}


def dispatch_allows(ds, head):
    """上限判定。戻り値 (allowed, reason, escalate)。
    同一 (PR, head) への送信は DISPATCH_MAX_PER_HEAD 回まで。
    dispatch を送った異なる head の数（往復ラウンド）が
    DISPATCH_MAX_ROUNDS に達したら打ち切り。上限到達は「機械的往復で
    解消しない」サインなので escalation で人間に回す。"""
    if ds.get("escalated"):
        return False, "escalated", False
    same_head = [d for d in ds.get("dispatches", []) if d.get("sha") == head]
    if len(same_head) >= DISPATCH_MAX_PER_HEAD:
        return False, f"dispatch cap per head ({DISPATCH_MAX_PER_HEAD})", True
    rounds = ds.get("rounds") or []
    if head in rounds or len(rounds) < DISPATCH_MAX_ROUNDS:
        return True, "", False
    return False, f"dispatch rounds cap ({DISPATCH_MAX_ROUNDS})", True


def dispatch_already_sent(ds, head, sig):
    return any(d.get("sha") == head and d.get("sig") == sig
               for d in ds.get("dispatches", []))


def mark_dispatch_sent(state, repo, number, head, sig):
    ds = dispatch_state(state, repo, number)
    ds.setdefault("dispatches", []).append(
        {"sha": head, "sig": sig, "at": _iso(_now())})
    ds["stale_ticks"] = 0  # 新しい指摘へ送ったので滞留カウントは戻す
    rounds = ds.setdefault("rounds", [])
    if head and head not in rounds:
        rounds.append(head)


# ---------- dispatch message ----------

def build_dispatch_message(repo, pr, items):
    lines = [
        "[pr-merge-lane] PR の対応を依頼します: "
        f"{pr.get('url')}",
        f"repo: {repo} PR #{pr.get('number')} "
        f"「{pr.get('title') or ''}」",
        "",
        "まず各指摘が妥当かを判断してください。採用しないものは理由を書いて"
        "返信し、thread を resolve してください（レビュー指摘を常に採用する"
        "わけではありません）。merge はこちらで行うので不要です。",
        "",
        "未対応の指摘・障害:",
    ]
    if any(it["kind"] in ("conflict", "dependency_ci", "dependency_migration")
           for it in items):
        lines += [
            "競合・依存更新の CI 失敗・major 更新への追従は "
            "~/.agents/skills/pr-auto-merge/references/repair.md を読んで処理する。",
            "該当 PR・base・失敗ログだけを調べる。機械的な追従以外は hold。"
            "cooldown は rerun・回避しない。push 前に OPEN と head を再確認する。"
            "修正後は PR に根拠を書き、merge せず次 tick に返す。", "",
        ]
    for i, it in enumerate(items, 1):
        loc = f" {it['path']}:{it['line']}" if it.get("path") else ""
        who = f" ({it['author']})" if it.get("author") else ""
        body = re.sub(r"\s+", " ", it.get("body") or "").strip()[:400]
        lines.append(f"{i}. [{it['kind']}]{loc}{who} {body}")
    msg = "\n".join(lines)
    if len(msg) > DISPATCH_MSG_MAX:
        msg = msg[:DISPATCH_MSG_MAX - 60] + \
            "\n... (省略 — 残りは PR の review thread を参照)"
    return msg


# ---------- send / spawn ----------

def _find_request_id(detail):
    """terminal send receipt から --retry-request 用の request id を探す。"""
    if not isinstance(detail, dict):
        return None
    for k in ("requestId", "request_id", "id"):
        if detail.get(k):
            return detail[k]
    for v in detail.values():
        if isinstance(v, dict):
            rid = _find_request_id(v)
            if rid:
                return rid
    return None


def send_prompt(handle, text):
    """terminal send --wait-submit で turn_started まで観測する。
    既定 receipt は入力受理のみを示すので turn_started を見る。
    timeout/受理止まりは未配信扱い（dispatch カウントを進めず次 tick で
    再送対象になる）。輸送層が曖昧な失敗を返した場合は receipt の
    --retry-request id で冪等に再送する。"""
    res, err = None, None
    try:
        res = orca_json(["terminal", "send", "--terminal", handle,
                         "--text", text, "--enter",
                         "--wait-submit", str(SEND_WAIT_S)], timeout=90)
    except ApiError as e:
        err = str(e)
    blob = json.dumps(res or {}, ensure_ascii=False)
    if "turn_started" in blob:
        return True, res
    rid = _find_request_id(res or {})
    if rid:
        try:
            res2 = orca_json(["terminal", "send", "--terminal", handle,
                              "--text", text, "--enter",
                              "--wait-submit", str(SEND_WAIT_S),
                              "--retry-request", rid], timeout=90)
            if "turn_started" in json.dumps(res2, ensure_ascii=False):
                return True, res2
            return False, res2
        except ApiError as e2:
            return False, {"error": str(e2), "retry_request": rid}
    return False, res or {"error": err}


def spawn_worktree(repo_name, number, head_ref):
    """専用 worktree を立てて devin agent を起動し (handle, path, wtid) を
    返す。devin は --prompt を TUI ready 前に送ると入力が消失するので
    （--agent のみで起動 → wait tui-idle → send）の手順を取る。
    head branch は作成した worktree 内で checkout する。"""
    name = f"pr{number}-review"
    try:
        res = orca_json(["worktree", "create", "--repo", f"name:{repo_name}",
                         "--name", name, "--agent", "devin"], timeout=300)
    except ApiError as e:
        # repo 未登録 (repo_not_found) のときだけ登録して再試行する
        # （~/src/github.com/wwwyo/<name> が個人 repo の規約 path）。
        # timeout 等の非回復エラーで再試行すると原因を覆い隠すので絞る
        if "repo_not_found" not in str(e):
            raise
        canonical = Path.home() / "src" / "github.com" / "wwwyo" / repo_name
        if not canonical.is_dir():
            raise
        orca_json(["repo", "add", "--path", str(canonical)], timeout=60)
        res = orca_json(["worktree", "create", "--repo",
                         f"name:{repo_name}", "--name", name,
                         "--agent", "devin"], timeout=300)
    wt = (res or {}).get("worktree") or {}
    wtid = wt.get("id") or wt.get("worktreeId")
    path = wt.get("path") or (wtid or "").split("::", 1)[-1]
    handle = ((res or {}).get("startupTerminal") or {}).get("handle")
    if not wtid or not path:
        raise ApiError(f"worktree create returned no path: {res}")
    if not handle:
        for t in terminal_list(wtid):
            if t.get("agentIdentity"):
                handle = t["handle"]
                break
    if not handle:
        raise ApiError("worktree created but no agent terminal handle")

    # head branch を checkout（他 worktree で checkout 済みでないことは
    # gate 側で確認済み。ここでの失敗は spawn 失敗として上位へ）
    sh(["git", "-C", path, "fetch", "origin", head_ref], timeout=120)
    r = subprocess.run(["git", "-C", path, "checkout", head_ref],
                       capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        # local branch が無い/既存で拾えないなら FETCH_HEAD から作る
        r = subprocess.run(
            ["git", "-C", path, "checkout", "-b", head_ref, "FETCH_HEAD"],
            capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            raise ApiError(f"checkout {head_ref} failed: "
                           f"{r.stderr.strip()[:300]}")
    # remote 側が進んでいるなら fast-forward だけ追従する（merge commit は
    # 作らない — local 実体が残っている場合の分岐は動かさない）
    subprocess.run(["git", "-C", path, "merge", "--ff-only", "FETCH_HEAD"],
                   capture_output=True, text=True, timeout=60)
    return handle, path, wtid


def wait_tui_idle(handle):
    try:
        res = orca_json(["terminal", "wait", "--terminal", handle,
                         "--for", "tui-idle",
                         "--timeout-ms", str(TUI_IDLE_TIMEOUT_MS)],
                        timeout=TUI_IDLE_TIMEOUT_MS / 1000 + 60)
    except ApiError as e:
        return False, {"error": str(e)}
    w = (res or {}).get("wait") or res or {}
    return bool(w.get("satisfied")), res


# ---------- plan / tick ----------

def pr_facts(repo, number, base_cache):
    """gate/merge 共通の事実収集。files/diff は遅延 — unaddressed
    や早期 hold で classify に届かない PR 分の API call を省く（None = 未取得。
    ensure_facts が使用直前に埋める）。required はほぼ全経路で必要なので
    ここで取る。"""
    v = pr_view(repo, number)
    v["reviews"] = pr_reviews(repo, number)
    base = v.get("baseRefName") or "main"
    if (repo, base) not in base_cache:
        base_cache[(repo, base)] = required_contexts(repo, base)
    return {
        "repo": repo,
        "view": v,
        "files": None,
        "renamed_from": None,
        "threads": pr_threads(repo, number),
        "required": base_cache[(repo, base)],
        "diff": None,
    }


def ensure_facts(repo, number, facts):
    """files/diff の遅延取得。classify が要る経路に進んだ PR で
    だけ呼ぶ。None = 未取得として取得する（注入済みの値はそのまま使う）。
    取得失敗はそのまま ApiError — gate/merge の fail-closed に載せる。"""
    if facts.get("files") is None:
        facts["files"], facts["renamed_from"] = pr_files(repo, number)
    touched = (facts["files"] or []) + (facts.get("renamed_from") or [])
    if any(classify_path(p) == "hold" for p in touched):
        return
    if facts.get("diff") is None:
        facts["diff"] = pr_diff(repo, number)


def compute_pr_decision(pr, facts, worktrees, terms_cache, state):
    """1 PR 分の action 決定（gate の中核）。戻り値は plan の1エントリ分。"""
    repo, num = pr["repo"], pr["number"]
    v = facts["view"]
    head = v.get("headRefOid")
    entry = {"repo": repo, "number": num, "title": v.get("title"),
             "url": v.get("url"), "head": head,
             "author": (v.get("author") or {}).get("login"),
             "actions": []}
    if (v.get("state") or "").upper() != "OPEN":
        entry["note"] = f"state {v.get('state')} (raced with enumeration)"
        return entry

    items = dispatch_items(repo, num, facts, state)
    sig = unaddressed_sig(items) if items else ""
    ds = get_dispatch_state(state, repo, num)

    # --- dispatch（指摘・競合・依存 CI の対応を merge 判定より先に行う） ---
    if items:
        entry["dispatch_kinds"] = sorted({it["kind"] for it in items})
        allowed, why, escalate = dispatch_allows(ds, head)
        if ds.get("escalated"):
            entry["actions"].append({"type": "hold",
                                     "reason": "escalated previously"})
        elif escalate:
            entry["actions"].append({"type": "escalate",
                                     "reason": why,
                                     "items": len(items)})
        elif allowed:
            if dispatch_already_sent(ds, head, sig):
                # 同じ指摘が残ったままの滞留も往復の一種 — session が
                # 応答しない場合に限りなく hold し続けないよう tick を数えて
                # 上限で escalate する
                dsm = dispatch_state(state, repo, num)
                dsm["stale_ticks"] = int(dsm.get("stale_ticks") or 0) + 1
                if dsm["stale_ticks"] >= DISPATCH_STALE_TICKS:
                    entry["actions"].append({
                        "type": "escalate",
                        "reason": "dispatch items persist "
                                  f"{dsm['stale_ticks']} ticks after dispatch",
                        "items": len(items)})
                else:
                    entry["actions"].append({
                        "type": "hold",
                        "reason": "already dispatched for this head+items "
                                  f"(stale {dsm['stale_ticks']}/"
                                  f"{DISPATCH_STALE_TICKS})"})
            else:
                w, _how = find_worktree(worktrees, repo, num,
                                        v.get("headRefName"))
                if w and w.get("worktreeId") not in terms_cache:
                    terms_cache[w["worktreeId"]] = terminal_list(
                        w["worktreeId"])
                route = route_dispatch(worktrees, terms_cache, repo, v)
                if route["route"] in ("none", "defer"):
                    # none（author 非対象）は永続、defer（作業中）は次 tick で
                    # 再評価 — どちらも dispatch subcommand が no-op で終わる
                    # だけなので、session 起動コストを払わず hold にする
                    entry["actions"].append(
                        {"type": "hold", "reason": route["reason"]})
                else:
                    entry["actions"].append({
                        "type": "dispatch", "route": route["route"],
                        "reason": route["reason"],
                        "worktree":
                            (route["worktree"] or {}).get("worktreeId"),
                        "handle": route.get("handle"),
                        "items": len(items), "sig": sig})
        else:
            entry["actions"].append({"type": "hold", "reason": why})
        # 対応すべき障害がある限り lane 判定に進まない
        return entry

    # --- lane merge 候補判定 ---
    rd = (v.get("reviewDecision") or "").upper()
    if rd == "CHANGES_REQUESTED":
        entry["actions"].append({"type": "hold",
                                 "reason": "reviewDecision="
                                           "CHANGES_REQUESTED"})
        return entry
    mergeable = (v.get("mergeable") or "").upper()
    if mergeable != "MERGEABLE":
        entry["actions"].append({"type": "hold",
                                 "reason": f"mergeable={mergeable or '?'}"})
        return entry
    roll = check_rollup(v)
    chk = required_check_state(roll, facts["required"])
    if chk["failing"]:
        entry["actions"].append({"type": "hold", "reason":
            f"required check failing: {','.join(chk['failing'])}"})
        return entry
    if chk["pending"] or chk["missing"]:
        entry["actions"].append({"type": "hold", "reason":
            "required check pending/missing: "
            f"{','.join(chk['pending'] + chk['missing'])}"})
        return entry
    if not _author_eligible(v):
        entry["actions"].append({"type": "hold", "reason":
                                 f"author {v.get('author', {}).get('login')}"
                                 " ineligible for lane"})
        return entry

    ensure_facts(repo, num, facts)
    j = (state.get("judge") or {}).get(pr_key(repo, num)) or {}
    repaired = j.get("dependency_repair")
    cls = dependency_repair_classification(
        classify_pr(facts["files"], v, facts.get("diff"),
                    facts.get("renamed_from") or ()), v, j)
    entry["lane"] = cls["lane"]
    entry["lane_reasons"] = cls["reasons"]
    entry["bot_dep_only"] = cls["bot_dep_only"]
    if cls["lane"] == "hold":
        entry["actions"].append({"type": "hold",
                                 "reason": "; ".join(cls["reasons"])})
        return entry

    jok = j.get("verdict") == "ok" and current_judge(j, head, v)
    # bot 依存更新のみの PR: 実 manifest 差分から全更新が minor/patch・
    # devDependencies（major 含む）と確定できるものは LLM judge を介さず
    # script が自動 ok とする。確定できない更新・runtime major は judge へ。
    dep_auto = dep_auto_ok(repo, facts) if cls["bot_dep_only"] else None
    auto_ok = dep_auto_ok_eligible(dep_auto, j, head, v)
    if dep_auto is not None:
        entry["dep_auto_ok"] = dep_auto["eligible"]
    if not (jok or auto_ok):
        if current_judge(j, head, v):
            entry["actions"].append({"type": "hold",
                                     "reason": "judge " + j.get("verdict", "ng") + ": "
                                               f"{j.get('reason')}"})
            return entry
        reasons = cls["reasons"]
        if dep_auto is not None:
            reasons = dep_auto["reasons"] + reasons
        entry["actions"].append({"type": "judge", "head": head,
                                 "whitelist_hint":
                                 "bot_dep_repair" if repaired else
                                 "bot_dep" if cls["bot_dep_only"]
                                 else "risk_review",
                                 "reasons": reasons +
                                 ["QA and Blast Radius assessment required"]})
        return entry

    # lane / ok 共通: pullfrog-approval（bot_dep または確認済み追従で
    # judge ok・script 自動 ok の経路のみ免除）
    ok_app, app_state = pullfrog_approval(roll)
    if not ((cls["bot_dep_only"] or cls.get("dependency_repair"))
            and (jok or auto_ok)) and not ok_app:
        entry["actions"].append({"type": "hold", "reason":
            f"pullfrog-approval not success ({app_state or 'absent'})"})
        return entry
    action = {"type": "merge", "via": "lane", "head": head,
              "bot_dep_only": cls["bot_dep_only"],
              "dependency_repair": bool(cls.get("dependency_repair")),
              "dep_auto_ok": auto_ok,
              "nonrequired_failing": chk["nonrequired_failing"]}
    if auto_ok:
        action["dep_updates"] = dep_auto["updates"]
    entry["actions"].append(action)
    return entry


def sweep_candidates(state, worktrees):
    """merge 済み PR の local worktree 削除候補。git と session は削除直前に再検証する。"""
    out = []
    for key, m in (state.get("merged") or {}).items():
        # 永続的な skip（dirty・HEAD 不一致・rm 失敗）で SWEEP_MAX_TRIES を
        # 超えた候補は諦める — plan の sweep が空にならないと毎 tick
        # executor session が起きてしまう
        if int(m.get("sweep_skips") or 0) >= SWEEP_MAX_TRIES:
            continue
        repo, _, n = key.partition("#")
        head_ref = m.get("head_ref")
        for w in worktrees:
            if w.get("repo") != repo.split("/")[-1]:
                continue
            if w.get("githubRepo") and w["githubRepo"] != repo:
                continue
            lp = w.get("linkedPR") or {}
            pr_match = lp.get("number") == int(n) and \
                (lp.get("state") or "") == "merged"
            br_match = head_ref and \
                _short_branch(w.get("branch")) == head_ref
            # linkedPR が merged を指していても、worktree が別 branch に
            # 切り替わっているなら「merge した PR の worktree」ではない
            if pr_match and head_ref and not br_match:
                continue
            if not (pr_match or br_match):
                continue
            if w.get("hostId", "local") != "local" or \
                    w.get("isMainWorktree") or w.get("isArchived") or \
                    w.get("isActive") or w.get("childWorktreeIds"):
                continue
            agents = w.get("agents") or []
            if any(x.get("state") not in ("idle", "done") for x in agents):
                continue
            if w.get("status") == "working":
                continue
            if (w.get("liveTerminalCount") or 0) > 0 and \
                    w.get("workspaceStatus") != "completed":
                continue
            out.append({"repo": repo, "number": int(n),
                        "head_ref": head_ref, "sha": m.get("sha"),
                        "worktree": w.get("worktreeId"),
                        "path": w.get("path")})
            break
    return out


def local_session_audit(state, worktrees, terms_cache, record=True):
    """local session 全件を確認し、routine 外も含む merge 済み PR を照合する。"""
    count = 0
    for w in worktrees:
        if w.get("hostId", "local") != "local":
            continue
        wid = w.get("worktreeId")
        terms_cache[wid] = terminal_list(wid)
        count += len(terms_cache[wid])
        if w.get("isMainWorktree") or w.get("isArchived") or \
                w.get("workspaceKind", "git") != "git":
            continue
        branch = _short_branch(w.get("branch"))
        if not branch or branch in ("main", "master"):
            continue
        remote = sh(["git", "-C", w["path"], "remote", "get-url", "origin"]).stdout.strip()
        match = re.search(r"github\.com[:/]([^/]+/[^/]+?)(?:\.git)?$", remote)
        if not match:
            continue
        repo = match.group(1)
        w["githubRepo"] = repo
        lp = w.get("linkedPR") or {}
        if lp.get("number"):
            v = gh_json(["pr", "view", str(lp["number"]), "--repo", repo,
                         "--json", "number,state,headRefName,headRefOid,mergedAt"])
        else:
            found = gh_json(["pr", "list", "--repo", repo, "--state", "merged",
                             "--head", branch, "--limit", "1", "--json",
                             "number,state,headRefName,headRefOid,mergedAt"])
            v = found[0] if found else {}
        if v.get("state") != "MERGED" or v.get("headRefName") != branch:
            continue
        key = pr_key(repo, v["number"])
        state.setdefault("merged", {}).setdefault(key, {
            "sha": v["headRefOid"], "head_ref": branch,
            "merged_at": v["mergedAt"], "via": "external"})
    audit = {"worktrees": sum(w.get("hostId", "local") == "local" for w in worktrees),
             "sessions": count}
    if record:
        append_event("local_sessions_checked", **audit)
    return audit


def sweep_sessions_ready(w, terms):
    """完了 agent と prompt に戻った shell だけを close 対象にする。"""
    agents = w.get("agents") or []
    if w.get("isActive") or w.get("childWorktreeIds") or w.get("status") == "working":
        return False
    if any(x.get("state") not in ("idle", "done") for x in agents):
        return False
    for t in terms:
        if t.get("agentIdentity"):
            if not agents:
                return False
        elif t.get("connected") and not (t.get("preview") or "").rstrip().endswith(("$", "%", "❯", "➜")):
            return False
    return True


def sweep_skip_transient(reason):
    """skip 理由が一時的（ps との race）なら True。False = 永続的で
    sweep_skips の加算対象（SWEEP_MAX_TRIES で候補から外れる）。"""
    return any(t in reason for t in SWEEP_TRANSIENT_REASONS)


def cmd_gate(a):
    # --no-lock でも STATE_DIR は要る（lock を飛ばすと _lock_acquire 内の
    # mkdir も走らず、plan/state の書き込み先が無い path になる）
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    run_id = None
    try:
        if not a.no_lock:
            run_id = _lock_acquire(LOCK_TTL_S)
            if not run_id:
                # 前回 run が残っている → この tick は起動しない
                emit({"ok": True, "run": False, "reason": "locked"})
                sys.exit(1)
        # lock 取得後に読む — 前の run が release 直前に save_state した
        # 最終書き込み（merged/escalated/dispatch 回数）を取りこぼして
        # 古い snapshot で save_state → 上書き消失させないため
        st = load_state()
        _gate(a, st, run_id)
    except Exception as e:
        # fail-closed: API 失敗の tick では merge・削除を実行しない。
        # run_id が無い = 自分の lock を持っていないので release もしない
        # （他人の lock を消さない）
        if run_id:
            _lock_release(run_id)
        msg = str(e) if isinstance(e, ApiError) else \
            f"{type(e).__name__}: {e}"
        append_event("tick_error", error=msg)
        fail(msg, code=2)


def _merge_events(dates):
    """reconcile 用: 指定日の merge record を (repo, pr, sha) の集合で
    まとめて読む（intent 件数分だけ jsonl を読み直さない）。"""
    out = set()
    for d in dates:
        for ev in read_events(d):
            if ev.get("event") == "merge":
                out.add((ev.get("repo"), ev.get("pr"), ev.get("sha")))
    return out


def prune_state(st, days=30):
    """state.json の無制限成長を止める — merged/judge/dispatch の記録は
    jsonl が監査用の正本なので、動作に要る分（直近期間）だけ残す。"""
    cutoff = _now() - timedelta(days=days)

    def old(ts):
        t = _ts(ts or "")
        return t is not None and t < cutoff

    for k, m in list((st.get("merged") or {}).items()):
        if old(m.get("merged_at")):
            st["merged"].pop(k)
    for k, j in list((st.get("judge") or {}).items()):
        if old(j.get("at")):
            st["judge"].pop(k)
    for k, d in list((st.get("prs") or {}).items()):
        acts = [x.get("at") for x in d.get("dispatches", []) if x.get("at")]
        if not acts:
            # dispatch 実績が無い entry は read path で作られた空殻
            # （escalated だけ立っているものは往復の記録なので残す）
            if not d.get("escalated") and not d.get("stale_ticks"):
                st["prs"].pop(k)
        elif all(old(x) for x in acts):
            st["prs"].pop(k)


def _gate(a, st, run_id):
    # intent reconcile: 前回 crash 等で record が欠落した merge を拾い直す。
    # merge 発行前に intent を書いているので、API が受理した直後に
    # process が死んでもここで MERGED を確認して record を補完する
    recorded = _merge_events(
        {_today_jst(),
         (datetime.now(JST) - timedelta(days=1)).strftime("%Y-%m-%d")})
    for key, it in list((st.get("merge_intents") or {}).items()):
        try:
            v = gh_json(["pr", "view", str(it["number"]), "--repo",
                         it["repo"], "--json", "state,headRefOid"])
        except ApiError:
            continue  # reconcile 失敗は次 tick に回す（intent は残す）
        if (v.get("state") or "").upper() == "MERGED":
            sha = it.get("sha") or v.get("headRefOid")
            if (it["repo"], it["number"], sha) not in recorded:
                append_event("merge", repo=it["repo"], pr=it["number"],
                             sha=sha, via=it.get("via", "?"),
                             reconciled=True)
            st.get("merge_intents", {}).pop(key, None)
        else:
            # MERGED 以外（OPEN=受理前に死んだ・CLOSED=拒否された）=
            # merge は成立していないので intent を落とす
            st.get("merge_intents", {}).pop(key, None)
    prune_state(st)
    save_state(st)

    prs = list_open_prs()
    worktrees = worktree_ps()
    base_cache, terms_cache = {}, {}
    entries = [(p, pr_facts(p["repo"], p["number"], base_cache))
               for p in prs]

    session_audit = local_session_audit(st, worktrees, terms_cache)

    plan_entries = [compute_pr_decision(p, facts, worktrees, terms_cache, st)
                    for p, facts in entries]

    sweeps = sweep_candidates(st, worktrees)
    has_work = sweeps or any(
        x["type"] in ("dispatch", "merge", "judge", "escalate")
        for e in plan_entries for x in e["actions"])

    plan = {"generated_at": _iso(_now()), "date": _today_jst(),
            "run_id": run_id,
            "prs": plan_entries, "sweep": sweeps, "local_sessions": session_audit,
            "report": {"md": str(ME_REPO / "daily" / _today_jst() /
                                 "pr-watch.md"),
                       "jsonl": str(jsonl_path())}}
    PLAN_FILE.write_text(json.dumps(plan, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    save_state(st)
    if not has_work:
        if run_id:
            _lock_release(run_id)
        emit({"ok": True, "run": False, "reason": "no actions",
              "prs": len(prs)})
        sys.exit(1)
    emit({"ok": True, "run": True, "plan": str(PLAN_FILE), "run_id": run_id,
          "actions": sum(len(e["actions"]) for e in plan_entries),
          "sweep": len(sweeps)})


def cmd_plan(a):
    try:
        emit({"ok": True,
              **json.loads(PLAN_FILE.read_text(encoding="utf-8"))})
    except (FileNotFoundError, json.JSONDecodeError):
        emit({"ok": True, "run": False, "reason": "no plan"})


# ---------- dispatch ----------

def cmd_dispatch(a):
    try:
        return _cmd_dispatch(a)
    except ApiError as e:
        append_event("dispatch_failed", repo=a.repo, pr=a.number,
                     error=str(e))
        fail(str(e))


def _cmd_dispatch(a):
    st = load_state()
    facts = pr_facts(a.repo, a.number, {})
    v = facts["view"]
    head = v.get("headRefOid")
    items = dispatch_items(a.repo, a.number, facts, st)
    if not items:
        emit({"ok": True, "dispatched": False,
              "reason": "no dispatch items (stale plan)"})
        return
    sig = unaddressed_sig(items)
    ds = get_dispatch_state(st, a.repo, a.number)
    allowed, why, escalate = dispatch_allows(ds, head)
    if escalate:
        emit({"ok": True, "dispatched": False, "needs_escalate": True,
              "reason": why})
        return
    if not allowed:
        emit({"ok": True, "dispatched": False, "reason": why})
        return
    if dispatch_already_sent(ds, head, sig):
        emit({"ok": True, "dispatched": False,
              "reason": "already sent for head+items"})
        return

    msg = build_dispatch_message(a.repo, v, items)
    worktrees = worktree_ps()
    w, _how = find_worktree(worktrees, a.repo, a.number,
                            v.get("headRefName"))
    terms = {}
    if w:
        terms = {w["worktreeId"]: terminal_list(w["worktreeId"])}
    route = route_dispatch(worktrees, terms, a.repo, v)
    if route["route"] in ("defer", "none"):
        emit({"ok": True, "dispatched": False, "reason": route["reason"],
              "defer": route["route"] == "defer"})
        return

    if route["route"] == "send":
        handle = route["handle"]
    elif route["route"] == "revive":
        res = orca_json(["terminal", "create", "--worktree",
                         route["worktree"]["worktreeId"],
                         "--command", "devin"], timeout=120)
        handle = ((res or {}).get("terminal") or {}).get("handle") or \
            (res or {}).get("handle")
        if not handle:
            raise ApiError(f"terminal create returned no handle: {res}")
        ok, detail = wait_tui_idle(handle)
        if not ok:
            raise ApiError(f"tui-idle not satisfied: {detail}")
    else:  # spawn
        handle, _wpath, _wtid = spawn_worktree(
            a.repo.split("/")[-1], a.number, v.get("headRefName"))
        ok, detail = wait_tui_idle(handle)
        if not ok:
            raise ApiError(f"tui-idle not satisfied: {detail}")

    delivered, detail = send_prompt(handle, msg)
    if not delivered:
        # 送信カウントを進めない — 次 tick で再送対象になる
        append_event("dispatch_failed", repo=a.repo, pr=a.number,
                     error="turn_started not observed")
        emit({"ok": True, "dispatched": False,
              "reason": "turn_started not observed", "detail": detail})
        return
    mark_dispatch_sent(st, a.repo, a.number, head, sig)
    save_state(st)
    append_event("dispatch", repo=a.repo, pr=a.number, sha=head,
                 route=route["route"], items=len(items),
                 kinds=sorted({it["kind"] for it in items}))
    emit({"ok": True, "dispatched": True,
          "route": route["route"], "items": len(items)})


def cmd_escalate(a):
    try:
        return _cmd_escalate(a)
    except ApiError as e:
        fail(str(e))


def _cmd_escalate(a):
    st = load_state()
    ds = dispatch_state(st, a.repo, a.number)
    if ds.get("escalated"):
        emit({"ok": True, "escalated": False, "reason": "already"})
        return
    body = (a.reason or "") or \
        "レビュー指摘・PR 修正の対応が上限に達したため、自動応答を打ち切りました。" \
        "以降は人間の判断が必要です（pr-merge-lane）。"
    gh(["pr", "comment", str(a.number), "--repo", a.repo,
        "--body", body])
    ds["escalated"] = True
    save_state(st)
    append_event("escalate", repo=a.repo, pr=a.number, reason=body[:200])
    emit({"ok": True, "escalated": True})


# ---------- judge ----------

def cmd_judge_input(a):
    try:
        return _cmd_judge_input(a)
    except ApiError as e:
        fail(str(e))


def _cmd_judge_input(a):
    v = pr_view(a.repo, a.number)
    files, renamed_from = pr_files(a.repo, a.number)
    diff = review_diff(pr_diff(a.repo, a.number))
    emit({"ok": True, "repo": a.repo, "number": a.number,
          "sha": v.get("headRefOid"), "title": v.get("title"),
          "body": v.get("body") or "", "context_hash": pr_context_hash(v),
          "base": v.get("baseRefName"), "base_sha": v.get("baseRefOid"),
          "author": (v.get("author") or {}).get("login"),
          "files": files, "renamed_from": renamed_from,
          "checks": check_rollup(v),
          "ignored_files":
              [f for f in files + renamed_from if is_lockfile(f)],
          "policy_version": JUDGE_POLICY_VERSION,
          "truncated": False, "diff": diff})


def cmd_judge_result(a):
    try:
        return _cmd_judge_result(a)
    except ApiError as e:
        fail(str(e))


def _cmd_judge_result(a):
    if a.verdict not in ("ok", "ng", "repair"):
        fail("--verdict must be ok|ng|repair")
    if not re.fullmatch(r"[0-9a-f]{64}", a.context_hash):
        fail("--context-hash must be the context_hash from judge-input")
    st = load_state()
    previous = (st.get("judge") or {}).get(pr_key(a.repo, a.number)) or {}
    # dependency_repair は追従履歴の属性（dep-only head に repair を出した
    # 事実）なので policy version を跨いで保持する — 失効させると追従コードを
    # 含む head が bot_dep_only を外れ、approval の付かない bot PR が hold に
    # 固定される。whitelist の効力は gate 側が verdict・head sha・version を
    # 再検証して縛るので、ここでは過去の属性だけを引き継ぐ
    repairing = bool(previous.get("dependency_repair"))
    if a.verdict == "repair":
        if not (a.reason or "").strip():
            fail("repair requires --reason with affected usage and required changes")
        v = pr_view(a.repo, a.number)
        files, renamed_from = pr_files(a.repo, a.number)
        touched = files + renamed_from
        if v.get("state") != "OPEN" or v.get("headRefOid") != a.sha or \
                not _is_bot(v.get("author")) or not touched or \
                any(not is_lockfile(p) and classify_path(p) == "hold"
                    for p in touched) or \
                not (repairing or all(
                    is_dependency_file(p) or is_actions_workflow(p)
                    for p in touched)):
            fail("repair requires current open bot dependency-only head")
        repairing = True
    st.setdefault("judge", {})[pr_key(a.repo, a.number)] = {
        "sha": a.sha, "context_hash": a.context_hash, "verdict": a.verdict,
        "reason": a.reason or "", "at": _iso(_now()),
        "policy_version": JUDGE_POLICY_VERSION, "dependency_repair": repairing}
    save_state(st)
    append_event("judge", repo=a.repo, pr=a.number, sha=a.sha, context_hash=a.context_hash,
                 verdict=a.verdict, reason=a.reason or "",
                 policy_version=JUDGE_POLICY_VERSION, dependency_repair=repairing)
    out = {"ok": True, "verdict": a.verdict, "merge_ready": False}
    if a.verdict == "ok":
        # ok 登録後に残りの hard gate が現在 head で全て通るなら、次 tick を
        # 待たず同じ executor 実行内で merge を呼んでよい。merge 自体が
        # 発行直前に全条件を再検証するので、ここでの False は「今はまだ
        # 通らない」を示すだけで安全性には関与しない。判定後に PR 状態が
        # 変わっていれば context/head の不一致で False になる。
        rec = st["judge"][pr_key(a.repo, a.number)]
        try:
            facts = pr_facts(a.repo, a.number, {})
            ready, blocked = hard_gate(facts, judge=rec, via="lane",
                                       expect_sha=a.sha)
        except ApiError as e:
            ready, blocked = False, [str(e)]
        out["merge_ready"] = ready
        if not ready:
            out["blocked"] = blocked
    emit(out)


# ---------- merge ----------

def cmd_merge(a):
    try:
        return _cmd_merge(a)
    except ApiError as e:
        append_event("merge_failed", repo=a.repo, pr=a.number,
                     error=str(e))
        fail(str(e))


def _cmd_merge(a):
    if a.via != "lane":
        fail("--via must be lane")
    st = load_state()
    key = pr_key(a.repo, a.number)
    # 直前に state・mergeable・approval・unaddressed・required check・
    # path 分類を全件引き直す（pullfrog-approval だけに依存しない）
    facts = pr_facts(a.repo, a.number, {})
    judge = (st.get("judge") or {}).get(key)
    ok, reasons = hard_gate(facts, judge=judge, via=a.via,
                            expect_sha=a.sha or None)
    if not ok:
        append_event("merge_blocked", repo=a.repo, pr=a.number,
                     reasons=reasons)
        emit({"ok": True, "merged": False, "blocked": reasons})
        return
    v = facts["view"]
    head = v.get("headRefOid")

    # intent を先に永続化: API が merge を受理した直後に process が死んでも
    # 次 tick の reconcile が record を補完する
    st.setdefault("merge_intents", {})[key] = {
        "repo": a.repo, "number": a.number, "sha": head,
        "via": a.via, "at": _iso(_now())}
    save_state(st)

    if v.get("isDraft"):
        gh(["pr", "ready", str(a.number), "--repo", a.repo])
    # --match-head-commit: gate 検証と発行の間に head が動いたら GitHub 側
    # で拒否される（判定した head 以外が merge されないことを API レベルで
    # 保証する — expect_sha のアプリ側照合だけでは race 窓が残る）
    r = subprocess.run(["gh", "pr", "merge", str(a.number), "--repo",
                        a.repo, "--squash", "--delete-branch",
                        "--match-head-commit", head],
                       capture_output=True, text=True, timeout=120)
    st2 = gh_json(["pr", "view", str(a.number), "--repo", a.repo,
                   "--json", "state"])
    merged = (st2.get("state") or "").upper() == "MERGED"
    if not merged:
        # API が受理する前に失敗したと確定できるときだけ intent を落とす
        if r.returncode != 0:
            st.get("merge_intents", {}).pop(key, None)
            save_state(st)
            raise ApiError(f"gh pr merge failed: "
                           f"{r.stderr.strip()[:300]}")
        raise ApiError("merge command succeeded but state != MERGED")
    st.get("merge_intents", {}).pop(key, None)
    st.setdefault("merged", {})[key] = {
        "sha": head, "head_ref": v.get("headRefName"),
        "merged_at": _iso(_now()), "via": a.via}
    chk = required_check_state(check_rollup(v), facts["required"])
    save_state(st)
    # cls は hard_gate の分類を再利用する
    cls = facts.get("cls") or {}
    dep_auto = facts.get("dep_auto_ok") or {}
    append_event("merge", repo=a.repo, pr=a.number, sha=head, via=a.via,
                 bot_dep_only=cls.get("bot_dep_only"),
                 dependency_repair=bool(cls.get("dependency_repair")),
                 dep_auto_ok=dep_auto.get("eligible") or None,
                 dep_updates=[u["name"] for u in dep_auto.get("updates", [])]
                 or None,
                 nonrequired_failing=chk["nonrequired_failing"])
    emit({"ok": True, "merged": True, "sha": head})


# ---------- sweep ----------

def cmd_sweep(a):
    try:
        return _cmd_sweep(a)
    except ApiError as e:
        fail(str(e))


def _cmd_sweep(a):
    st = load_state()
    worktrees = worktree_ps()
    terms_cache = {}
    audit = local_session_audit(st, worktrees, terms_cache, record=not a.dry_run)
    cands = sweep_candidates(st, worktrees)
    removed, skipped = [], []

    def skip(c, reason):
        skipped.append({**c, "reason": reason})
        if a.dry_run:
            return
        m = (st.get("merged") or {}).get(pr_key(c["repo"], c["number"]))
        if m is None:
            return
        # 残した理由の監査先は jsonl だけ。同じ worktree+理由の連続は
        # 初回だけ記録する — live terminal が tick を跨いで残る場合に
        # 毎回書くと jsonl が埋まるため
        if m.get("last_skip") != {"worktree": c["worktree"], "reason": reason}:
            m["last_skip"] = {"worktree": c["worktree"], "reason": reason}
            append_event("sweep_skipped", repo=c["repo"], pr=c["number"],
                         worktree=c["worktree"], reason=reason)
        if sweep_skip_transient(reason):
            return
        m["sweep_skips"] = int(m.get("sweep_skips") or 0) + 1
        if m["sweep_skips"] == SWEEP_MAX_TRIES:
            append_event("sweep_giveup", repo=c["repo"], pr=c["number"],
                         worktree=c["worktree"], reason=reason)

    for c in cands:
        if a.only and c["worktree"] != a.only:
            continue
        # ps 再取得と rm はこの呼び出し内で続けて行う（確認と削除の間に
        # session が起きる競合を最小化）。残る僅かな race 窓は設計上の受容
        w = next((x for x in worktree_ps()
                  if x.get("worktreeId") == c["worktree"]), None)
        if w is None:
            skip(c, "worktree gone")
            continue
        if not sweep_candidates(st, [w]) or \
                not sweep_sessions_ready(w, terminal_list(c["worktree"])):
            skip(c, "terminal/agent live")
            continue
        path = w.get("path")
        try:
            dirty = sh(["git", "-C", path, "status", "--porcelain"],
                       timeout=30).stdout.strip()
            if dirty:
                skip(c, "dirty worktree")
                continue
            head = sh(["git", "-C", path, "rev-parse", "HEAD"],
                      timeout=30).stdout.strip()
            branch = sh(["git", "-C", path, "branch", "--show-current"],
                        timeout=30).stdout.strip()
            if branch != c["head_ref"]:
                skip(c, "branch changed")
                continue
            if c.get("sha") and head != c["sha"]:
                skip(c, f"HEAD {head[:8]} != merged {c['sha'][:8]}")
                continue
            v = gh_json(["pr", "view", str(c["number"]), "--repo", c["repo"],
                         "--json", "state,headRefOid,headRefName"])
            if v.get("state") != "MERGED" or v.get("headRefOid") != head or \
                    v.get("headRefName") != branch:
                skip(c, "merged PR changed")
                continue
        except ApiError as e:
            skip(c, str(e))
            continue
        if a.dry_run:
            removed.append({**c, "dry_run": True})
            continue
        # --force は付けない — 確認と削除の間に未追跡ファイル等が増えた
        # 場合に git worktree remove 側が dirty 拒否してくれる最後の網に
        # なる（失敗は skipped 扱いで次 tick に回る）
        try:
            fresh = next((x for x in worktree_ps() if x.get("worktreeId") == c["worktree"]), None)
            if fresh is None or not sweep_candidates(st, [fresh]) or \
                    not sweep_sessions_ready(fresh, terminal_list(c["worktree"])):
                skip(c, "terminal/agent live")
                continue
            if (fresh.get("liveTerminalCount") or 0) > 0:
                closed = orca_json(["terminal", "close", "--worktree",
                                    f"id:{c['worktree']}", "--all"], timeout=120)
                append_event("sessions_closed", repo=c["repo"], pr=c["number"],
                             worktree=c["worktree"], result=closed)
            after = next((x for x in worktree_ps() if x.get("worktreeId") == c["worktree"]), None)
            if after is None or (after.get("liveTerminalCount") or 0) > 0:
                skip(c, "terminal/agent live")
                continue
            orca_json(["worktree", "rm", "--worktree",
                       f"id:{c['worktree']}"], timeout=120)
        except ApiError as e:
            skip(c, f"rm failed: {e}")
            continue
        removed.append(c)
        append_event("worktree_rm", repo=c["repo"], pr=c["number"],
                     path=path)
    if not a.dry_run:
        save_state(st)
    emit({"ok": True, "local_sessions": audit, "removed": removed, "skipped": skipped})


# ---------- lock / events ----------
def _lock_info():
    try:
        return json.loads((LOCK_DIR / "info.json").read_text())
    except Exception:
        return {}


def _write_lock_info():
    info = {"pid": os.getpid(), "run_id": uuid.uuid4().hex,
            "ts": time.time(), "ts_iso": _iso(_now())}
    (LOCK_DIR / "info.json").write_text(json.dumps(info))
    return info["run_id"]


def _lock_acquire(ttl):
    """mkdir lock。取得できたらその run の run_id、lock が残っていれば
    None。run_id は release 時の所有者照合に使う — TTL 超で stale 回収
    された後に旧 run が release すると新しい run の lock を消してしまう
    のを防ぐ。stale は info.json の ts が TTL 超のときだけ回収する。"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.mkdir(LOCK_DIR)
    except FileExistsError:
        pass
    else:
        try:
            return _write_lock_info()
        except OSError:
            # mkdir と info 書き込みの間に stale 回収で消された — 競合として
            # 未取得扱いにする（dir だけ残ると mtime では即回収されないため）
            return None
    info = _lock_info()
    try:
        age = time.time() - float(info.get("ts")
                                  or os.stat(LOCK_DIR).st_mtime)
    except OSError:
        return None  # stat が通らない = 並走中。保守的に locked 扱い
    if age < ttl:
        return None
    # stale 回収は reclaim.lock の flock で直列化する。検証→rmtree→mkdir
    # の間に別の回収者が fresh lock を建てると、それを rmtree してしまう
    # — run lock 自体は process を跨ぐので flock では保持できないが、
    # 回収のクリティカルセクションは process 内で閉じるので flock が効く
    # （flock を取れない = 他の回収者が作業中 → 今回は諦める）
    rf = (STATE_DIR / "reclaim.lock").open("w")
    try:
        fcntl.flock(rf.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        rf.close()
        return None
    try:
        # 取得直前に世代を再照合し、差し替わっていたら他人の fresh lock
        if _lock_info().get("ts") != info.get("ts"):
            return None
        shutil.rmtree(LOCK_DIR)
        os.mkdir(LOCK_DIR)  # atomic — 間に他人が取れば FileExistsError
        try:
            return _write_lock_info()
        except OSError:
            return None
    except (FileExistsError, OSError):
        return None
    finally:
        fcntl.flock(rf.fileno(), fcntl.LOCK_UN)
        rf.close()


def _lock_release(run_id=None):
    """run_id 指定時は info.json の run_id と一致するときだけ消す。
    照合しない呼び出し（run_id=None）は手動運用用に消す。
    照合→削除は reclaim.lock 下で行う — stale 回収の検証→rmtree と
    交差すると「回収者が stale 判定 → owner が release → 第三者が
    fresh lock → 回収者がそれを rmtree」の順で新しい lock を消しうる。"""
    if not STATE_DIR.exists():
        return True
    rf = (STATE_DIR / "reclaim.lock").open("w")
    try:
        fcntl.flock(rf.fileno(), fcntl.LOCK_EX)
        info = _lock_info()
        if info.get("run_id") and run_id and info["run_id"] != run_id:
            return False
        try:
            shutil.rmtree(LOCK_DIR)
        except FileNotFoundError:
            pass
        return True
    finally:
        fcntl.flock(rf.fileno(), fcntl.LOCK_UN)
        rf.close()


def cmd_lock(a):
    if a.action == "status":
        emit({"ok": True, "locked": LOCK_DIR.exists(),
              "holder": _lock_info()})
        return
    if a.action == "release":
        if not _lock_release(a.run_id):
            emit({"ok": False, "released": False,
                  "reason": "run_id mismatch (lock held by another run)"})
            return
        emit({"ok": True, "released": True})
        return
    run_id = _lock_acquire(LOCK_TTL_S)
    emit({"ok": bool(run_id), "acquired": bool(run_id),
          "run_id": run_id})


def cmd_log(a):
    """JSON の補足記録を note event として日次ログへ追記する。"""
    try:
        note = json.loads(Path(a.input).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(f"invalid log input: {e}")
    allowed = {"message", "repo", "pr", "sha", "sources", "details"}
    if not isinstance(note, dict) or set(note) - allowed:
        fail("log input must be an object with message, repo, pr, sha, sources, details only")
    if not isinstance(note.get("message"), str) or not note["message"].strip():
        fail("log input requires a non-empty message")
    for key in ("repo", "sha"):
        if key in note and not isinstance(note[key], str):
            fail(f"log {key} must be a string")
    if "pr" in note and (type(note["pr"]) is not int or note["pr"] < 1):
        fail("log pr must be a positive integer")
    if "sources" in note and (not isinstance(note["sources"], list) or
                              any(not isinstance(x, str) for x in note["sources"])):
        fail("log sources must be an array of strings")
    if "details" in note and not isinstance(note["details"], dict):
        fail("log details must be an object")
    # 補足から実績 event や時刻を偽装させない。note は gate/state を変えない。
    rec = append_event("note", **note)
    emit({"ok": True, "record": rec, "path": str(jsonl_path())})


def cmd_events(a):
    events = read_events(a.date)
    if a.event:
        events = [e for e in events if e.get("event") in a.event]
    if a.repo:
        events = [e for e in events if e.get("repo") == a.repo]
    if a.number is not None:
        events = [e for e in events if e.get("pr") == a.number]
    if a.limit is not None:
        if a.limit < 1:
            fail("--limit must be positive")
        events = events[-a.limit:]
    emit({"ok": True, "events": events, "path": str(jsonl_path(a.date))})


SCHEMA = {
    "gate": {"out": "{run, plan?, reason?}", "exit":
             "0=session必要 1=skip(変化なし/locked) 2=API失敗(fail-closed)"},
    "plan": {"out": "current tick plan"},
    "dispatch": {"args": "--repo R --number N",
                 "out": "{dispatched, route?, reason?, needs_escalate?}"},
    "escalate": {"args": "--repo R --number N [--reason T]",
                 "out": "{escalated}"},
    "judge-input": {"args": "--repo R --number N",
                    "out": "{sha, body, base, base_sha, context_hash, files, renamed_from, checks, ignored_files, diff, policy_version, truncated:false}"},
    "judge-result": {"args": "--repo R --number N --sha S "
                     "--context-hash H --verdict ok|ng|repair [--reason T]",
                     "out": "{verdict, merge_ready, blocked?} — ok で "
                            "merge_ready=true なら同じ実行内で merge を呼べる"},
    "merge": {"args": "--repo R --number N [--via lane] [--sha S]",
              "out": "{merged, blocked?}"},
    "sweep": {"args": "[--dry-run] [--only worktreeId]",
              "out": "{removed[], skipped[]}"},
    "lock": {"args": "acquire|release [--run-id S]|status",
             "out": "{acquired, run_id?} | {released}"},
    "log": {"args": "--input JSON_FILE",
            "input": {"message": "required non-empty string",
                      "repo": "optional string", "pr": "optional positive integer",
                      "sha": "optional string", "sources": "optional string[]",
                      "details": "optional object"},
            "out": "{record:{ts,event:note,...},path}",
            "effect": "append-only note; no action or state changes"},
    "events": {"args": "[--date YYYY-MM-DD] [--event E ...] "
                       "[--repo R] [--number N] [--limit N]",
               "out": "{events[],path}"},
    "schema": {"out": "this document"},
}


def cmd_schema(a):
    emit({"ok": True, "commands": SCHEMA,
          "state_dir": str(STATE_DIR), "me_repo": str(ME_REPO)})


def main():
    p = argparse.ArgumentParser(
        prog="pr_triage", description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("gate", help="triage + plan 生成（automation precheck）")
    g.add_argument("--no-lock", action="store_true",
                   help="lock を取らず試す（手動検証用）")
    g.set_defaults(fn=cmd_gate)

    pl = sub.add_parser("plan", help="現在の tick plan を返す")
    pl.set_defaults(fn=cmd_plan)

    d = sub.add_parser("dispatch", help="1 PR の dispatch を実行")
    d.add_argument("--repo", required=True)
    d.add_argument("--number", type=int, required=True)
    d.set_defaults(fn=cmd_dispatch)

    e = sub.add_parser("escalate", help="上限到達 PR へ escalation コメント")
    e.add_argument("--repo", required=True)
    e.add_argument("--number", type=int, required=True)
    e.add_argument("--reason")
    e.set_defaults(fn=cmd_escalate)

    ji = sub.add_parser("judge-input", help="judge 用の diff + 材料を返す")
    ji.add_argument("--repo", required=True)
    ji.add_argument("--number", type=int, required=True)
    ji.set_defaults(fn=cmd_judge_input)

    jr = sub.add_parser("judge-result", help="judge の判定を head SHA に記録")
    jr.add_argument("--repo", required=True)
    jr.add_argument("--number", type=int, required=True)
    jr.add_argument("--sha", required=True)
    jr.add_argument("--context-hash", required=True)
    jr.add_argument("--verdict", required=True)
    jr.add_argument("--reason")
    jr.set_defaults(fn=cmd_judge_result)

    m = sub.add_parser("merge", help="merge の唯一の発行経路（hard gate 再検証）")
    m.add_argument("--repo", required=True)
    m.add_argument("--number", type=int, required=True)
    m.add_argument("--via", choices=["lane"], default="lane")
    m.add_argument("--sha", help="判定した head SHA")
    m.set_defaults(fn=cmd_merge)

    s = sub.add_parser("sweep", help="routine merge PR の worktree 削除")
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--only", help="worktreeId を1つに絞る")
    s.set_defaults(fn=cmd_sweep)

    lk = sub.add_parser("lock", help="run lock")
    lk.add_argument("action", choices=["acquire", "release", "status"])
    lk.add_argument("--run-id", help="release 時の所有者照合"
                                     "（plan.run_id を渡す）")
    lk.set_defaults(fn=cmd_lock)

    lg = sub.add_parser("log", help="根拠・確認・引き継ぎを jsonl に追記")
    lg.add_argument("--input", required=True, help="note の JSON ファイル（schema 参照）")
    lg.set_defaults(fn=cmd_log)

    ev = sub.add_parser("events", help="jsonl イベントを返す")
    ev.add_argument("--date", help="YYYY-MM-DD（既定: 今日 JST）")
    ev.add_argument("--event", action="append", help="event を絞る（複数指定可）")
    ev.add_argument("--repo", help="repo を絞る")
    ev.add_argument("--number", type=int, help="PR 番号を絞る")
    ev.add_argument("--limit", type=int, help="絞り込み後の最新 N 件を返す")
    ev.set_defaults(fn=cmd_events)

    sc = sub.add_parser("schema", help="subcommand スキーマを返す")
    sc.set_defaults(fn=cmd_schema)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
