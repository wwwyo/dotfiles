# skillctrl

skill の取得・更新・削除・lock の比較・意図への再適応は、CLI と CI とも mise で管理する公開 Go 版 `skillctrl`（v0.3 系）に統一する。この repo に管理処理の独自実装は置かない。コマンドの契約は upstream の [usage](https://github.com/wwwyo/skillctrl/blob/main/docs/usage.md) と bundled [references/ci.md](../skills/skillctrl/references/ci.md) を参照する。

## 日常の操作

発見・導入・統合・作成の手順は [skillctrl skill](../skills/skillctrl/SKILL.md) に従う。chezmoi が `~/.local/bin` に配る入口も mise の CLI を呼ぶ。対象は常に cwd の Git repo — `--repo` は存在しない。別 repo（dotfiles の共有 skill 等）を操作するときは対象の worktree に `cd` して実行する。skillctrl は worktree を作らないので、新しい worktree が要る場合は先に `orca worktree create` 等で用意する。

```bash
skillctrl find browser --owner vercel-labs
skillctrl add vercel-labs/agent-browser:agent-browser
skillctrl update agent-browser
skillctrl check
skillctrl record agent-browser
skillctrl remove agent-browser
```

取得 adapter は既定 `skills`（PATH 上の互換 `skills` CLI（mise pin）を再利用し、無ければ npx で起動する）。`--adapter gh` は GitHub CLI、`--adapter git` は直接 Git fetch を使う。tool が無いときはエラーで、別 adapter への黙った fallback はしない。

`update` は原本の取り込みだけを行い、AI も受理 hash も動かさない。原本が変わった skill は、その intent を読んで直接編集・検証し、`record <name>` で受理 hash を更新する。`record` は指定名だけを受理し、staging・commit は変更しない。引数なしの `record` は対象外 entry の pruning だけで何も受理しない。`check` は offline で受理 hash の drift を JSON に出し、drift 自体は exit 0、入力エラーだけが exit 1。

## repo に保持するデータ

- `.agents/skills/<name>/`: skill 本体と付属資源。
- `skills-lock.json`: upstream 登録。`npx skills` 互換の native lock で repo root に置く。独自 entry・field は追加しない。
- `.agents/skillctrl/lock.json`: upstream provenance（alias・merge の inputs・補足情報）と受理 hash の unified private state。native entry に紐付き、native 側の独立した変更が優先される。
- `.agents/skillctrl/intents/<name>.md`: 原本更新時に維持する文脈・意図。patch や実装手順の正本にしない。
- `.agents/skillctrl/evals/`: skill 品質評価の資源・結果。CLI 実装のテストとは別に保持する。

手書き skill は intent があっても accepted lock・不一致検出・再適応の対象外。`record` は未登録名を拒否する。旧 lock の未登録 hash は次の書き込みで除かれ、skill 本文は変わらない。

## Actions との接続

2 つの gh-aw workflow に分かれており、設計の根拠は bundled skill の [references/ci.md](../skills/skillctrl/references/ci.md) が正本。[skillctrl](../../.github/workflows/skillctrl.md) は PR の hash 審査、[skillctrl-update](../../.github/workflows/skillctrl-update.md) は土曜09:00 JST・手動 dispatch の定期更新を実行する。dotfiles が持つのは起動条件・job の権限・artifact の受け渡し・Pi/OpenCode Go engine の接続設定で、処理は基本コマンドと Git/gh だけに渡す。

| 処理 | 実装 |
| --- | --- |
| 対象の drift 検出（両 workflow 共通） | `skillctrl check`（offline、JSON、boolean を `jq -er` で厳密判定） |
| PR の intent 審査 | engine の agent が intent・diff・skill 全体を検証し、適合だけ `skillctrl record <name>` |
| PR への通知 | `add_comment` safe output（intent 違反の疑い・判断不能）。skill 本体は直さない |
| upstream 原本の取得（update のみ） | `skillctrl update --adapter git` |
| 意図に沿う再適応（update のみ） | engine の agent が直接編集・検証し `skillctrl record <name>` |
| 固定 scope の patch 検証 | workflow 内の固定 script（PR は受理 lock のみ、update は skill・登録・受理 lock） |
| 対象外 entry の整理 | `skillctrl record`（引数なし、prune のみ） |
| 公開 | Git/gh が push・draft PR を作成 |
| 最終ゲート | `skillctrl check` を `jq -e '.local.lock_changed == false'` で検査する `Skill lock status` |

CLI の pin は信頼済み base commit の `home/dot_config/mise/config.toml` から取得する。独立した mise 設定に CLI の pin・同じ base の `mise.lock` にある release checksum・release policy だけを取り出し、repo 側の設定や global の暗号化 env は読み込まない。agent の sandbox から使える場所に binary を配置し、各 job はその絶対パスを呼ぶ。reviewer の Node・Pi・model 定義も base 由来とする。

認証なしで対象を選択し、lock の整理と upstream 取得は推論なしで行う。intent のある対象には Actions secret `OPENCODE_API_KEY` が必要。この engine はユーザー指定の例外として pi / OpenCode Go を使う。書き込み token を持たない agent が patch・report を出し、別 job が scope と `check` を検証して公開する。未解決・認証不足・公開結果不明なら最後の **Skill lock status** は fail する。

レビュー報告と定期更新の draft PR 本文は英語で生成する。

定期更新は repo のテストを実行し、main の進行を確認して draft PR を作る。Actions の「Allow GitHub Actions to create and approve pull requests」が必要。自動 merge はしない。`GITHUB_TOKEN` による push は CI を再起動しないため、修正前の check を新しい commit の証明にしない。

## 接続の検証

公開 CLI 自体のテストは upstream が管理する。この repo の [workflow 接続テスト](../../tests/skillctrl-workflow.test.sh) は、信頼済み pin・公開 binary・選択結果・artifact・engine の接続を確認する。品質評価は `eval.test.sh` で検証する。

```bash
mise exec -- bash tests/skillctrl-workflow.test.sh
mise exec -- bash .agents/skillctrl/eval.test.sh
mise exec -- gh-aw compile --strict
```

workflow の正本は Markdown、`*.lock.yml` は compiler の生成物。編集後は再 compile し、両方を同じ変更に含める。
