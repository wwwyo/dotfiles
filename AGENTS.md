# dotfiles

開発環境の設定ファイルを管理するリポジトリ。

各 tool の非自明な仕様・制約・設定値の理由（Orca・Claude Code・pi・agent hooks・Langfuse telemetry・macOS アプリの code 管理など）は wwwyo/skills の [dev-env skill](https://github.com/wwwyo/skills/blob/main/.agents/skills/dev-env/SKILL.md) を参照 — AGENTS.md には repo の機構と管理ファイルの記述を置き、agent tool 自体の仕様は skill 側へ持たせる。

## セットアップ

[chezmoi](https://www.chezmoi.io/) で管理する。macOS・Linux 両対応。

```bash
chezmoi init --source ~/src/github.com/wwwyo/dotfiles   # ~/.config/chezmoi/chezmoi.toml を生成
chezmoi apply -v                                       # deploy + run_once/run_after script 実行
chezmoi diff                                           # apply 前に差分確認
```

**apply は main checkout（canonical path）から実行する**。worktree から apply すると `run_after` が張る dir symlink が worktree 内を指し、worktree 削除で壊れる。

`~` 側に手元変更のある実ファイルがあると `apply` は確認で止まる — 差分を読んで意図どおりなら `--force` で進める。`run_after` の dir link script は毎回 `chezmoi diff` に残るので、「差分あり＝未適用」の判定に使わない。

## chezmoi layout

`.chezmoiroot` が `home` を指し、`home/` が source state root。repo root の `.agents/` `.claude/` `.codex/` `.pi/` 等は source state の外（chezmoi は見ない）。

- `home/dot_foo` → `~/.foo`。`mode = "symlink"` で普通のファイルは source への symlink になる（repo 編集が即反映＝旧 link.sh と同じ）
- **symlink 化できないもの**（template・executable・encrypted）は実ファイルとして置かれる
- **dir 単位リンク**: runtime が新規ファイルを書き込む・repo 内相対 symlink を含む・executable を含む dir は `home/run_after_20-link-repodirs.sh.tmpl` が repo dir へ symlink を張る。一覧は同 script、理由は `home/.chezmoiignore` 冒頭。dir link 対象の source は `.chezmoiignore` で chezmoi 管理から除外する
  - **dir link script は repo dir ↔ `~` の link だけを張る**（例外は Devin 用の `~/.config/devin/skills` → wwwyo/skills の `.agents/skills` だけ。理由は Skills 管理の節）。repo 内の共有は `.codex/hooks/…` →
  `../../.agents/hooks/…` のような相対 symlink を git に乗せる。link 対象の source が他 entry の
  target 配下を指しているのはこのパターン違反のサイン
  - **dir link で配る file の変更は merge/pull した時点で即座に本番へ届く**（`~` 側は repo dir を
  指す symlink なので apply を挟まず repo が正=本番）。file の削除・rename・移動を、その file を
  読む consumer（hook・skill・scheduled task）の切替と別の変更に分けると、存在しない・旧名の
  file を読みに行く window が空く — 両者は同じ merge に束ねる
- **OS 分岐**: shell script は `[[ "$OSTYPE" == darwin* ]]` or `[[ -x /opt/homebrew/bin/brew ]]` で分岐。JSON/TOML 等の data file は `.tmpl` 化して `{{ if eq .chezmoi.os "darwin" }}`。macOS 専用 entry は `.chezmoiignore` で linux 無効化
- `home/dot_gitignore.tmpl` は `{{ include "../.gitignore" }}` で repo root の `.gitignore` を読む（git 用と deploy 用の SSOT）。tool が cwd に生成する cache・state dir は各 repo の `.gitignore` ではなくこの `.gitignore` へ追加する — global gitignore として全 repo に効く（`**/.cloudflare/`・`**/.firecrawl/`・`**/.pi/npm/` が先例）

## 他 repo・他セッションから触るとき

wwwyo/me 等、別 repo で立ったセッションからこの repo に変更を加えるときは、main から worktree を切って作業する。checkout 中のブランチに直接 commit しない — dotfiles は他のセッション・作業からも常時触られており、任意のタイミングで何が checkout されているかを前提にできない。

dotfiles 自身の session から skill 本体・hook・`AGENTS.md` のような恒久資産を編集するときも worktree + PR を既定にする。他 repo・他 session と同じ file を同時に読み書きする共有物で、canonical main へ直 push すると後続の修正・rebase で履歴書き換え（force push）の手戻りになる。main 直 commit の可否が曖昧なときは worktree を選ぶ。

## 開発フロー

動画（demo・product launch・motion graphic）は `~/src/github.com/wwwyo/hyperframes`（HyperFrames の fork）を cwd にして `/hyperframes` skill から入る。

要件をまとめる [prd](https://github.com/wwwyo/skills/blob/main/.agents/skills/prd/SKILL.md) → 実装・self review・検証を行う [implement](https://github.com/wwwyo/skills/blob/main/.agents/skills/implement/SKILL.md) → 公開・レビュー・CIを扱う [pr](https://github.com/wwwyo/skills/blob/main/.agents/skills/pr/SKILL.md) → 定期merge laneの [pr-auto-merge](https://github.com/wwwyo/skills/blob/main/.agents/skills/pr-auto-merge/SKILL.md) の順で進める。期待動作が明確な実装タスクはimplementから始められる。テストの選択とunit testを最小限にする方針はimplementを参照する。

## Skills 管理

共有 skill の正本は [wwwyo/skills](https://github.com/wwwyo/skills)（canonical checkout は `~/src/github.com/wwwyo/skills`）。skill の追加・編集・skillctrl 運用・plugin の layout はその repo の `AGENTS.md` に従い、この repo には skill 本体を置かない。dotfiles が持つのは各 tool への登録だけ。

- Claude Code: core は claude.ai のアカウントに入れた core（`core@synced`）を使い、local は `extraKnownMarketplaces.wwwyo`（directory source）の `local@wwwyo` で入れる。`enabledPlugins` で `core@synced` を有効、directory 側の `core@wwwyo` を無効にして重複させない。local をアカウントに入れると cloud にも届くので、local だけは手元で入れる。core の編集は wwwyo/skills の main への merge と claude.ai の同期を経てから届く。merge 前の版を試すときは `claude --settings '{"enabledPlugins":{"core@wwwyo":true,"core@synced":false}}'` で起動し、その session だけ checkout の core に切り替える（`--plugin-dir` は marketplace の root を plugin として読まない）
- Codex: `home/.chezmoitemplates/codex-base.toml.tmpl` の `[marketplaces.wwwyo]` と `[plugins."core@wwwyo"]` 等。宣言だけでは cache に入らないため `home/run_after_30-codex-skill-plugins.sh` が apply 毎に `codex plugin add` する
- pi: `home/.chezmoitemplates/pi-settings-base.json` の `packages` にローカルパス
- Devin: plugin を読まないため、dir link script が `~/.config/devin/skills` を wwwyo/skills の `.agents/skills` へ link する（repo 外を指す唯一の dir link。`~/.agents/skills` に置くと Codex・pi の native discovery と plugin が重複する）
- Orca が配る skill（`orca-cli`・`orchestration`・`orca-computer-use`）だけは wwwyo/skills に置かず、この repo の `.agents/skills/` で git 追跡する。`~/.agents` はこの `.agents` への link なので、Orca 本体の更新で Orca が書き換えた内容は repo の差分として現れ、それを commit する。Claude 向けには `.claude/skills/<name>` → `../../.agents/skills/<name>` の相対 symlink を git に載せ、`~/.claude/skills` を dir link で配る（`tests/agents-skills-symlinks.test.sh` が対応を検査する）。Orca は手を入れていない copy だけを更新するので、中身は Orca 純正のまま保ち、手元の方針は global instructions か dev-env の reference に置く
- scheduled task・hook から skill の tools を呼ぶときは canonical checkout（`~/src/github.com/wwwyo/skills/.agents/skills/...`）を指す。`~/.agents/skills` には Orca の skill しか無い（Codex・pi はそこを直接読む）
- tool ごとの読み込み方・編集の反映は [dev-env の skill-plugins](https://github.com/wwwyo/skills/blob/main/.agents/skills/dev-env/references/skill-plugins.md) を参照する

## ユーザー名に依存しない

新しい Mac に別ユーザー名で移行しても dotfiles だけで復元できるよう、repo 内に `/Users/<name>` を書かない。

- **JSON/TOML の設定値は `$HOME` を展開しない**。Claude `settings.json` の `env`、Codex `config.toml` の `shell_environment_policy.set` に PATH を書くと literal の `$HOME` か旧ユーザー名が残るので、PATH はそこに書かない。Claude 側は `home/dot_claude/hooks/session-start.sh`（SessionStart hook）が `CLAUDE_ENV_FILE` に `export PATH=...` を書いて組む
- **home dir 参照が必要な .tmpl は `{{ .chezmoi.homeDir }}` を使う**（例: agent hook の配置先）。`{{ .chezmoi.username }}`・`{{ .chezmoi.hostname }}` も使える。hook command など shell snippet 内の path は `"$HOME"` で書けば展開されるので template 化不要
- **Codex の共通設定**は [`home/.chezmoitemplates/codex-base.toml.tmpl`](home/.chezmoitemplates/codex-base.toml.tmpl) が正本。[`home/dot_codex/private_config.toml.tmpl`](home/dot_codex/private_config.toml.tmpl) が既存の `~/.codex/config.toml` に共通設定だけを上書きし、実ファイルとして配置する。repo にない key は保持し、書き込み先の追加許可も消さない。base から key を削除しても既存の local 値は消えないため、不要になった local 値は `~` 側で削除する。`projects`（trust）・`hooks.state`・ローカル marketplace・モデル案内履歴・PC ごとの editor 設定・browser client の承認 hash は `~` 側だけで管理し、repo に snapshot を取り込まない。共通設定に含めた key を変える場合は base を編集する。逆に、base に載せた key は `mergeOverwrite` で apply 毎に local 値を base 値へ巻き戻すため、local で増殖・変化する値（dictation 辞書・`open-in-target-preferences.perPath` など）は base に入れない。
  - `projectlessWorkspaceRoot` はローカル設定。未設定時は Codex 標準の `~/Documents/Codex` を使う。
- **Pi sandbox は使っていない**。2026-10-27 に `pi-sandbox` package と chezmoi 側の template（`pi-sandbox-base.json`・`private_sandbox.json.tmpl`）・`~/.pi/agent/sandbox.json` を削除した。依存の `@carderne/sandbox-runtime` が Anthropic `srt` の個人フォークで zod advisory を抱え、恒久無効運用だったため。再導入の前提（config 無しだと `enabled: true`、`--no-sandbox` は extension 提供）は [dev-env](https://github.com/wwwyo/skills/blob/main/.agents/skills/dev-env/references/pi.md) を見る。知識としては残すが、明示指示がない限り復活させない。
- **Pi の settings.json** も同じ方式 — [`home/dot_pi/agent/private_settings.json.tmpl`](home/dot_pi/agent/private_settings.json.tmpl) が既存の `~/.pi/agent/settings.json` と [`home/.chezmoitemplates/pi-settings-base.json`](home/.chezmoitemplates/pi-settings-base.json) を合成する。pi が TUI から書き戻す key（既定 provider/model・theme・changelog 既読）は local を残し、symlink 配備だった頃の repo 汚染を防ぐ。

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

org 共通の defaults（model・effort、日本語出力・重要度ラベルの instructions 等）は [`.github/pullfrog.org.config.sh`](.github/pullfrog.org.config.sh)（script の `ORGS` に並べた owner ごとの `--org` scope。今は wwwyo・fudoki-hensansitu）が正本で、repo 側で unset した key は org の値を継承する。各 repo の script は model・effort を `pf_unset` して継承し、repo 個別に変えたいときだけ `pf_set` で上書きする。`pullfrog config list --repo` は継承値を見せないので、実効値の監査は `--repo` と、その repo の owner の `--org` の両方を引く。`review.approve=false` でも `review.approval-check=true` が `pullfrog-approval` status check を出す — merge lane はこちらを見る。

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
