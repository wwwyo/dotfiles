"""page-check.py の unittest。"""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "page_check", Path(__file__).parent / "page-check.py"
)
check = importlib.util.module_from_spec(_spec)
sys.modules["page_check"] = check
_spec.loader.exec_module(check)

SPEC_MD = """# Design — test

## Tokens

```css
:root { --primary: #1B6E5C; }
```

## Components

```css
.card { padding: 16px; }
.stat-strip { display: flex; }
```
"""


def write_file(tmpdir: Path, name: str, content: str) -> Path:
    p = tmpdir / name
    p.write_text(content, encoding="utf-8")
    return p


class InventedColorTest(unittest.TestCase):
    def test_hex_literal_in_style_block_is_warning(self):
        html = "<html><head><style>.x { color: #ff0000; }</style></head><body></body></html>"
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        invented = [f for f in findings if f.rule == "invented-color"]
        self.assertEqual(len(invented), 1)
        self.assertEqual(invented[0].severity, "warning")

    def test_var_reference_is_not_flagged(self):
        html = "<html><head><style>.x { color: var(--primary); }</style></head><body></body></html>"
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        invented = [f for f in findings if f.rule == "invented-color"]
        self.assertEqual(invented, [])


class InventedFontTest(unittest.TestCase):
    def test_font_family_literal_is_warning(self):
        html = '<html><body><div style="font-family: Helvetica, sans-serif;">x</div></body></html>'
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        invented = [f for f in findings if f.rule == "invented-font"]
        self.assertEqual(len(invented), 1)
        self.assertEqual(invented[0].severity, "warning")

    def test_no_font_declaration_is_not_flagged(self):
        html = '<html><body><div style="padding: 4px;">x</div></body></html>'
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        invented = [f for f in findings if f.rule == "invented-font"]
        self.assertEqual(invented, [])


class UnknownClassTest(unittest.TestCase):
    def test_class_not_in_design_md_is_info(self):
        html = '<html><body><div class="mystery-box">x</div></body></html>'
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        unknown = [f for f in findings if f.rule == "unknown-class" and f.text == "mystery-box"]
        self.assertEqual(len(unknown), 1)
        self.assertEqual(unknown[0].severity, "info")

    def test_class_defined_in_design_md_is_not_flagged(self):
        html = '<html><body><div class="card">x</div></body></html>'
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        unknown = [f for f in findings if f.rule == "unknown-class"]
        self.assertEqual(unknown, [])

    def test_class_in_allowlist_is_not_flagged(self):
        html = '<html><body><div class="mystery-box">x</div></body></html>'
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, {"mystery-box"})
        unknown = [f for f in findings if f.rule == "unknown-class"]
        self.assertEqual(unknown, [])


class NegativeWithoutMinusTest(unittest.TestCase):
    def test_negative_class_without_minus_mark_is_warning(self):
        html = '<html><body><span class="negative">1200</span></body></html>'
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        negs = [f for f in findings if f.rule == "negative-without-minus"]
        self.assertEqual(len(negs), 1)
        self.assertEqual(negs[0].severity, "warning")

    def test_negative_class_with_minus_mark_is_not_flagged(self):
        html = '<html><body><span class="negative">-1200</span></body></html>'
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        negs = [f for f in findings if f.rule == "negative-without-minus"]
        self.assertEqual(negs, [])


class ExternalResourceTest(unittest.TestCase):
    def test_google_fonts_link_is_error(self):
        html = (
            '<html><head><link href="https://fonts.googleapis.com/css2?family=Inter" '
            'rel="stylesheet"></head><body></body></html>'
        )
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        ext = [f for f in findings if f.rule == "external-resource"]
        self.assertEqual(len(ext), 1)
        self.assertEqual(ext[0].severity, "error")

    def test_no_external_reference_is_not_flagged(self):
        html = "<html><head><style>.x{color:red}</style></head><body></body></html>"
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        ext = [f for f in findings if f.rule == "external-resource"]
        self.assertEqual(ext, [])

    def test_external_resource_causes_exit_code_1(self):
        html = (
            '<html><head><script src="https://example.com/lib.js"></script></head>'
            "<body></body></html>"
        )
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            code = check.main([str(spec), str(page)])
        self.assertEqual(code, 1)


class WidthUsageTest(unittest.TestCase):
    def test_table_ratio_below_threshold_is_warning(self):
        layout = {"blocks": [{"selector": "table", "width": 300, "containerWidth": 800, "ratio": 0.375}], "stripItems": []}
        html = "<html><body><table></table></body></html>"
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, layout, set())
        width_findings = [f for f in findings if f.rule == "width-usage"]
        self.assertEqual(len(width_findings), 1)
        self.assertEqual(width_findings[0].severity, "warning")

    def test_table_ratio_above_threshold_is_not_flagged(self):
        layout = {"blocks": [{"selector": "table", "width": 780, "containerWidth": 800, "ratio": 0.975}], "stripItems": []}
        html = "<html><body><table></table></body></html>"
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, layout, set())
        width_findings = [f for f in findings if f.rule == "width-usage"]
        self.assertEqual(width_findings, [])


class StripItemsCrampedTest(unittest.TestCase):
    def test_low_ratio_is_warning(self):
        layout = {
            "blocks": [],
            "stripItems": [
                {"selector": "div.stat-strip", "stripWidth": 800, "childrenWidthSum": 300, "ratio": 0.375}
            ],
        }
        html = "<html><body><div class='stat-strip'></div></body></html>"
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, layout, set())
        cramped = [f for f in findings if f.rule == "strip-items-cramped"]
        self.assertEqual(len(cramped), 1)
        self.assertEqual(cramped[0].severity, "warning")

    def test_high_ratio_is_not_flagged(self):
        layout = {
            "blocks": [],
            "stripItems": [
                {"selector": "div.stat-strip", "stripWidth": 800, "childrenWidthSum": 780, "ratio": 0.975}
            ],
        }
        html = "<html><body><div class='stat-strip'></div></body></html>"
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, layout, set())
        cramped = [f for f in findings if f.rule == "strip-items-cramped"]
        self.assertEqual(cramped, [])


class LayoutSkippedTest(unittest.TestCase):
    def test_no_layout_flag_emits_info_finding(self):
        html = "<html><body></body></html>"
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, None, set())
        skipped = [f for f in findings if f.rule == "layout-skipped"]
        self.assertEqual(len(skipped), 1)
        self.assertEqual(skipped[0].severity, "info")

    def test_layout_given_suppresses_layout_skipped(self):
        html = "<html><body></body></html>"
        layout = {"blocks": [], "stripItems": []}
        with tempfile.TemporaryDirectory() as d:
            spec = write_file(Path(d), "design.md", SPEC_MD)
            page = write_file(Path(d), "page.html", html)
            findings = check.run_check(spec, page, layout, set())
        skipped = [f for f in findings if f.rule == "layout-skipped"]
        self.assertEqual(skipped, [])


if __name__ == "__main__":
    unittest.main()
