# agent hooks

各 agent CLI（Claude Code / Codex / Devin / pi）の hook 機構に共通する知見。tool 個別の設定値は各 tool の reference を参照。

- **`matcher` は `tool_name` の regex で、tool 名は tool ごとに違う**。shell は Claude/Codex が
  `Bash`、Devin が `exec`。file 系は `read`/`write`/`edit`、MCP は `mcp__<server>__<tool>`。
  script が `tool_name` でゲートしていて名前を受理しないと payload は全件素通りして
  静かに死ぬ。新しい tool は共有 script の `SHELL_TOOLS`（現 `{"Bash","exec"}`）に足し、
  `echo '{"tool_name":"exec","tool_input":{"command":"git add -A"}}' | <script>` で
  exit 2 を確認する
- **置き場は「共有できるか」で決める**。tool 非依存なら `.agents/hooks/` に 1 本置き、
  各 tool の設定から `~/.agents/hooks/<name>` を指す。実装が違うなら各 tool の dir に別々に置く:

  | script | 置き場 | 理由 |
  | --- | --- | --- |
  | `deny-git-add-all.py` | `.agents/hooks/` | 判定は共通。Codex は `~/.codex/hooks/` 前提なので `.codex/hooks/` に repo 内相対 symlink を置く |
  | `status-line.js` | `home/dot_claude/hooks/` | Claude 専用 |

- **`nohup` で background 実行する hook は stderr を自分で拾う**。`>/dev/null 2>&1` を
  付けたまま子 shell の実行時エラーを捨てると、失敗の原因が一切残らない
