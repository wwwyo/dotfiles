#!/usr/bin/env python3
"""design.md の機械可読チェック。

未定義の custom property 参照とコントラスト比不足を検出する。
design-md-check.py <design.md> [scan paths...] [--json]

design.md の `## Tokens` / `## Components` は fenced ```css block で書く約束なので、
.md 入力では css block だけを取り出して検査する（行番号は .md のものを維持）。
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

SCAN_EXTENSIONS = {".css", ".html", ".tsx", ".jsx", ".vue", ".svelte"}

CUSTOM_PROP_DEF_RE = re.compile(r"(--[a-zA-Z0-9_-]+)\s*:\s*([^;{}]+);")
VAR_REF_RE = re.compile(r"var\(\s*(--[a-zA-Z0-9_-]+)\s*(?:,\s*((?:[^()]|\([^()]*\))*))?\)")
COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)

HEX_RE = re.compile(r"^#([0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
RGB_RE = re.compile(
    r"^rgba?\(\s*([\d.]+)(%?)\s*[,\s]\s*([\d.]+)(%?)\s*[,\s]\s*([\d.]+)(%?)"
    r"(?:\s*[,/]\s*([\d.]+)(%?))?[\s]*\)$"
)


def strip_comments(css: str) -> str:
    """CSS コメントを解析前に除去する（コメント内の var/property 定義を誤検出しないため）。

    改行は保持して行番号を保つ。
    """
    def replace_comment(m):
        return "\n" * m.group(0).count("\n")
    return COMMENT_RE.sub(replace_comment, css)


def parse_rules_from_blocks(css: str, base: int = 0) -> list[tuple[str, str, int, int]]:
    """CSS を brace カウントで解析し、通常 rule の (selector, body, start_offset, body_offset) を返す。

    at-rule（@media / @supports 等）は外側 block を剥がして中の rule を返す。
    文字列リテラル内の `{` `}` `;` は無視する。offset は元の css 先頭からの位置。
    body_offset は `{` 直後の位置を指す。body は strip しない — `body_offset + i`
    がそのまま css 内 offset になり、decl の正確な行番号が取れる。
    """
    n = len(css)

    def skip_string(j: int) -> int:
        quote = css[j]
        j += 1
        while j < n and css[j] != quote:
            j += 2 if css[j] == "\\" else 1
        return j + 1

    def block_end(j: int) -> int:
        depth = 0
        while j < n:
            c = css[j]
            if c in "\"'":
                j = skip_string(j)
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
                if depth == 0:
                    return j
            j += 1
        return n

    rules: list[tuple[str, str, int, int]] = []
    i = 0
    while i < n:
        if css[i].isspace():
            i += 1
            continue
        start = i
        while i < n and css[i] not in "{;":
            i = skip_string(i) if css[i] in "\"'" else i + 1
        if i >= n:
            break
        if css[i] == ";":
            i += 1
            continue
        prelude = css[start:i].strip()
        end = block_end(i)
        body = css[i + 1 : end]
        if prelude.startswith("@"):
            rules.extend(parse_rules_from_blocks(body, base + i + 1))
        elif prelude:
            rules.append((prelude, body, base + start, base + i + 1))
        i = end + 1
    return rules


def parse_custom_properties(css: str) -> dict[str, tuple[str, int]]:
    """`--name: value;` の定義を { name: (value, line) } で返す。後勝ちで上書きする。"""
    props: dict[str, tuple[str, int]] = {}
    for m in CUSTOM_PROP_DEF_RE.finditer(css):
        name, value = m.group(1), m.group(2).strip()
        props[name] = (value, line_of(css, m.start()))
    return props


def find_var_refs(css: str) -> list[tuple[str, str | None, int, str]]:
    """`var(--name[, fallback])` の出現を (name, fallback, line, matched_text) で返す。"""
    refs = []
    for m in VAR_REF_RE.finditer(css):
        name = m.group(1)
        fallback = m.group(2)
        refs.append((name, fallback.strip() if fallback else None, line_of(css, m.start()), m.group(0)))
    return refs


def find_var_refs_in_fallback(fallback: str) -> list[tuple[str, str | None]]:
    """fallback テキスト内の var 参照を再帰的に抽出する。

    Returns: [(name, nested_fallback), ...]
    """
    refs = []
    for m in VAR_REF_RE.finditer(fallback):
        name = m.group(1)
        nested_fallback = m.group(2)
        refs.append((name, nested_fallback.strip() if nested_fallback else None))
        if nested_fallback:
            refs.extend(find_var_refs_in_fallback(nested_fallback))
    return refs


def resolve_color(value: str, props: dict[str, tuple[str, int]], _seen: frozenset[str] = frozenset()) -> tuple[float, float, float] | None:
    """色値を (r, g, b) の 0-255 タプルへ解決する。解決不能なら None。

    alpha < 1 の場合も None を返す（合成が必要なため判定できない）。
    """
    value = value.strip()

    m = VAR_REF_RE.fullmatch(value)
    if m:
        name = m.group(1)
        if name in _seen:
            return None
        if name in props:
            return resolve_color(props[name][0], props, _seen | {name})
        fallback = m.group(2)
        if fallback:
            return resolve_color(fallback.strip(), props, _seen | {name})
        return None

    hex_m = HEX_RE.match(value)
    if hex_m:
        h = hex_m.group(1)
        if len(h) in (3, 4):
            h = "".join(ch * 2 for ch in h)
        channels = [int(h[i : i + 2], 16) for i in range(0, len(h), 2)]
        if len(channels) == 4 and channels[3] < 255:
            return None
        return tuple(channels[:3])

    rgb_m = RGB_RE.match(value)
    if rgb_m:
        r_str, r_pct, g_str, g_pct, b_str, b_pct, a_str, a_pct = rgb_m.groups()

        # Parse RGB values
        try:
            r = float(r_str)
            g = float(g_str)
            b = float(b_str)
        except ValueError:
            return None

        # Convert percentage to 0-255
        if r_pct:
            r = r * 2.55
        if g_pct:
            g = g * 2.55
        if b_pct:
            b = b * 2.55

        # Check ranges
        if not (0 <= r <= 255) or not (0 <= g <= 255) or not (0 <= b <= 255):
            return None

        # Check alpha
        if a_str is not None:
            try:
                a = float(a_str)
            except ValueError:
                return None
            if a_pct:
                a = a / 100.0
            if a < 1.0:
                return None

        return (r, g, b)

    return None


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG の相対輝度を計算する。"""

    def channel(c: float) -> float:
        c = c / 255.0
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(rgb1: tuple[float, float, float], rgb2: tuple[float, float, float]) -> float:
    l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def rule_undefined_and_fallback_var(css: str, filename: str, all_props: dict[str, tuple[str, int]]) -> list[Finding]:
    findings = []
    for name, fallback, ln, matched in find_var_refs(css):
        if name in all_props:
            # Check for undefined vars in fallback recursively
            if fallback:
                for fb_name, _ in find_var_refs_in_fallback(fallback):
                    if fb_name not in all_props:
                        findings.append(
                            Finding(
                                "undefined-var",
                                "error",
                                filename,
                                ln,
                                matched,
                                f"{fb_name} が fallback 内で参照されているが未定義",
                            )
                        )
            continue
        if fallback is not None:
            findings.append(
                Finding(
                    "fallback-var",
                    "warning",
                    filename,
                    ln,
                    matched,
                    f"--{name.lstrip('-')} が未定義。fallback 値 {fallback!r} がそのまま描画され続ける可能性がある",
                )
            )
            # Also check for undefined vars in fallback
            for fb_name, _ in find_var_refs_in_fallback(fallback):
                if fb_name not in all_props:
                    findings.append(
                        Finding(
                            "undefined-var",
                            "error",
                            filename,
                            ln,
                            matched,
                            f"{fb_name} が fallback 内で参照されているが未定義",
                        )
                    )
        else:
            findings.append(
                Finding(
                    "undefined-var",
                    "error",
                    filename,
                    ln,
                    matched,
                    f"{name} を design.md または scan 対象のどこにも定義していない",
                )
            )
    return findings


def rule_contrast_same_block(css: str, filename: str, all_props: dict[str, tuple[str, int]]) -> tuple[list[Finding], set[str]]:
    """同一 rule block 内の color / background(-color) の組をコントラスト判定する。

    入れ子 block（@media など）内の rule も検査する。
    """
    findings: list[Finding] = []
    unresolved_reported: set[str] = set()
    rules = parse_rules_from_blocks(css)

    for selector, body, start_offset, _body_offset in rules:
        if not body.endswith(";"):
            body += ";"
        color_m = re.search(r"(?<![-\w])color\s*:\s*([^;]+);", body)
        bg_m = re.search(r"background(?:-color)?\s*:\s*([^;]+);", body)
        if not color_m or not bg_m:
            continue
        color_val, bg_val = color_m.group(1).strip(), bg_m.group(1).strip()
        ln = line_of(css, start_offset)

        color_rgb = resolve_color(color_val, all_props)
        bg_rgb = resolve_color(bg_val, all_props)

        if color_rgb is None:
            key = f"{filename}:{ln}:{color_val}"
            if key not in unresolved_reported:
                unresolved_reported.add(key)
                findings.append(
                    Finding("unresolved-color", "info", filename, ln, color_val, "解決不能な色値のためコントラスト判定を skip した")
                )
        if bg_rgb is None:
            key = f"{filename}:{ln}:{bg_val}"
            if key not in unresolved_reported:
                unresolved_reported.add(key)
                findings.append(
                    Finding("unresolved-color", "info", filename, ln, bg_val, "解決不能な色値のためコントラスト判定を skip した")
                )
        if color_rgb is None or bg_rgb is None:
            continue

        ratio = contrast_ratio(color_rgb, bg_rgb)
        if ratio < 4.5:
            findings.append(
                Finding(
                    "contrast-ratio",
                    "warning",
                    filename,
                    ln,
                    f"{selector} {{ color: {color_val}; background: {bg_val}; }}",
                    f"WCAG AA 4.5:1 未満（実測 {ratio:.2f}:1）",
                )
            )
    return findings, unresolved_reported


def pair_base_name(name: str) -> str | None:
    """foreground ペア規約から base 名を返す。ペアでなければ None。

    shadcn/ui 規約: `--x-foreground` → `--x`、`--foreground` → `--background`。
    旧 `on-` 規約（`--on-x` / `--<p>-on-x` → `--x` / `--<p>-x`）も拾う。
    """
    if name == "--foreground":
        return "--background"
    if name.endswith("-foreground"):
        return name.removesuffix("-foreground")
    stripped = name.lstrip("-")
    idx = stripped.find("on-")
    if idx == -1:
        return None
    prefix = stripped[:idx]
    base_key = stripped[idx + len("on-"):]
    return f"--{prefix}{base_key}"


def rule_contrast_pairs(
    css: str,
    filename: str,
    all_props: dict[str, tuple[str, int]],
    prop_files: dict[str, str],
    already_unresolved: set[str],
) -> list[Finding]:
    """`-foreground` / `on-` 命名規約のペアを rule block（スコープ）ごとにコントラスト判定する。

    `:root` と `.dark` で同じ名前が別の値を持ち得るため、block 単位で判定する。
    ペアの片方だけを再定義する block（例: `.dark` が `--primary` だけ上書き）も対象 —
    もう片方は外側スコープ（`:root`・トップレベル・scan 対象 file）から継承値を解決する。
    兄弟 scope の値は継承しない（`.sepia` の定義は `.dark` の評価に混ざらない）。
    """
    findings: list[Finding] = []

    def is_outer_scope(selector: str) -> bool:
        # design.md の convention は `:root` / `.dark`。`:root.dark` や `html:root` のような
        # compound は scope 扱いする（中身は条件付きで、全 scope に無条件継承されるわけではない）。
        return selector.strip() in (":root", "html", "*")

    blocks: list[tuple[str, dict[str, tuple[str, int]]]] = []
    scoped_names: set[str] = set()
    root_props: dict[str, tuple[str, int]] = {}
    for selector, body, _start_offset, body_offset in parse_rules_from_blocks(css):
        props: dict[str, tuple[str, int]] = {}
        for m in CUSTOM_PROP_DEF_RE.finditer(body):
            props[m.group(1)] = (m.group(2).strip(), line_of(css, body_offset + m.start()))
        if not props:
            continue
        blocks.append((selector, props))
        if is_outer_scope(selector):
            root_props.update(props)
        else:
            scoped_names.update(props)

    # どの block からも見える外側スコープ — class scope（.dark 等）の定義は
    # 兄弟 scope に継承されないので除く。all_props は同名 last-wins で scope 値が
    # 残っていることがあるため、:root 系 block の定義を必ず上書きで戻す。
    outer_props = {
        **{k: v for k, v in all_props.items() if k not in scoped_names},
        **root_props,
    }

    def emit_pair(
        name: str, base_name: str,
        fg: tuple[str, int], base: tuple[str, int],
        fg_file: str, base_file: str,
        selector: str, scope_props: dict[str, tuple[str, int]],
    ) -> None:
        fg_val, fg_line = fg
        base_val, base_line = base
        fg_rgb = resolve_color(fg_val, scope_props)
        base_rgb = resolve_color(base_val, scope_props)
        for val, ln, rgb, file in (
            (fg_val, fg_line, fg_rgb, fg_file),
            (base_val, base_line, base_rgb, base_file),
        ):
            if rgb is not None:
                continue
            key = f"{file}:{ln}:{val}"
            if key not in already_unresolved:
                already_unresolved.add(key)
                findings.append(
                    Finding("unresolved-color", "info", file, ln, val, "解決不能な色値のためコントラスト判定を skip した")
                )
        if fg_rgb is None or base_rgb is None:
            return
        ratio = contrast_ratio(fg_rgb, base_rgb)
        if ratio < 4.5:
            findings.append(
                Finding(
                    "contrast-ratio",
                    "warning",
                    fg_file,
                    fg_line,
                    f"{selector} {{ {name}: {fg_val}; }} /* on {base_name}: {base_val} */",
                    f"WCAG AA 4.5:1 未満（実測 {ratio:.2f}:1）",
                )
            )

    def lookup(name: str, block_props: dict[str, tuple[str, int]]) -> tuple[tuple[str, int], str]:
        # block 定義は spec file 由来。外側スコープから拾った場合は定義ファイルを prop_files から引く
        if name in block_props:
            return block_props[name], filename
        return outer_props[name], prop_files.get(name, filename)

    touched: set[tuple[str, str]] = set()
    for selector, block_props in blocks:
        scope_props = {**outer_props, **block_props}
        candidates = {
            name: base
            for name in set(block_props) | set(outer_props)
            if (base := pair_base_name(name))
        }
        for name in sorted(candidates):
            base_name = candidates[name]
            if name not in block_props and base_name not in block_props:
                continue  # この scope ではペアに触れていない — 外側 scope で判定する
            touched.add((name, base_name))
            if name not in block_props | outer_props or base_name not in block_props | outer_props:
                continue
            fg, fg_file = lookup(name, block_props)
            base, base_file = lookup(base_name, block_props)
            emit_pair(name, base_name, fg, base, fg_file, base_file, selector, scope_props)

    # どの spec block にも属さないペア（scan file やトップレベルのみに定義）を残存パスで判定する。
    for name in sorted(outer_props):
        base_name = pair_base_name(name)
        if not base_name or (name, base_name) in touched:
            continue
        base = outer_props.get(base_name)
        if base is None:
            continue
        emit_pair(
            name, base_name, outer_props[name], base,
            prop_files.get(name, filename), prop_files.get(base_name, filename),
            ":root", outer_props,
        )
    return findings


def rule_token_summary(filename: str, defined_count: int, ref_count: int) -> Finding:
    return Finding(
        "token-summary",
        "info",
        filename,
        1,
        f"defined={defined_count} refs={ref_count}",
        "custom property の定義数と参照数のサマリ",
    )


def iter_scan_files(paths: list[Path]) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            for ext in SCAN_EXTENSIONS:
                files.extend(sorted(p.rglob(f"*{ext}")))
    return files


def run_check(spec_path: Path, scan_paths: list[Path]) -> list[Finding]:
    findings: list[Finding] = []

    spec_css_text = spec_text(spec_path)
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
    spec_css_text = strip_comments(spec_css_text)

    scan_files = [spec_path] + [f for f in iter_scan_files(scan_paths) if f.resolve() != spec_path.resolve()]

    # 全ファイル横断で custom property 定義を集約する（design.md 以外での定義も許容するため）。
    all_props: dict[str, tuple[str, int]] = {}
    prop_files: dict[str, str] = {}
    file_texts: dict[Path, str] = {}
    for f in scan_files:
        try:
            if f == spec_path:
                text = spec_css_text
            else:
                text = strip_comments(spec_text(f))
        except (UnicodeDecodeError, OSError):
            continue
        file_texts[f] = text
        # design.md 自身の行番号を保つため、定義元ファイルの props は spec のものを優先しつつ他ファイルでもマージする。
        for name, (value, ln) in parse_custom_properties(text).items():
            if name not in all_props:
                all_props[name] = (value, ln)
                prop_files[name] = str(f)

    total_refs = 0

    for f, text in file_texts.items():
        rel = str(f)
        findings.extend(rule_undefined_and_fallback_var(text, rel, all_props))
        total_refs += len(find_var_refs(text))

        if f.suffix in (".css", ".md"):
            block_findings, unresolved = rule_contrast_same_block(text, rel, all_props)
            findings.extend(block_findings)
            if f == spec_path:
                findings.extend(rule_contrast_pairs(text, rel, all_props, prop_files, unresolved))

    findings.append(rule_token_summary(str(spec_path), len(all_props), total_refs))

    return findings


def main(argv: list[str]) -> int:
    if not argv:
        print("usage: design-md-check.py <design.md> [scan paths...] [--json]", file=sys.stderr)
        return 2

    as_json = "--json" in argv
    positional = [a for a in argv if a != "--json"]

    if not positional:
        print("usage: design-md-check.py <design.md> [scan paths...] [--json]", file=sys.stderr)
        return 2
    spec_path = Path(positional[0])
    if not spec_path.is_file():
        print(f"error: {spec_path} が見つからない", file=sys.stderr)
        return 2

    scan_paths = [Path(p) for p in positional[1:]] if len(positional) > 1 else [spec_path]
    if spec_path not in scan_paths:
        scan_paths = [spec_path] + scan_paths

    findings = run_check(spec_path, scan_paths)

    if as_json:
        for f in findings:
            print(json.dumps(f.as_dict(), ensure_ascii=False))
    else:
        for f in findings:
            print(format_human(f))

    return 1 if any(f.severity == "error" for f in findings) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
