"""design-md-check.py の unittest。"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "design_md_check", Path(__file__).parent / "design-md-check.py"
)
check = importlib.util.module_from_spec(_spec)
sys.modules["design_md_check"] = check
_spec.loader.exec_module(check)


def write_file(tmpdir: Path, name: str, content: str) -> Path:
    p = tmpdir / name
    p.write_text(content, encoding="utf-8")
    return p


def design_md(css: str) -> str:
    return f"# Design — test\n\n## Tokens\n\n```css\n{css}\n```\n"


class UndefinedVarTest(unittest.TestCase):
    def test_undefined_var_is_error(self):
        css = """
        .btn { color: var(--not-defined); }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        rules = [f.rule for f in findings if f.rule == "undefined-var"]
        self.assertEqual(len(rules), 1)
        self.assertEqual(findings[0].severity, "error")

    def test_defined_var_is_not_flagged(self):
        css = """
        :root { --primary: #1B6E5C; }
        .btn { color: var(--primary); }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        rules = [f.rule for f in findings if f.rule in ("undefined-var", "fallback-var")]
        self.assertEqual(rules, [])


class DesignMdInputTest(unittest.TestCase):
    def test_css_block_in_md_is_parsed(self):
        md = design_md("""
:root { --primary: #1b6e5c; }
.btn { color: var(--primary); }
""")
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.md", md)
            findings = check.run_check(path, [path])
        rules = [f.rule for f in findings if f.rule in ("undefined-var", "fallback-var")]
        self.assertEqual(rules, [])

    def test_undefined_var_in_md_is_error_with_md_line(self):
        md = design_md(".btn { color: var(--not-defined); }")
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.md", md)
            findings = check.run_check(path, [path])
        undefined = [f for f in findings if f.rule == "undefined-var"]
        self.assertEqual(len(undefined), 1)
        # ```css fence が 5 行目、対象は 6 行目
        self.assertEqual(undefined[0].line, 6)

    def test_prose_outside_css_block_is_ignored(self):
        md = "# Design\n\n`var(--fake)` と --also-fake を prose に書いても検査しない\n\n" + design_md(":root { --a: #fff; }")
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.md", md)
            findings = check.run_check(path, [path])
        undefined = [f for f in findings if f.rule in ("undefined-var", "fallback-var")]
        self.assertEqual(undefined, [])

    def test_md_without_css_block_is_error(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.md", "# Design\n\ntokens なし\n")
            findings = check.run_check(path, [path])
        no_block = [f for f in findings if f.rule == "no-css-block"]
        self.assertEqual(len(no_block), 1)
        self.assertEqual(no_block[0].severity, "error")

    def test_longer_backtick_css_opener_is_recognized(self):
        md = "# Design\n\n````css\n:root { --primary: #1b6e5c; }\n.x { color: var(--primary); }\n````\n"
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.md", md)
            findings = check.run_check(path, [path])
        undefined = [f for f in findings if f.rule in ("undefined-var", "fallback-var", "no-css-block")]
        self.assertEqual(undefined, [])

    def test_non_css_fence_marker_inside_css_does_not_close(self):
        """```python のような他言語 marker 行は css block を閉じない。"""
        md = design_md(":root { --primary: #1b6e5c; }\n```python\n.x { color: var(--missing); }\n")
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.md", md)
            findings = check.run_check(path, [path])
        # ```python で閉じると .x 行が css 外に追い出され undefined-var が出ない。
        # fence を閉じない実装では .x は css 内に残り、var(--missing) が error になる
        undefined = [f for f in findings if f.rule == "undefined-var"]
        self.assertEqual(len(undefined), 1)

    def test_four_space_indent_is_code_block_not_fence(self):
        """4スペース以上のインデントは markdown の code block — fence として開かない。"""
        md = (
            "# Design\n\n"
            "    ```css\n"
            "    :root { --primary: #1b6e5c; }\n"
            "    ```\n"
        )
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.md", md)
            findings = check.run_check(path, [path])
        no_block = [f for f in findings if f.rule == "no-css-block"]
        self.assertEqual(len(no_block), 1)

    def test_css_inside_longer_non_css_fence_is_not_opened(self):
        """````text の中の ```css は css block を開始しない。"""
        md = "# Design\n\n````text\n```css\n:root { --primary: #1b6e5c; }\n```\n````\n"
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.md", md)
            findings = check.run_check(path, [path])
        no_block = [f for f in findings if f.rule == "no-css-block"]
        self.assertEqual(len(no_block), 1)


class FallbackVarTest(unittest.TestCase):
    def test_fallback_var_not_undefined(self):
        css = """
        .btn { color: var(--not-defined, #000000); }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        rules = [f.rule for f in findings if f.rule in ("undefined-var", "fallback-var")]
        self.assertEqual(rules, ["fallback-var"])
        fallback_finding = next(f for f in findings if f.rule == "fallback-var")
        self.assertEqual(fallback_finding.severity, "warning")


class ContrastSameBlockTest(unittest.TestCase):
    def test_low_contrast_pair_is_warning(self):
        css = """
        .low { color: #ffffff; background: #f0f0f0; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(len(contrast), 1)
        self.assertEqual(contrast[0].severity, "warning")

    def test_high_contrast_pair_is_ok(self):
        css = """
        .ok { color: #000000; background: #ffffff; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(contrast, [])

    def test_last_declaration_without_semicolon_is_checked(self):
        css = """
        .low { color: #ffffff; background: #f0f0f0 }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(len(contrast), 1)


class ContrastForegroundPairTest(unittest.TestCase):
    def test_foreground_pair_checked(self):
        css = """
        :root {
          --primary: #f0f0f0;
          --primary-foreground: #ffffff;
        }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(len(contrast), 1)

    def test_foreground_alone_pairs_with_background(self):
        css = """
        :root {
          --background: #ffffff;
          --foreground: #ffffff;
        }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(len(contrast), 1)

    def test_on_prefix_pair_still_checked(self):
        css = """
        :root {
          --color-primary: #f0f0f0;
          --color-on-primary: #ffffff;
        }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(len(contrast), 1)

    def test_pair_finding_reports_decl_line(self):
        """複数行 block でも finding の行番号は対象 decl の行を指す。"""
        css = ":root {\n  --primary: #f0f0f0;\n  --primary-hover: #154f42;\n  --primary-foreground: #ffffff;\n}\n"
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(len(contrast), 1)
        # --primary-foreground は 4 行目（strip ずれだと 3 行目になる）
        self.assertEqual(contrast[0].line, 4)
        self.assertIn("--primary-foreground", contrast[0].text)


class ContrastScopeTest(unittest.TestCase):
    def test_dark_scope_pairs_checked_separately(self):
        """`:root` と `.dark` のペアはそれぞれのスコープの値で判定する。"""
        css = """
        :root {
          --primary: #1b6e5c;
          --primary-foreground: #ffffff;
        }
        .dark {
          --primary: #f0f0f0;
          --primary-foreground: #ffffff;
        }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        # .dark のペアだけが低コントラスト
        self.assertEqual(len(contrast), 1)
        self.assertIn(".dark", contrast[0].text)

    def test_partial_dark_override_still_checks_pair(self):
        """`.dark` がペアの片方だけ上書きしても、継承されたもう片方と組み合わせて判定する。"""
        css = """
        :root {
          --primary: #1b6e5c;
          --primary-foreground: #ffffff;
        }
        .dark {
          --primary: #f0f0f0;
        }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        # .dark: #f0f0f0 背景に継承した白文字 = 実測 1.14:1
        self.assertEqual(len(contrast), 1)
        self.assertIn(".dark", contrast[0].text)

    def test_partial_dark_override_ok_pair_not_flagged(self):
        """片方だけ上書きしても継承値とのコントラストが足りれば warning にしない。"""
        css = """
        :root {
          --primary: #1b6e5c;
          --primary-foreground: #ffffff;
        }
        .dark {
          --primary: #154f42;
        }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(contrast, [])

    def test_sibling_scope_values_do_not_leak(self):
        """`.dark` で定義した名前が `:root` scope の判定に混入しない。"""
        css = """
        :root {
          --primary: #1b6e5c;
        }
        .dark {
          --primary-foreground: #f0f0f0;
        }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        # :root 側では --primary-foreground が見えないのでペア未成立。
        # .dark 側では fg 定義済み + base は :root 継承 → #1b6e5c 上の #f0f0f0 は十分なコントラスト
        self.assertEqual(contrast, [])

    def test_root_value_survives_when_sibling_redefines(self):
        """`:root` と `.dark` 両方が定義する名前でも、第三の scope は :root 値を継承して判定する。"""
        css = """
        :root {
          --primary: #f0f0f0;
        }
        .dark {
          --primary: #111111;
          --primary-foreground: #ffffff;
        }
        .sepia {
          --primary-foreground: #ffffff;
        }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        # .sepia は :root の --primary (#f0f0f0) を継承 → 白文字で実測 1.16:1。
        # outer_props が scoped 名を落とす実装だとこの finding が丸ごと消える
        self.assertEqual(len(contrast), 1)
        self.assertIn(".sepia", contrast[0].text)

    def test_pair_defined_only_in_scan_file_is_checked(self):
        """spec の rule block を持たないペア（scan file のみの定義）も残存パスで判定する。"""
        spec_css = ":root { --other: #000000; }\n"
        scan_css = ":root { --x: #f0f0f0; --x-foreground: #ffffff; }\n"
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.css", spec_css)
            scan = write_file(Path(d), "tokens.css", scan_css)
            findings = check.run_check(spec, [spec, scan])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(len(contrast), 1)
        # finding は spec ではなく定義元の scan file に帰属する
        self.assertEqual(contrast[0].file, str(scan))


class RecursiveVarResolutionTest(unittest.TestCase):
    def test_chain_resolves(self):
        css = """
        :root {
          --a: var(--b);
          --b: #ffffff;
        }
        .x { color: var(--a); background: #000000; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        rules = [f.rule for f in findings if f.rule in ("undefined-var", "fallback-var", "unresolved-color")]
        self.assertEqual(rules, [])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(contrast, [])  # black on white is high contrast


class UnresolvedColorTest(unittest.TestCase):
    def test_oklch_reported_and_not_contrast_checked(self):
        css = """
        .x { color: oklch(62% 0.18 250); background: #ffffff; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        unresolved = [f for f in findings if f.rule == "unresolved-color"]
        self.assertEqual(len(unresolved), 1)
        self.assertEqual(unresolved[0].severity, "info")
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(contrast, [])


class ExitCodeTest(unittest.TestCase):
    def test_exit_code_1_when_error(self):
        css = ".x { color: var(--missing); }"
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            code = check.main([str(path)])
        self.assertEqual(code, 1)

    def test_exit_code_0_when_no_error(self):
        css = ":root { --primary: #000000; }\n.x { color: var(--primary); background: #ffffff; }"
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            code = check.main([str(path)])
        self.assertEqual(code, 0)


class NestedBlockTest(unittest.TestCase):
    def test_contrast_in_media_block_is_warning(self):
        css = """
        @media (prefers-color-scheme: dark) {
          .low { color: #ffffff; background: #f0f0f0; }
        }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(len(contrast), 1)
        self.assertEqual(contrast[0].severity, "warning")

    def test_custom_prop_redefined_in_media_is_recognized(self):
        css = """
        :root { --primary: #1B6E5C; }
        @media (prefers-color-scheme: dark) {
          :root { --primary: #3d4e47; }
        }
        .btn { color: var(--primary); }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        undefined = [f for f in findings if f.rule in ("undefined-var", "fallback-var")]
        self.assertEqual(undefined, [])


class FallbackVarNestedTest(unittest.TestCase):
    def test_undefined_var_in_nested_fallback(self):
        css = """
        .btn { color: var(--a, var(--missing)); }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        undefined = [f for f in findings if f.rule == "undefined-var"]
        self.assertEqual(len(undefined), 1)
        self.assertIn("--missing", undefined[0].text)

    def test_nested_fallback_resolves_correctly(self):
        css = """
        :root { --a: #000000; --b: #ffffff; }
        .btn { color: var(--a, var(--b)); background: #000000; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        undefined = [f for f in findings if f.rule in ("undefined-var", "fallback-var")]
        self.assertEqual(undefined, [])


class CircularVarTest(unittest.TestCase):
    def test_circular_var_reference_no_crash(self):
        css = """
        :root {
          --a: var(--b);
          --b: var(--a);
        }
        .x { color: var(--a); background: #000000; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        unresolved = [f for f in findings if f.rule == "unresolved-color"]
        self.assertGreater(len(unresolved), 0)


class CommentLineNumberTest(unittest.TestCase):
    def test_line_numbers_after_multiline_comment(self):
        css = "/* comment\nline2\nline3 */\n.low { color: #ffffff; background: #f0f0f0; }"
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(len(contrast), 1)
        # Line number should be 4 due to multiline comment (3 lines in comment + 1 for rule)
        self.assertEqual(contrast[0].line, 4)


class AlphaChannelTest(unittest.TestCase):
    def test_rgba_with_alpha_is_unresolved(self):
        css = """
        .x { color: rgba(255, 255, 255, 0.5); background: #000000; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        unresolved = [f for f in findings if f.rule == "unresolved-color"]
        self.assertEqual(len(unresolved), 1)
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(contrast, [])

    def test_rgba_with_full_alpha_resolves(self):
        css = """
        .x { color: rgba(0, 0, 0, 1); background: #ffffff; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        unresolved = [f for f in findings if f.rule == "unresolved-color"]
        self.assertEqual(unresolved, [])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(contrast, [])

    def test_hex8_with_alpha_is_unresolved(self):
        css = """
        .x { color: #ffffff80; background: #000000; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        unresolved = [f for f in findings if f.rule == "unresolved-color"]
        self.assertEqual(len(unresolved), 1)


class PercentageRGBTest(unittest.TestCase):
    def test_percentage_rgb_resolves(self):
        css = """
        :root { --black: rgb(0% 0% 0%); }
        .x { color: var(--black); background: #ffffff; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        undefined = [f for f in findings if f.rule in ("undefined-var", "fallback-var")]
        self.assertEqual(undefined, [])
        # rgb(0% 0% 0%) is #000000 which has high contrast with white
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual(contrast, [])

    def test_percentage_rgb_comma_separated(self):
        css = """
        .x { color: rgb(100%, 0%, 0%); background: #ffffff; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        unresolved = [f for f in findings if f.rule == "unresolved-color"]
        self.assertEqual(unresolved, [])

    def test_out_of_range_rgb_is_unresolved(self):
        css = """
        .x { color: rgb(999, 0, 0); background: #000000; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        unresolved = [f for f in findings if f.rule == "unresolved-color"]
        self.assertEqual(len(unresolved), 1)

    def test_negative_rgb_is_unresolved(self):
        css = """
        .x { color: rgb(-1, 0, 0); background: #000000; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        unresolved = [f for f in findings if f.rule == "unresolved-color"]
        self.assertEqual(len(unresolved), 1)


class StringLiteralInRuleTest(unittest.TestCase):
    def test_content_with_braces_and_semicolons(self):
        css = """
        .x::before { content: "{;}"; color: #000000; background: #ffffff; }
        """
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        # Should parse correctly without errors
        self.assertGreater(len(findings), 0)
        errors = [f for f in findings if f.severity == "error" and "parse" in f.text.lower()]
        self.assertEqual(errors, [])


class HexParsingTest(unittest.TestCase):
    def test_six_digit_hex_ratio_matches_wcag(self):
        white = check.resolve_color("#ffffff", {})
        green = check.resolve_color("#1b6e5c", {})
        self.assertEqual(green, (27, 110, 92))
        self.assertAlmostEqual(check.contrast_ratio(white, green), 6.12, places=2)

    def test_three_digit_hex_expands(self):
        self.assertEqual(check.resolve_color("#fff", {}), (255, 255, 255))


class NestedRuleLineNumberTest(unittest.TestCase):
    def test_rule_inside_media_reports_its_own_line(self):
        css = "\n@media (x) {\n  :root { --p: #000; }\n  .low { color: #ffffff; background: #eeeeee }\n}\n"
        with tempfile.TemporaryDirectory() as d:
            path = write_file(Path(d), "design.css", css)
            findings = check.run_check(path, [path])
        contrast = [f for f in findings if f.rule == "contrast-ratio"]
        self.assertEqual([f.line for f in contrast], [4])
        self.assertTrue(contrast[0].text.startswith(".low {"))


if __name__ == "__main__":
    unittest.main()
