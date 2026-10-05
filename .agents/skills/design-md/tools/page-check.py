#!/usr/bin/env python3
"""生成ページの構図 check。

design-md-check.py は design.md 自体（未定義 var 参照・コントラスト比）しか見ておらず、
CSS を当てた後の生成ページの構図崩れ（テーブルが使える幅を使わない等）は拾えない。
headless Chrome がこの環境で動かないため、レイアウト計測は page-check.js をブラウザ内
（コンソール / javascript_tool / agent-browser eval --stdin）で実行して得た JSON を受け取り、
このスクリプトは静的な HTML/CSS ルールとその計測 JSON の判定だけを担当する。

page-check.py <design.md> <page.html> [--layout <measurements.json>] [--allow-classes <file>] [--json]

第1引数は視覚正本（repo root の design.md）。fenced ```css block からクラス名を拾う。
.css ファイルを直接渡すこともできる。

このファイルが正本。consumer（product-design 型 skill 等）はコピーせずここを直接実行する。
詳細は README.md 参照。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from check_common import Finding, format_human, line_of, spec_text

CSS_CLASS_DEF_RE = re.compile(r"\.([a-zA-Z_][a-zA-Z0-9_-]*)")
COLOR_LITERAL_RE = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\)|hsla?\([^)]*\)"
)
FONT_DECL_RE = re.compile(r"font-family\s*:\s*[^;]+;|font-size\s*:\s*[^;]+;")
EXTERNAL_HREF_RE = re.compile(r'href\s*=\s*["\']https?://[^"\']+["\']', re.IGNORECASE)
EXTERNAL_SRC_RE = re.compile(r'src\s*=\s*["\']https?://[^"\']+["\']', re.IGNORECASE)
IMPORT_URL_RE = re.compile(r'@import\s+url\(\s*["\']?https?://', re.IGNORECASE)
NEGATIVE_MARK_RE = re.compile(r"[-−▲]")
WIDTH_USAGE_THRESHOLD = 0.6
STRIP_ITEM_THRESHOLD = 0.6


def parse_spec_classes(css_text: str) -> set[str]:
    """design.md の css block で `.name { ... }` として定義済みのクラス名集合を返す。"""
    return set(CSS_CLASS_DEF_RE.findall(css_text))


def extract_negative_elements(html_text: str) -> list[tuple[str, int]]:
    """`class` に `negative` を含む要素のテキストと開始行を、簡易正規表現で抜き出す。

    HTMLParser のネスト追跡はコストが高いため、`negative` を含む開始タグから対応する
    終了タグ直前までを非貪欲マッチする単純な近似で十分とする（product-design のページは浅い構造）。
    """
    results = []
    for m in re.finditer(
        r'<([a-zA-Z0-9]+)\b[^>]*class\s*=\s*"[^"]*\bnegative\b[^"]*"[^>]*>(.*?)</\1>',
        html_text,
        re.DOTALL,
    ):
        inner_text = re.sub(r"<[^>]+>", "", m.group(2))
        results.append((inner_text.strip(), line_of(html_text, m.start())))
    return results


def rule_invented_color(html_text: str, filename: str) -> list[Finding]:
    """page の `<style>` / `style=` に直書きされた色リテラルを検出する。"""
    findings = []
    for style_content, base_line in _iter_style_and_inline(html_text):
        text, offset = style_content
        for m in COLOR_LITERAL_RE.finditer(text):
            ln = base_line if offset == -1 else line_of(html_text, offset + m.start())
            findings.append(
                Finding(
                    "invented-color",
                    "warning",
                    filename,
                    ln,
                    m.group(0),
                    "design.md の custom property ではなく色値を直接書いている",
                )
            )
    return findings


def rule_invented_font(html_text: str, filename: str) -> list[Finding]:
    """page の `<style>` / `style=` に直書きされたフォント指定を検出する。"""
    findings = []
    for style_content, base_line in _iter_style_and_inline(html_text):
        text, offset = style_content
        for m in FONT_DECL_RE.finditer(text):
            ln = base_line if offset == -1 else line_of(html_text, offset + m.start())
            findings.append(
                Finding(
                    "invented-font",
                    "warning",
                    filename,
                    ln,
                    m.group(0).strip(),
                    "design.md 由来ではなくフォント指定を直接書いている",
                )
            )
    return findings


def _iter_style_and_inline(html_text: str):
    """`<style>` 本文（offset 付き）と `style=` 属性値（行番号付き）をまとめて列挙する。"""
    for m in re.finditer(r"<style[^>]*>(.*?)</style>", html_text, re.DOTALL | re.IGNORECASE):
        yield (m.group(1), m.start(1)), 0
    for m in re.finditer(r'style\s*=\s*"([^"]*)"', html_text):
        ln = line_of(html_text, m.start())
        yield (m.group(1), -1), ln


def rule_unknown_class(html_text: str, filename: str, spec_classes: set[str], allow_classes: set[str]) -> list[Finding]:
    """design.md に定義がなく allowlist にもない class を検出する。"""
    findings = []
    used: dict[str, int] = {}
    for m in re.finditer(r'class\s*=\s*"([^"]*)"', html_text):
        ln = line_of(html_text, m.start())
        for cls in m.group(1).split():
            used.setdefault(cls, ln)
    for cls, ln in sorted(used.items()):
        if cls in spec_classes or cls in allow_classes:
            continue
        findings.append(
            Finding(
                "unknown-class",
                "info",
                filename,
                ln,
                cls,
                "design.md に未定義。レイアウト専用なら --allow-classes に足す、それ以外は語彙の欠落を疑う",
            )
        )
    return findings


def rule_negative_without_minus(html_text: str, filename: str) -> list[Finding]:
    """`.negative` 要素なのにマイナス記号を含まないテキストを検出する。"""
    findings = []
    for text, ln in extract_negative_elements(html_text):
        if text and not NEGATIVE_MARK_RE.search(text):
            findings.append(
                Finding(
                    "negative-without-minus",
                    "warning",
                    filename,
                    ln,
                    text,
                    "負値なのに -/−/▲ のいずれも含まない",
                )
            )
    return findings


def rule_external_resource(html_text: str, filename: str) -> list[Finding]:
    """外部リソース参照（link/script/@import/Google Fonts）を検出する。固定シナリオでは外部参照ゼロが前提。"""
    findings = []
    for m in re.finditer(r"<link\b[^>]*>", html_text, re.IGNORECASE):
        tag = m.group(0)
        if EXTERNAL_HREF_RE.search(tag) or "fonts.googleapis" in tag:
            findings.append(_external_finding(html_text, filename, m.start(), tag))
    for m in re.finditer(r"<script\b[^>]*>", html_text, re.IGNORECASE):
        tag = m.group(0)
        if EXTERNAL_SRC_RE.search(tag):
            findings.append(_external_finding(html_text, filename, m.start(), tag))
    for m in IMPORT_URL_RE.finditer(html_text):
        line_start = html_text.rfind("\n", 0, m.start()) + 1
        line_end = html_text.find("\n", m.start())
        line_end = line_end if line_end != -1 else len(html_text)
        findings.append(_external_finding(html_text, filename, m.start(), html_text[line_start:line_end].strip()))
    return findings


def _external_finding(html_text: str, filename: str, offset: int, text: str) -> Finding:
    return Finding(
        "external-resource",
        "error",
        filename,
        line_of(html_text, offset),
        text.strip(),
        "固定シナリオのページは外部リソース参照ゼロが前提。フォント・スクリプトは design.md / ページ内に閉じる",
    )


def rule_width_usage(layout: dict, filename: str) -> list[Finding]:
    """table / .stat-strip が親要素の幅を十分使えていない block を検出する。"""
    findings = []
    for block in layout.get("blocks", []):
        selector = block.get("selector", "")
        is_target = selector == "table" or selector.split(" > ")[-1].startswith("table") or ".stat-strip" in selector
        if not is_target:
            continue
        ratio = block.get("ratio", 1)
        if ratio < WIDTH_USAGE_THRESHOLD:
            findings.append(
                Finding(
                    "width-usage",
                    "warning",
                    filename,
                    0,
                    f"{selector} ratio={ratio:.2f}",
                    "使える幅を使っていない",
                )
            )
    return findings


def rule_strip_items_cramped(layout: dict, filename: str) -> list[Finding]:
    """`.stat-strip` の子要素の幅合計が strip 幅に対して小さい（左詰まり）を検出する。"""
    findings = []
    for item in layout.get("stripItems", []):
        ratio = item.get("ratio", 1)
        if ratio < STRIP_ITEM_THRESHOLD:
            findings.append(
                Finding(
                    "strip-items-cramped",
                    "warning",
                    filename,
                    0,
                    f"{item.get('selector', '')} ratio={ratio:.2f}",
                    "項目が左に詰まっている",
                )
            )
    return findings


def run_check(spec_path: Path, page_path: Path, layout: dict | None, allow_classes: set[str]) -> list[Finding]:
    """静的ルールと（あれば）レイアウト計測 JSON を判定し、finding の一覧を返す。"""
    spec_css_text = spec_text(spec_path)
    html_text = page_path.read_text(encoding="utf-8")
    spec_classes = parse_spec_classes(spec_css_text)
    filename = str(page_path)

    findings: list[Finding] = []
    if spec_path.suffix == ".md" and not spec_css_text.strip():
        findings.append(
            Finding(
                "no-css-block",
                "error",
                str(spec_path),
                1,
                spec_path.name,
                "design.md に fenced ```css block が見つからない。## Tokens / ## Components は ```css で書く約束",
            )
        )
    findings.extend(rule_invented_color(html_text, filename))
    findings.extend(rule_invented_font(html_text, filename))
    findings.extend(rule_unknown_class(html_text, filename, spec_classes, allow_classes))
    findings.extend(rule_negative_without_minus(html_text, filename))
    findings.extend(rule_external_resource(html_text, filename))

    if layout is None:
        findings.append(
            Finding(
                "layout-skipped",
                "info",
                filename,
                0,
                "--layout 未指定",
                "page-check.js をブラウザで実行して JSON を渡すとレイアウト判定が有効になる",
            )
        )
    else:
        findings.extend(rule_width_usage(layout, filename))
        findings.extend(rule_strip_items_cramped(layout, filename))

    return findings


def main(argv: list[str]) -> int:
    if not argv:
        print(
            "usage: page-check.py <design.md> <page.html> [--layout <measurements.json>] "
            "[--allow-classes <file>] [--json]",
            file=sys.stderr,
        )
        return 2

    as_json = "--json" in argv
    layout_path: Path | None = None
    allow_classes_path: Path | None = None
    positional: list[str] = []

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--json":
            i += 1
            continue
        if arg == "--layout":
            layout_path = Path(argv[i + 1])
            i += 2
            continue
        if arg == "--allow-classes":
            allow_classes_path = Path(argv[i + 1])
            i += 2
            continue
        positional.append(arg)
        i += 1

    if len(positional) < 2:
        print("error: design.md と page.html の両方が必要", file=sys.stderr)
        return 2

    spec_path, page_path = Path(positional[0]), Path(positional[1])
    if not spec_path.is_file():
        print(f"error: {spec_path} が見つからない", file=sys.stderr)
        return 2
    if not page_path.is_file():
        print(f"error: {page_path} が見つからない", file=sys.stderr)
        return 2

    layout = None
    if layout_path is not None:
        if not layout_path.is_file():
            print(f"error: {layout_path} が見つからない", file=sys.stderr)
            return 2
        layout = json.loads(layout_path.read_text(encoding="utf-8"))

    allow_classes: set[str] = set()
    if allow_classes_path is not None:
        if not allow_classes_path.is_file():
            print(f"error: {allow_classes_path} が見つからない", file=sys.stderr)
            return 2
        allow_classes = {
            line.strip()
            for line in allow_classes_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    findings = run_check(spec_path, page_path, layout, allow_classes)

    if as_json:
        for f in findings:
            print(json.dumps(f.as_dict(), ensure_ascii=False))
    else:
        for f in findings:
            print(format_human(f))

    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
