"""design-md tools 共通部品 — Finding / line_of / format_human / md→css 抽出。

design-md-check.py と page-check.py の両方から import される。
ファイル名にハイフンを含む script 同士は互いに import できないため、
共有ロジックはこのモジュールに置く（同じ dir が sys.path[0] に入る）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")  # CommonMark: fence は3スペースまでのインデント。4+ は code block


@dataclass
class Finding:
    rule: str
    severity: str
    file: str
    line: int
    text: str
    hint: str

    def as_dict(self) -> dict:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "text": self.text,
            "hint": self.hint,
        }


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def format_human(f: Finding) -> str:
    return f"{f.severity} {f.rule} {f.file}:{f.line} {f.text} — {f.hint}"


def md_to_css(text: str) -> str:
    """design.md を CSS 部分だけ残したテキストに変換する。

    ```css fenced block の中身だけを残し、それ以外の行（本文・見出し・fence 行）は
    空行にする。行数を保つので、以降の解析で出る行番号はそのまま .md の行番号になる。

    fence は CommonMark 規約で追跡する — opener の文字（` / ~）と長さを記憶し、
    同じ文字・長さが opener 以上・後続が空白のみの行だけが閉じる。
    ```python や ```css extra のような行は css block の内側では本文扱いになり、
    長い非 css fence（````text 等）の中の ```css は opener にならない。
    """
    out: list[str] = []
    in_css = False
    fence_char, fence_len = "", 0
    for line in text.split("\n"):
        m = FENCE_RE.match(line)
        if m:
            marker, info = m.group(1), line[m.end() :].strip()
            if fence_len == 0:
                fence_char, fence_len = marker[0], len(marker)
                in_css = marker[0] == "`" and info == "css"
                out.append("")
                continue
            if marker[0] == fence_char and len(marker) >= fence_len and not info:
                fence_char, fence_len, in_css = "", 0, False
                out.append("")
                continue
            # fence 内にあるが閉じ条件を満たさない marker 行は本文扱い
        out.append(line if in_css else "")
    return "\n".join(out)


def spec_text(path: Path) -> str:
    """spec ファイル（design.md / .css）を css-only テキストとして読む。"""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".md":
        return md_to_css(text)
    return text
