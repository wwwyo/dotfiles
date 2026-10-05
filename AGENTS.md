# dotfiles

開発環境の設定ファイルを管理するリポジトリ。

各 tool の非自明な仕様・制約・設定値の理由（Orca・Claude Code・Devin CLI・pi・agent hooks・Langfuse telemetry・macOS アプリの code 管理など）は `.agents/skills/dev-env/` を参照 — AGENTS.md には repo の機構と管理ファイルの記述を置き、agent tool 自体の仕様は skill 側へ持たせる。

## セットアップ

[chezmoi](https://www.chezmoi.io/) で管理する。macOS・Linux 両対応。

```bash
chezmoi init --source ~/src/github.com/wwwyo/dotfiles   # ~/.config/chezmoi/chezmoi.toml を生成
chezmoi apply -v                                       # deploy + run_once/run_after script 実行
chezmoi diff                                           # apply 前に差分確認
```

**apply は main checkout（canonical path）から実行する**。worktree から apply すると `run_after` が張る dir symlink が worktree 内を指し、worktree 削除で壊れる。

## chezmoi layout

`.chezmoiroot` が `home` を指し、`home/` が source state root。repo root の `.agents/` `.claude/` `.codex/` `.pi/` 等は source state の外（chezmoi は見ない）。

- `home/dot_foo` → `~/.foo`。`mode = "symlink"` で普通のファイルは source への symlink になる（repo 編集が即反映＝旧 link.sh と同じ）
- **symlink 化できないもの**（template・executable・encrypted）は実ファイルとして置かれる
- **dir 単位リンク**: runtime が新規ファイルを書き込む・repo 内相対 symlink を含む・executable を含む dir は `home/run_after_20-link-repodirs.sh.tmpl` が repo dir へ symlink を張る。一覧は同 script、理由は `home/.chezmoiignore` 冒頭。dir link 対象の source は `.chezmoiignore` で chezmoi 管理から除外する
  - **dir link script は repo dir ↔ `~` の link だけを張る**。repo 内の共有は `.codex/hooks/…` →
  `../../.agents/hooks/…` のような相対 symlink を git に乗せる。link 対象の source が他 entry の
  target 配下を指しているのはこのパターン違反のサイン
  - **dir link で配る file の変更は merge/pull した時点で即座に本番へ届く**（`~` 側は repo dir を
  指す symlink なので apply を挟まず repo が正=本番）。file の削除・rename・移動を、その file を
  読む consumer（hook・skill・scheduled task）の切替と別の変更に分けると、存在しない・旧名の
  file を読みに行く window が空く — 両者は同じ merge に束ねる
- **OS 分岐**: shell script は `[[ "$OSTYPE" == darwin* ]]` or `[[ -x /opt/homebrew/bin/brew ]]` で分岐。JSON/TOML 等の data file は `.tmpl` 化して `{{ if eq .chezmoi.os "darwin" }}`。macOS 専用 entry は `.chezmoiignore` で linux 無効化
- `home/dot_gitignore.tmpl` は `{{ include "../.gitignore" }}` で repo root の `.gitignore` を読む（git 用と deploy 用の SSOT）

## 他 repo・他セッションから触るとき

wwwyo/me 等、別 repo で立ったセッションからこの repo に変更を加えるときは、main から worktree を切って作業する。checkout 中のブランチに直接 commit しない — dotfiles は他のセッション・作業からも常時触られており、任意のタイミングで何が checkout されているかを前提にできない。

## 開発フロー

要件をまとめる [prd](.agents/skills/prd/SKILL.md) → 実装・self review・検証を行う [implement](.agents/skills/implement/SKILL.md) → 公開・レビュー・CIを扱う [pr](.agents/skills/pr/SKILL.md) → 定期merge laneの [pr-auto-merge](.agents/skills/pr-auto-merge/SKILL.md) の順で進める。期待動作が明確な実装タスクはimplementから始められる。テストの選択とunit testを最小限にする方針はimplementを参照する。

## Skills 管理

実装に固有のテストは実装の隣に置く（collocation を優先する）。skillctrl の処理は CLI・CI とも mise で管理する公開 Go 版を使い、この repo に重複実装を置かない。dotfiles 固有の workflow 接続テストは `tests/`、skill 品質評価は `.agents/skillctrl/evals/` に置く。

skill の検索・追加・作成・改善・更新・削除は `skillctrl` に統一し、手順は [skillctrl skill](.agents/skills/skillctrl/SKILL.md) に従う。CLI は常に cwd の Git repo を対象にし、`--repo` は無い — 共有 skill を操作するときは dotfiles の worktree に `cd` して実行する。worktree の新規作成は orca CLI 側の責務で、skillctrl は worktree を作らない。

skill の更新・独自適応は [skillctrl](.agents/skillctrl/README.md) に従う。`skillctrl update <name>` が原本をその場で取り込み、保存した `.agents/skillctrl/intents/<name>.md` の意図に沿うよう agent が直接編集・検証して `skillctrl record <name>` で受理 hash を記録する。upstream 管理 skill を意図的に変更するときは、環境・運用の文脈と保ちたい振る舞いの理由を `intents/<name>.md` に書く。意図ファイルは差分や patch の正本にせず、手順・チェックリストや共通設定の規約も重複して書かない。一般的な欠陥は upstream に修正を返す。意図がない skill は、原本が変わる update で適応が失われる。commit hook は設けず、lock 不一致を 2 つの gh-aw CI が offline の `skillctrl check` で検出する。通常 PR は [skillctrl](.github/workflows/skillctrl.md) が hash drift のときだけ AI に intent 適合を審査させ、検証済みの対象だけ `record` で受理する — PR の skill 本体は自動修正せず、intent 違反の疑い・判断不能はコメントして失敗する。lock 一致なら AI を呼ばず、意図ファイルの変更・削除自体は確認対象にしない。別 workflow の [skillctrl-update](.github/workflows/skillctrl-update.md) が土曜09:00 JST・手動 dispatch で `skillctrl update` の upstream 更新を取得し、現在の意図へ再適応・テストして draft PR を作る。各 workflow 最後の `Skill lock status` は、公開処理後も `.local.lock_changed` が残る場合に fail する。AI engine はユーザー指定の例外として pi / OpenCode Go を固定し、必要な認証がなければ確定しない。`~/.agents` 経由の本番を直接更新しない。

- **このリポジトリの skill は基本すべて global**。`~/.agents` → `.agents/` の symlink なので、取得先は worktree の `.agents/skills/` に固定する。upstream 登録は root の `skills-lock.json`（native `npx skills` 互換）、skillctrl 固有の provenance・受理 hash は `.agents/skillctrl/lock.json` で `skillctrl` が管理する
- source は GitHub の `owner/repo:skill`（例: `skillctrl add googleworkspace/cli:gws-calendar`）。取得 adapter は既定 `skills`（PATH 上の mise pin `skills` CLI を再利用し、無ければ npx で取得）、`--adapter gh|git` か `SKILLCTRL_ADAPTER` で明示できる。原本が変わっていない skill は取り込み直さず、独自適応を保持する
- 手書き skill（`memo` `wiki` `project-setup` 等）は `.agents/skills/` に直接置くため、upstream lock に載らない。accepted lock の記録・不一致検出・再適応も upstream lock の登録済み skill だけを対象にする。手書き skill は意図ファイルがあっても対象外。旧 accepted lock に残った未登録 skill の hash は次の `record` で削除し、skill 本文は変更しない
- 削除は `skillctrl remove <name>` を使い、worktree の実体・upstream 登録・保存済み intent を変更する。Claude symlink は CLI が管理しないため別途確認する。codex は `.agents/skills` を native discovery するため `.codex/skills` に symlink は置かない

- 独立 skill として残すかの判断基準は「その skill だけを目的に起動する場面（単独の入口）があるか」。無ければ既存 skill の reference か節として持つ
- 運用ルールの記載先は、情報の発生源（不具合の根拠・制約の由来）と適用時（操作を行う skill）で分ける。発生源にだけ書くと使う側が見ず、両方に全文書くと drift する
- skill・reference の rename・移動・削除では、path だけでなく link の表示名（label）・anchor も対象に repo 全体を grep して残存参照を消す。path だけ直して旧タイトルの label が残る事故が起きている

## ユーザー名に依存しない

新しい Mac に別ユーザー名で移行しても dotfiles だけで復元できるよう、repo 内に `/Users/<name>` を書かない。

- **JSON/TOML の設定値は `$HOME` を展開しない**。Claude `settings.json` の `env`、Codex `config.toml` の `shell_environment_policy.set` に PATH を書くと literal の `$HOME` か旧ユーザー名が残るので、PATH はそこに書かない。Claude 側は `home/dot_claude/hooks/session-start.sh`（SessionStart hook）が `CLAUDE_ENV_FILE` に `export PATH=...` を書いて組む
- **home dir 参照が必要な .tmpl は `{{ .chezmoi.homeDir }}` を使う**（例: Devin hook の配置先）。`{{ .chezmoi.username }}`・`{{ .chezmoi.hostname }}` も使える。hook command など shell snippet 内の path は `"$HOME"` で書けば展開されるので template 化不要
- **Devin Desktop の MCP**（`home/dot_config/devin/mcp_config.json.tmpl`）は GUI 起動で shims が PATH に無いため、mise のフルパスを command にして `mise x -- context7-mcp` で起動する。`mise x` は global config の env（age で復号した API key 等）も子に注入する。mise の path は OS で分岐（darwin: `/opt/homebrew/bin/mise`、linux: `~/.local/bin/mise`）
- **Codex の共通設定**は [`home/.chezmoitemplates/codex-base.toml.tmpl`](home/.chezmoitemplates/codex-base.toml.tmpl) が正本。[`home/dot_codex/private_config.toml.tmpl`](home/dot_codex/private_config.toml.tmpl) が既存の `~/.codex/config.toml` に共通設定だけを上書きし、実ファイルとして配置する。repo にない key は保持し、書き込み先の追加許可も消さない。base から key を削除しても既存の local 値は消えないため、不要になった local 値は `~` 側で削除する。`projects`（trust）・`hooks.state`・ローカル marketplace・モデル案内履歴・PC ごとの editor 設定・browser client の承認 hash は `~` 側だけで管理し、repo に snapshot を取り込まない。共通設定に含めた key を変える場合は base を編集する。
  - `projectlessWorkspaceRoot` はローカル設定。未設定時は Codex 標準の `~/Documents/Codex` を使い、`~/src/Codex` は `run_after_20-link-repodirs.sh.tmpl` が参照用 alias を張る。
- **Pi sandbox の共通設定**は [`home/.chezmoitemplates/pi-sandbox-base.json`](home/.chezmoitemplates/pi-sandbox-base.json) が正本。[`home/dot_pi/agent/private_sandbox.json.tmpl`](home/dot_pi/agent/private_sandbox.json.tmpl) が既存の `~/.pi/agent/sandbox.json` と合成して実ファイル化する。`filesystem.allowRead` の個別許可は `~` 側だけに保持し、通信先・Unix socket・書き込み先の追加許可も apply で消さない。sandbox の恒久無効設定は維持する。

## gitignore されたファイルを grep 対象に戻す（`home/dot_ignore` → `~/.ignore`）

`rg` は `.gitignore` を尊重するため、「git に載せたくないが grep では引きたい」ファイルが
検索結果から丸ごと落ちる。Claude Code の Grep tool も内部が rg なので、**agent が実在する
ファイルを「該当なし」と誤報告する**。

`home/dot_ignore` を `~/.ignore` へ symlink して対処している。rg は search path の
親ディレクトリを遡って `.ignore` を読み、かつ `.ignore` を `.gitignore` より優先するので、
**$HOME に置けば git repo の境界を越えて全 repo に効く**。対象は `*.local.*`、
`skills/_*`、`.agent/`。

- ディレクトリ除外を打ち消すには、**dir 自体を `!` で負にする**。配下のファイルだけ負にしても
rg はそのディレクトリへ降りない。`!**/skills/_*` が `.agent/skills/_*` に届かず実効ゼロだったのは
これが原因で、`!**/.agent/` を足して解決した
- `.ignore` の検索除外の打消しは Git には効かない。`*.local.*` は repo root の `.gitignore` で除外し、同じ内容を `~/.gitignore` へ配るため全 repo に効く（各 repo の明示的な打消しや追跡済みファイルを除く）。`<name>.local.<ext>` は machine 固有・非公開ファイルの命名規約として扱う

`RIPGREP_CONFIG_PATH` に `--no-ignore-vcs` を置く案は採らなかった。全 repo で gitignore が
無視されて `node_modules` 等がヒットしノイズが激増するうえ、Claude Code の Grep tool が
この環境変数を読む保証がなく、肝心の agent 側の問題が解決しない。`~/.ignore` は
ripgrep 本体の探索経路に乗るので、この懸念が両方とも無い。

## デフォルトアプリ（`home/dot_config/duti/defaults.duti`）

拡張子・URL スキーム → アプリの紐付けを duti で一元管理する。macOS では `run_once` script から
適用され、手動再適用は `duti-apply`（abbr）。放置すると Xcode が `.md`/`.json`、ChatGPT が `.csv`、
Edge が `.svg` を奪っていくので、宣言して奪い返す運用にしている。

**宣言しても効かない拡張子がある**（`.tf` `.html` `https` 等）。一覧と理由は defaults.duti 末尾の
「設定できないもの」節が SSOT。追加しても動かなかったときはそこを読むこと。

奪い返しは手動（`duti-apply`）で行い、LaunchAgent で定期的に強制していない。ユーザーが意図して
別アプリに変えた場合まで巻き戻してしまい、宣言的管理の利点が驚きに変わるため。

## macshot の設定

設定の正本は [scripts/macshot-settings.json](scripts/macshot-settings.json)。macshot 4.2.1 の UI から export した JSON で、ホットキーなど持ち運び可能な設定を収める。新しい Mac ではアプリの Settings → General → Settings Backup → Import Settings… から読み込み、再起動する。import は既存の持ち運び可能な設定を置き換える。保存先、認証情報、履歴は対象外。

初回セットアップ時、`defaults write` は成功したがアプリのホットキーは既定値のままだった。sandbox container 作成後は macOS のアクセス制限で書き込みも拒否された。コマンドの終了コードや `defaults read` だけではアプリ側の反映を保証できないため、`install.sh` から自動設定を削除した。plist の symlink も、`cfprefsd` の書き込み時に置き換わるため使わない。公式に確認できる import 経路は UI 操作なので、自動化したと扱わない。設定を変更したらアプリから再 export して JSON を更新する。

## Pullfrog の個別設定

この repo の Pullfrog 設定は [`.github/pullfrog.config.sh`](.github/pullfrog.config.sh) が正本。public repo では初回レビューと追加コミットの再レビューを自動で行い、手動でも `@pullfrog` で依頼できる。CLI のバージョンはグローバルの mise 設定（[`home/dot_config/mise/config.toml`](home/dot_config/mise/config.toml)）で管理し、設定変更は script を編集して実行する。

org 共通の defaults（日本語出力・重要度ラベルの instructions 等）は [`.github/pullfrog.org.config.sh`](.github/pullfrog.org.config.sh)（`--org wwwyo` scope）が正本で、repo 側で unset した key は org の値を継承する。`pullfrog config list --repo` は継承値を見せないので、実効値の監査は `--repo` と `--org` の両方を引く。`review.approve=false` でも `review.approval-check=true` が `pullfrog-approval` status check を出す — merge lane はこちらを見る。

## Story

wwwyo は複数の coding agent を日々の開発に回し、その日の振り返りと学びの還元で開発環境を育て続けている。

Core actions:

- agent session を起こして開発タスクを進める — 日次・複数回
- その日の session を振り返り、学びを skill へ還元する — 日次
- skill・hook・権限・telemetry の設定を手直しする — 週次

## Glossary

- **trace**: Langfuse における観測単位。この repo の agent telemetry では 1 turn = 1 trace として emit される
- **Session (Langfuse)**: `session_id` で束ねられた trace の論理グループ。agent の1 session に対応する
- **score**: trace/session に付ける評価値（数値・真偽・カテゴリ + comment）。機械可読の基準値の置き場 — 分類の解釈は score value に埋め込まず、記録は session comment に書く
- **evaluator**: trace/session を読んで記録・score を付ける判定器。judge LLM を使うかルールベースかは問わない
- **evaluated_until**: session-eval が Langfuse Session に付ける NUMERIC score。観測済み最新 obs の `endTime or startTime` の epoch 秒で「ここまでの観測を評価済み」の watermark と評価完了 marker を兼ねる（evaluator が最後に書く）。壁時計の取得時刻ではなく coverage で書く — fetch 後に ingest された turn も endTime が新しければ再評価対象になる
- **session-consolidate**: 評価済み session の comment 記録にある `学習候補` を repo/wiki 単位でまとめて還元し、repo ごとに draft PR を出す batch（ADR 0003、`.agents/scheduled-tasks/session-consolidate/`）。session-eval とは別 task — evaluator は repo を書かない。採否は consolidator が記録を読んで判断する
- **consolidated**: session-consolidate が Langfuse Session に付ける NUMERIC score（処理済み marker）。値は束ねた時点の `evaluated_until` — 再評価で `evaluated_until` が進んだ session は `consolidated < evaluated_until` で再対象になる