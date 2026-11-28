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

「memory を off にする」は粒度が 4 段階ある: `features.memories = false`（機能ごと停止）、
`use_memories = false`（developer prompt への memory 注入・使用指示だけ止める。生成は続く）、
`generate_memories = false`（新規生成だけ止める）、`disable_on_external_context = true`
（外部 context がある thread だけ抑止）。現在 base は `features.memories = false`。

## shell_environment_policy

`inherit = "core"` は codex が spawn する shell の env を core set（PATH・HOME・
SHELL・TERM・USER・TMPDIR 等）に絞る — 親 process の env のうち core に含まれない
key（`SSH_AUTH_SOCK`・token 類・mise 由来の var 等）が丸ごと落ち、
`[shell_environment_policy.set]` の key だけが追加される。PATH は core に含まれ
親の値がそのまま通るので、PATH entry が欠けるときはこの policy ではなく
spawn 経路（daemon 起動時の env 等）を疑う。session 内コマンドに env が要る
ときは呼び出し側で明示する（`env FOO=… cmd`）か base の
`[shell_environment_policy.set]` に載せる — 外側の shell で export 済みでも
codex 側には届かない。ただし PATH は `[set]` に書かない — literal の `$HOME`・
旧ユーザー名が残る（AGENTS.md「ユーザー名に依存しない」節の制約）。
