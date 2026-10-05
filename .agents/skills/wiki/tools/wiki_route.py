#!/usr/bin/env python3
"""wiki バンドル（OKF v0.1）の自然文ルーターツール（依存なし・stdlib のみ）。

「この問いはどのページを見るべきか」（route）と「このページはどのページへ
リンクすべきか」（links）を、Jev（TypeSafe System One）の noul 判定で返す。
Jev が使えないとき／送るべきでないときは character-bigram TF-IDF に自動 fallback する。
exit code: 結果あり=0 / 結果0件=1 / 引数・root エラー=2（wiki_links.py 互換）。
"""
import argparse
import json
import math
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

# RESERVED・LINK_RE・parse_frontmatter・get_field・resolve_link は wiki_links.py と
# 同一実装なので import する（同じ dir の script はスクリプト実行時 sys.path[0] に
# 自分の dir が入るため import できる）。URL_RE は wiki_route.py 側では直接使わない
# （resolve_link の内部でのみ必要）ので import しない。
from wiki_links import RESERVED, LINK_RE, parse_frontmatter, get_field, resolve_link

DEFAULT_ROOT = "~/src/github.com/wwwyo/me/wiki"
LOG_PATH = "~/.local/state/wiki-route/log.jsonl"

JEV_URL = "https://api.typesafe.ai/v1/systemone"
JEV_MODEL = "jev-latest"
JEV_RETRYABLE_STATUS = {429, 529}
JEV_MAX_ATTEMPTS = 4
BODY_EXCERPT_CHARS = 3000


def body_after_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return "\n".join(lines[i + 1:]).lstrip("\n")
    return text


def load_all_pages(root: Path):
    """root 配下の全 .md を読み、path/text/frontmatter フィールドを付けて返す。

    wiki_links.py の load_pages と違い本文（text）を持つ点が必須（links の
    body_excerpt・already_linked 判定に使う）ため、無理に共通化しない。
    """
    pages = []
    for f in sorted(root.rglob("*.md")):
        rel = f.relative_to(root).as_posix()
        try:
            text = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as e:
            print(f"warn: 読めない: {rel}: {e}", file=sys.stderr)
            continue
        reserved = f.name in RESERVED
        fm = None if reserved else parse_frontmatter(text)
        pages.append({
            "path": rel,
            "text": text,
            "title": get_field(fm, "title") if fm else None,
            "description": get_field(fm, "description") if fm else None,
        })
    return pages


def is_local_path(path: str) -> bool:
    """業務・顧客データを含む `.local.` ページか（命名規約: `<name>.local.<ext>`）。

    本文を Jev（外部 API）へ送ってよいかの判定に使う。パス中のどこかに
    `.local.` が現れるかで見る（`routable_pages` の対象除外とここでの
    送信可否判定を同じ関数に統一し、末尾 `.local.md` だけを見て
    `foo.local.private.md` のような名前を見落とす、という食い違いを無くす）。
    """
    return ".local." in path


def routable_pages(all_pages):
    """route/links の対象候補: `.local.` を含むページ・予約 meta・title/description 欠落を除く。"""
    out = []
    for p in all_pages:
        name = p["path"].rsplit("/", 1)[-1]
        if name in RESERVED or is_local_path(p["path"]):
            continue
        if not p["title"] or not p["description"]:
            continue
        out.append(p)
    return out


def already_linked_paths(target, all_paths, bundle_dirs):
    linked = set()
    for link in LINK_RE.findall(target["text"]):
        kind, resolved = resolve_link(link, target["path"], all_paths, bundle_dirs)
        if kind == "bundle":
            linked.add(resolved)
    return linked


def _get_typesafe_key() -> str:
    """TYPESAFE_API_KEY を解決する。env → mise+age の順。無ければ空文字列。

    非対話シェルでは復号鍵 MISE_AGE_KEY が注入されないため、Keychain
    (`mise-age-key`) から取り出して `mise env` に渡す。global の mise config
    にあるので cwd はどこでもよい（home を使う）。
    """
    tok = os.environ.get("TYPESAFE_API_KEY", "").strip()
    if tok:
        return tok
    try:
        env = {**os.environ}
        if not env.get("MISE_AGE_KEY"):
            key = subprocess.run(
                ["security", "find-generic-password", "-a", os.environ.get("USER", ""),
                 "-s", "mise-age-key", "-w"],
                capture_output=True, text=True, timeout=5,
            ).stdout.strip()
            if key:
                env["MISE_AGE_KEY"] = key
        res = subprocess.run(
            ["mise", "env", "--json"],
            capture_output=True, text=True, timeout=20, env=env,
            cwd=str(Path.home()),
        )
        if res.returncode != 0:
            return ""
        return (json.loads(res.stdout or "{}").get("TYPESAFE_API_KEY") or "").strip()
    except Exception:
        return ""


def resolve_send_gate(*, local_only: bool, page_local: bool = False):
    """Jev（外部 API）へ送ってよいかを決める唯一の入口。

    None なら送信可、文字列ならその理由で bigram のみに留める（key の解決も
    Jev 呼び出しも一切行わない）。判定順序は「.local ページ」→「--local-only」。
    """
    if page_local:
        return ".local ページは外部 API (Jev) に送らない"
    if local_only:
        return "--local-only 指定のため Jev を呼ばない"
    return None


def noul(instructions: str, true_criterion: str, false_criterion: str) -> dict:
    return {"type": "noul", "instructions": instructions,
            "criteria": {"true": true_criterion, "false": false_criterion}}


def call_jev(state: dict, questions: dict, key: str) -> dict:
    """POST /v1/systemone。429/529 は backoff して再試行する。"""
    payload = {"state": state, "model": JEV_MODEL, "questions": questions}
    body = json.dumps(payload).encode("utf-8")
    last_err = None
    for attempt in range(JEV_MAX_ATTEMPTS):
        req = urllib.request.Request(
            JEV_URL, data=body, method="POST",
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in JEV_RETRYABLE_STATUS and attempt < JEV_MAX_ATTEMPTS - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"jev api error: HTTP {e.code}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"jev api unreachable: {e.reason}") from None
    raise RuntimeError(f"jev api error: {last_err}")


def jev_rank(pages, answers: dict):
    """`p{i}` キーの noul answers を、渡した pages と同じ並びで (page, prob) に戻し降順 sort する。"""
    ranked = []
    for i, page in enumerate(pages):
        a = answers.get(f"p{i}")
        if a is None:
            continue
        ranked.append((page, float(a.get("noul", 0.0))))
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked


def bigrams(text: str):
    s = re.sub(r"\s+", "", text)
    if len(s) < 2:
        return [s] if s else []
    return [s[i:i + 2] for i in range(len(s) - 1)]


def term_freq(tokens):
    tf = {}
    for t in tokens:
        tf[t] = tf.get(t, 0) + 1
    return tf


def build_bigram_index(pages, text_fn):
    """title+description（等）の文字 bigram TF-IDF index を組む（sklearn 風 smoothed idf）。"""
    docs_tf = {}
    df = {}
    for page in pages:
        tf = term_freq(bigrams(text_fn(page)))
        docs_tf[page["path"]] = tf
        for term in tf:
            df[term] = df.get(term, 0) + 1
    n = len(pages)
    idf = {term: math.log((1 + n) / (1 + d)) + 1 for term, d in df.items()}
    vectors = {}
    norms = {}
    for path, tf in docs_tf.items():
        vec = {term: count * idf.get(term, 0.0) for term, count in tf.items()}
        vectors[path] = vec
        norms[path] = math.sqrt(sum(w * w for w in vec.values()))
    return {"idf": idf, "vectors": vectors, "norms": norms}


def bigram_rank(query_text: str, pages, index):
    qtf = term_freq(bigrams(query_text))
    qvec = {term: count * index["idf"].get(term, 0.0) for term, count in qtf.items()}
    qnorm = math.sqrt(sum(w * w for w in qvec.values()))
    scored = []
    for page in pages:
        vec = index["vectors"].get(page["path"], {})
        norm = index["norms"].get(page["path"], 0.0)
        if norm == 0 or qnorm == 0:
            scored.append((page, 0.0))
            continue
        dot = sum(w * vec.get(term, 0.0) for term, w in qvec.items())
        scored.append((page, dot / (norm * qnorm)))
    scored.sort(key=lambda pair: pair[1], reverse=True)
    return scored


def append_log(record: dict, no_log: bool):
    if no_log:
        return
    try:
        path = Path(LOG_PATH).expanduser()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


def run_router(root: Path, args, *, subcommand: str, log_input: str, candidates,
                bigram_text_fn, bigram_query_text: str, jev_state: dict,
                build_questions, send_gate_reason, shape_results, header) -> int:
    """route/links 共通のパイプライン。

    router 選択 → key 解決 → Jev 呼び出し → 例外時 fallback → 結果整形 → log → 出力、
    をここ 1 箇所にまとめる。外部送信してよいかは `send_gate_reason`（呼び出し側が
    `resolve_send_gate` で決めた、None なら送信可）だけで判定し、ここでは判定し直さない
    ── これが唯一の送信ゲート。`shape_results(pairs, score_key)` が Jev/bigram 共通の
    行整形（already_linked 除外・min_prob 足切り等、サブコマンド固有のもの）を担う。
    `.local`／`--local-only` で送信しなかった実行は log に残さない
    （API 呼び出しを試みて失敗した fallback は従来どおり残す）。
    """
    bigram_start = time.monotonic()
    bigram_index = build_bigram_index(candidates, bigram_text_fn)
    bigram_scored = bigram_rank(bigram_query_text, candidates, bigram_index)
    shaped_bigram = shape_results(bigram_scored, "score")
    bigram_latency_ms = round((time.monotonic() - bigram_start) * 1000)
    bigram_top = [r["path"] for r in shaped_bigram[:10]]

    router = "bigram"
    fallback_reason = send_gate_reason
    results = shaped_bigram[:args.top]
    latency_ms = bigram_latency_ms
    usage = {}
    ranked_jev = []
    attempted = send_gate_reason is None

    if attempted:
        key = _get_typesafe_key()
        if not key:
            fallback_reason = "TYPESAFE_API_KEY を解決できない（env にも mise にも無い）"
        else:
            try:
                questions = build_questions(candidates)
                start = time.monotonic()
                resp = call_jev(jev_state, questions, key)
                latency_ms = round((time.monotonic() - start) * 1000)
                ranked_jev = jev_rank(candidates, resp.get("answers", {}))
                usage = resp.get("usage", {})
                router = "jev"
                results = shape_results(ranked_jev, "prob")[:args.top]
            except Exception as e:
                fallback_reason = str(e)

    if attempted:
        append_log({
            "timestamp": datetime.now(timezone.utc).astimezone().isoformat(),
            "subcommand": subcommand,
            "input": log_input,
            "router": router,
            "jev_top10": [{"path": p["path"], "prob": prob} for p, prob in ranked_jev[:10]],
            "bigram_top10": [{"path": p["path"], "score": score} for p, score in bigram_scored[:10]],
            "usage": usage,
            "latency_ms": latency_ms,
        }, args.no_log)

    out = {
        "router": router,
        "fallback_reason": fallback_reason,
        "results": results,
        "bigram_top": bigram_top,
        "usage": usage,
        "latency_ms": latency_ms,
    }
    if args.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        print(header(router, fallback_reason))
        for i, r in enumerate(results, 1):
            score = r.get("prob", r.get("score"))
            print(f"{i}. {r['path']}  {score:.3f}  {r['title']}")
    return 0 if results else 1


def cmd_route(root: Path, args) -> int:
    query = sys.stdin.read().strip() if args.query == "-" else args.query
    if not query:
        print("error: query が空です", file=sys.stderr)
        return 2

    candidates = routable_pages(load_all_pages(root))

    def build_questions(pages):
        return {
            f"p{i}": noul(
                f"Should this wiki page be referenced to answer the user's query `query`? "
                f"Page title: {page['title']}. Page description: {page['description']}.",
                "The page's subject directly supplies the answer to `query`.",
                "The page is unrelated or only tangential to `query`.",
            )
            for i, page in enumerate(pages)
        }

    def shape_results(pairs, score_key):
        rows = [
            {"path": p["path"], "title": p["title"], score_key: score, "abs_path": str(root / p["path"])}
            for p, score in pairs
        ]
        if score_key == "prob" and args.min_prob is not None:
            rows = [r for r in rows if r["prob"] >= args.min_prob]
        return rows

    send_gate_reason = resolve_send_gate(local_only=args.local_only)

    return run_router(
        root, args,
        subcommand="route", log_input=query,
        candidates=candidates,
        bigram_text_fn=lambda p: f"{p['title']} {p['description']}",
        bigram_query_text=query,
        jev_state={"query": query},
        build_questions=build_questions,
        send_gate_reason=send_gate_reason,
        shape_results=shape_results,
        header=lambda router, reason: f"router={router}" + (f"  (fallback: {reason})" if reason else ""),
    )


def cmd_links(root: Path, args) -> int:
    page_arg = args.page.lstrip("/")
    if not page_arg.endswith(".md"):
        page_arg += ".md"

    all_pages = load_all_pages(root)
    by_path = {p["path"]: p for p in all_pages}
    if page_arg not in by_path:
        print(f"error: ページが見つからない: {page_arg}", file=sys.stderr)
        return 2
    target = by_path[page_arg]

    all_paths = set(by_path)
    bundle_dirs = {p.name for p in root.iterdir() if p.is_dir()}
    linked = already_linked_paths(target, all_paths, bundle_dirs)

    candidates = [p for p in routable_pages(all_pages) if p["path"] != page_arg]
    body_excerpt = body_after_frontmatter(target["text"])[:BODY_EXCERPT_CHARS]
    query_text = f"{target['title'] or ''} {target['description'] or ''} {body_excerpt}"

    def build_questions(pages):
        # `state` に対象ページの title/description/body_excerpt を1回だけ渡している
        # （route の query 参照と同じ形）。ここで target の description を毎問 repeat
        # すると候補ページ数（200超）× 説明文の長さで input token が膨らみ
        # max_tokens_exceeded になる。
        return {
            f"p{i}": noul(
                f"Should this candidate wiki page be cross-linked with the page described in "
                f"`state` (its title, description, body_excerpt)? Candidate page title: "
                f"{page['title']}. Candidate page description: {page['description']}.",
                "Reading one page directly deepens understanding of the other; their subjects "
                "connect directly, not just by broad topic.",
                "The pages only share a broad topic area, or are unrelated.",
            )
            for i, page in enumerate(pages)
        }

    def shape_results(pairs, score_key):
        rows = []
        for p, score in pairs:
            is_linked = p["path"] in linked
            if is_linked and not args.include_linked:
                continue
            rows.append({
                "path": p["path"], "title": p["title"], score_key: score,
                "abs_path": str(root / p["path"]), "already_linked": is_linked,
            })
        return rows

    send_gate_reason = resolve_send_gate(local_only=args.local_only, page_local=is_local_path(page_arg))

    return run_router(
        root, args,
        subcommand="links", log_input=page_arg,
        candidates=candidates,
        bigram_text_fn=lambda p: f"{p['title']} {p['description']}",
        bigram_query_text=query_text,
        jev_state={"title": target["title"], "description": target["description"], "body_excerpt": body_excerpt},
        build_questions=build_questions,
        send_gate_reason=send_gate_reason,
        shape_results=shape_results,
        header=lambda router, reason: f"# {page_arg}  router={router}" + (f"  (fallback: {reason})" if reason else ""),
    )


def main() -> int:
    ap = argparse.ArgumentParser(
        description="wiki バンドルの自然文ルーター（route: 問い→ページ / links: ページ→リンク候補）")
    ap.add_argument("--root", default=DEFAULT_ROOT, help=f"bundle root (default: {DEFAULT_ROOT})")
    sub = ap.add_subparsers(dest="cmd", required=True)

    route_p = sub.add_parser(
        "route", formatter_class=argparse.RawDescriptionHelpFormatter,
        help="自然文の問いに対して参照すべきページを返す",
        epilog='例: python3 wiki_route.py route "エージェントに任せるかは検証のしやすさで決まる、とはどういうこと？" --json',
    )
    route_p.add_argument("query", help='問い。"-" で stdin から読む')
    route_p.add_argument("--json", action="store_true")
    route_p.add_argument("--top", type=int, default=5)
    route_p.add_argument("--min-prob", type=float, default=None, help="jev 使用時のみ有効な足切り閾値")
    route_p.add_argument("--local-only", action="store_true",
                          help="Jev を呼ばず bigram のみで返す（問いに業務・顧客情報を含むとき）")
    route_p.add_argument("--remote", action="store_true",
                          help="互換用。現在は既定で Jev を呼ぶため指定不要（--local-only は優先）")
    route_p.add_argument("--no-log", action="store_true")

    links_p = sub.add_parser(
        "links", formatter_class=argparse.RawDescriptionHelpFormatter,
        help="このページから相互リンクすべきページ候補を返す",
        epilog="例: python3 wiki_route.py links tech/oracle-problem.md --json",
    )
    links_p.add_argument("page", help="root からの相対 path（先頭 / の有無どちらも可）")
    links_p.add_argument("--json", action="store_true")
    links_p.add_argument("--top", type=int, default=5)
    links_p.add_argument("--include-linked", action="store_true", help="既にリンク済みのページも含める")
    links_p.add_argument("--local-only", action="store_true",
                          help="Jev を呼ばず bigram のみで返す（.local ページは指定なしでも常にこれになる）")
    links_p.add_argument("--no-log", action="store_true")

    args = ap.parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"error: bundle root が見つからない: {root}", file=sys.stderr)
        return 2

    if args.cmd == "route":
        return cmd_route(root, args)
    return cmd_links(root, args)


if __name__ == "__main__":
    raise SystemExit(main())
