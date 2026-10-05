#!/usr/bin/env python3
"""wiki バンドル（OKF v0.1）のリンクグラフツール（依存なし・stdlib のみ）。

PAGE の outbound リンクと backlinks（被リンク）を列挙する。knowledge graph の
traversal 用途に特化（横断検索・一覧は素の rg / grep で十分なので持たない）。

frontmatter は okf_check.py と同じ限定文法（1行スカラー）を正規表現で解析する
（YAML 非依存）。exit code: ヒットあり=0 / なし=1 / エラー=2（rg 互換）。
"""
import argparse
import json
import posixpath
import re
import sys
from pathlib import Path

DEFAULT_ROOT = "~/src/github.com/wwwyo/me/wiki"
# okf_check.py と同じ予約 meta 集合（frontmatter を持たない）
RESERVED = {"index.md", "log.md", "AGENTS.md", "CLAUDE.md"}
# okf_check.py と同じ link 抽出 regex（bundle 内 .md リンク）
LINK_RE = re.compile(r"\]\(([^)\s]+?\.md)(?:#[^)]*)?\)")
URL_RE = re.compile(r"^[a-z][a-z0-9+.\-]*://")


def parse_frontmatter(text: str):
    """先頭 `---` 行で開き `---` 単独行で閉じる frontmatter を返す。"""
    if not text.startswith("---\n"):
        return None
    lines = text.split("\n")
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            return "\n".join(lines[1:i])
    return None


def get_field(fm: str, key: str):
    m = re.search(rf"^{key}:[ \t]*(.*)$", fm, re.MULTILINE)
    return m.group(1).strip().strip("\"'") if m else None


def load_pages(root: Path):
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
            "type": get_field(fm, "type") if fm else None,
            "title": get_field(fm, "title") if fm else None,
            "description": get_field(fm, "description") if fm else None,
        })
    return pages


def header_line(page):
    kind = f"[{page['type'] or 'meta'}]"
    title = page["title"] or ""
    desc = page["description"] or ""
    parts = [page["path"], kind]
    if title:
        parts.append(f"{title} — {desc}" if desc else title)
    return "  ".join(parts)


def resolve_link(link, src_rel, all_paths, bundle_dirs):
    """link を分類して (kind, target_rel) を返す。kind: bundle/broken/external。"""
    if URL_RE.match(link):
        return "external", link
    if link.startswith("/"):
        tid = link.lstrip("/")
        if tid in all_paths:
            return "bundle", tid
        top = tid.split("/", 1)[0]
        if top in bundle_dirs:
            return "broken", tid
        return "external", link  # /raw・/daily 等 repo-root 参照
    resolved = posixpath.normpath(posixpath.join(posixpath.dirname(src_rel), link))
    if resolved.startswith(".."):
        return "external", link  # ../../raw 等 bundle 外
    if resolved in all_paths:
        return "bundle", resolved
    return "broken", resolved


def cmd_links(root, args):
    page_arg = args.page.lstrip("/")
    if not page_arg.endswith(".md"):
        page_arg += ".md"
    pages = load_pages(root)
    by_path = {p["path"]: p for p in pages}
    if page_arg not in by_path:
        print(f"error: ページが見つからない: {page_arg}", file=sys.stderr)
        return 2
    all_paths = set(by_path)
    bundle_dirs = {p.name for p in root.iterdir() if p.is_dir()}

    target = by_path[page_arg]
    outbound = []
    seen = set()
    for link in LINK_RE.findall(target["text"]):
        kind, resolved = resolve_link(link, page_arg, all_paths, bundle_dirs)
        if (kind, resolved) in seen:
            continue
        seen.add((kind, resolved))
        outbound.append({"link": link, "kind": kind,
                         "path": resolved if kind != "external" else None})

    backlinks = []
    for p in pages:
        if p["path"] == page_arg:
            continue
        for link in LINK_RE.findall(p["text"]):
            kind, resolved = resolve_link(link, p["path"], all_paths, bundle_dirs)
            if kind == "bundle" and resolved == page_arg:
                backlinks.append(p)
                break

    if args.json:
        print(json.dumps({
            "page": page_arg,
            "outbound": [{
                "link": o["link"], "kind": o["kind"], "path": o["path"],
                **({"title": by_path[o["path"]]["title"],
                    "description": by_path[o["path"]]["description"]}
                   if o["kind"] == "bundle" else {}),
            } for o in outbound],
            "backlinks": [{"path": p["path"], "title": p["title"],
                           "description": p["description"]} for p in backlinks],
        }, ensure_ascii=False, indent=2))
    else:
        print(f"# {header_line(target)}\n")
        print(f"## Outbound ({len(outbound)})")
        for o in outbound:
            if o["kind"] == "bundle":
                print(f"  {header_line(by_path[o['path']])}")
            elif o["kind"] == "broken":
                print(f"  {o['link']}  (broken)")
            else:
                print(f"  {o['link']}  (external)")
        print(f"\n## Backlinks ({len(backlinks)})")
        for p in backlinks:
            print(f"  {header_line(p)}")
    return 0 if outbound or backlinks else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="wiki バンドルのリンクグラフツール（outbound + backlinks）")
    ap.add_argument("--root", default=DEFAULT_ROOT, help=f"bundle root (default: {DEFAULT_ROOT})")
    ap.add_argument("page", help="bundle-relative path（/tech/ontology.md 等）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"error: bundle root が見つからない: {root}", file=sys.stderr)
        return 2
    return cmd_links(root, args)


if __name__ == "__main__":
    raise SystemExit(main())
