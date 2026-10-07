# Codex config.toml の非自明な key

upstream（codex の `config/src/types.rs` 等）を読まないと分からない設定セマンティクスだけを残す。
`~/.codex/config.toml` への載せ方（base と local の merge 方式・どの key を base に置くか）は
AGENTS.md「Codex の共通設定」が正本で、ここには書かない。

## memories

memory 機能は feature gate と `[memories]` sub-key の 2 層:

- `features.memories`（既定 off）は extension ごと切る gate — false なら `[memories]` の
  sub-key が local config に残っていても extension 自体が動かない。既存の `~/.codex/memories/`
  のファイルは消えず、読み書きが止まるだけ
- `[memories]` sub-key: `use_memories`（注入側）・`generate_memories`（生成側。false だと
  新規 thread が `memory_mode="disabled"` で state DB に記録される）・
  `disable_on_external_context`（MCP・web search が有効な thread を `memory_mode="polluted"`
  にする抑止）・`dedicated_tools`（memory tool の公開）

「memory を off にする」は粒度が 3 段階ある: `features.memories = false`（機能ごと停止）、
`generate_memories = false`（新規生成だけ止める）、`disable_on_external_context = true`
（外部 context がある thread だけ抑止）。現在 base は `features.memories = false`。
