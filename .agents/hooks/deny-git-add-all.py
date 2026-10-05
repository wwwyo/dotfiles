#!/usr/bin/env python3
"""PreToolUse: ワークツリー全体を stage する `git add` を止める。

Claude Code と Devin CLI の両方から参照する共有 hook。シェル実行の tool 名は
Claude が `Bash`、Devin が `exec` で、それ以外の判定は完全に同じなので両方受ける。


止めるのは `-A` / `--all` / `.`（`-Au` のような連結短オプションも含む）。
パス指定の `git add ./foo.ts` や `git add path/` は通す。

Why not `-u` も止める: 追跡済みファイルに限るので、無関係な新規ファイルを
巻き込む事故は起きない。止める対象を広げるほど回避のための例外が要る。

Why not コマンド全体をそのまま検査する: commit message や PR 本文で禁止形を
引用しただけでブロックされる。規約を文書化する作業そのものが止まるので、
heredoc と引用文字列の中身を落としてから判定する。

Why not 厳密なシェルパーサを使う: 引用の除去で誤検知の主因は消える。残る
取りこぼしの代償は「明示パスで書き直す」だけで、それは元々やってほしい形。
"""

import json
import re
import sys

# heredoc 本体（<<EOF / <<-'EOF' / <<"EOF" いずれも）
HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)(\w+)\1.*?^\s*\2\s*$",
    re.DOTALL | re.MULTILINE,
)
SHELL_TOOLS = {"Bash", "exec"}

SINGLE_QUOTED = re.compile(r"'[^']*'")
DOUBLE_QUOTED = re.compile(r'"(?:\\.|[^"\\])*"')

# `git [-C dir ...] add [--verbose ...] [--] <全体を指す引数>`
# オプション部は長短どちらも、`--` セパレータも受ける。ここを短オプションだけに
# 絞ると `git add --verbose -A` や `git add -- .` が素通りする。
GIT_ADD_ALL = re.compile(
    r"(?:^|[;&|(]|&&|\|\|)\s*"
    r"git(?:\s+-\S+(?:\s+\S+)?)*"
    r"\s+add(?:\s+-\S+)*"
    r"\s+(?:-[A-Za-z]*A[A-Za-z]*|--all|\.)(?:\s|$)"
)

MESSAGE = """`git add -A` / `--all` / `.` は禁止。stage するファイルを明示的に列挙すること。

理由: 進行中の別作業・別 repo の設定変更・エージェントが生成した一時ファイルを
無関係な commit へ巻き込む事故が実際に起きている。

代わりに:
  git status --short          # 何が変わっているか先に見る
  git add path/to/file.ts     # 意図したものだけ
"""


def strip_literals(command: str) -> str:
    """引用の中身を落とす。位置がずれても判定に使うだけなので長さは保たない。"""
    for pattern in (HEREDOC, SINGLE_QUOTED, DOUBLE_QUOTED):
        command = pattern.sub(" ", command)
    return command


def main() -> int:
    # 判定できない入力は通す。hook の失敗で作業が止まる方が、
    # この事故を 1 回見逃すより高くつく。
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    if not isinstance(payload, dict) or payload.get("tool_name") not in SHELL_TOOLS:
        return 0

    tool_input = payload.get("tool_input")
    command = tool_input.get("command", "") if isinstance(tool_input, dict) else ""
    if not isinstance(command, str) or not command:
        return 0

    if GIT_ADD_ALL.search(strip_literals(command)):
        sys.stderr.write(MESSAGE)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
