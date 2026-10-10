---
name: dev-env
description: "dotfiles で管理する開発環境の tool 設定・hooks・telemetry・macOS アプリ管理の非自明な制約を調べる。Orca の keybindings・browser のフォーカス移動、Claude/Codex/pi の設定・認証・起動不調、hook の不調、Langfuse opt-in、Cloudflare AI Gateway の開発環境設定を触るときに参照する。"
---

# dev-env

この環境の tool 別の知見を `references/` に持つ。SKILL.md はルーター — 正本は各 reference。

サービスの公開・保護・課金設定と security/cost の共通概念は [solo-product](../solo-product/SKILL.md) に置く。ここでは手元の tool と AI Gateway の開発環境設定を扱う。

置いてよいのは「調べてわかるが、発見に失敗コスト（設定を壊す・存在しない機能を掘る）が伴う」事実。`--help` や doc を読めばその場で出る情報は置かない。

境界: dotfiles repo の機構（chezmoi layout・`skillctrl` 運用・dir link の挙動・管理するシステム設定ファイルの記述）は dotfiles の `AGENTS.md` が正本でここには書かない。各 tool の file がどう `~` に載るかは、その reference の前提として冒頭に書いてよい。ここにある知見を AGENTS.md へ戻さない。

## Routing

| やること | 読む reference |
| --- | --- |
| Orca の keybindings・ショートカット可否・browser のフォーカス移動・CLI 補足・issue 起票 | [references/orca.md](references/orca.md) |
| macOS アプリを brew/cask/run_once で code 管理する判断 | [references/macos-app-install.md](references/macos-app-install.md) |
| Claude Code の settings.json（env・sandbox）を触る | [references/claude-code.md](references/claude-code.md) |
| Codex CLI の stdin・出力・起動不調を調べる | [Codex の実行・診断手順](../delegate/references/codex.md) |
| Codex の config.toml の key 意味（features gate・memories 等）を調べる | [references/codex.md](references/codex.md) |
| pi の設定・認証・モデル・sandbox・起動不調を調べる | [references/pi.md](references/pi.md) |
| mise の pin・cooldown・trust・worktree での版ずれを調べる | [references/mise.md](references/mise.md) |
| agent hook を書く・共有する・tool_name でゲートする | [references/agent-hooks.md](references/agent-hooks.md) |
| Langfuse telemetry の opt-in・exporter・secrets を触る | [references/langfuse-telemetry.md](references/langfuse-telemetry.md) |
| CodeRabbit の central config・`.coderabbit.yaml` を触る | [references/coderabbit.md](references/coderabbit.md) |
| Cloudflare AI Gateway の tool・Access 認証・環境設定を触る | [Cloudflare AI Gateway の開発環境設定](references/cloudflare.md) |
| gh-aw の生成 workflow（`.github/workflows/*.md` + `*.lock.yml`）を触る | [references/gh-aw.md](references/gh-aw.md) |

## 関連 skill

- `delegate` — Codex・pi の選択・起動・非対話実行・session 再開
- `orca-cli` — Orca CLI 操作の version-matched guide（upstream lock 管理。local の知見は `references/orca.md` へ）
- `skill-structure` — 学び skill の構造規約
- `langfuse` — Langfuse の API・概念の upstream doc
