# Devin CLI

対象の作業ディレクトリで実行する。Orca の terminal 操作は `orca-cli`、別 repo・独立したセッションへの委譲は `delegate` を使う。

委譲起動では `DEVIN_PERMISSION_MODE` の既定値（mise は smart）に依存せず、delegate の共通ルールに合わせて `--permission-mode dangerous` を毎回指定する。委譲先は確認プロンプトに応答できず、smart が必ず確認させる操作で止まるため。deny / ask ルールは mode を問わず効く。この環境では `Exec(terraform)` が ask にあり、委譲先はその確認で止まる。terraform の実行が要件に含まれる依頼は委譲せず、確認が要る旨を報告する。

## モデル選択

[delegate](../SKILL.md) の「Agent・モデルの共通設定」に従う。`devin models list --format json` で使用可能な model UID を確認し、以下の `DEVIN_MODEL_ID` に代入する。Devin は effort を含む UID で指定する（例: `swe-2:medium` → `swe-2-medium`）。

## 対話 session の起動・再開

以下を Orca の `terminal create --command` に渡す。新しい worktree で保存済みランチャーを使う場合は [delegate の handoff 手順](../SKILL.md#devin--pi-への-handoff) に従う。起動時には prompt を付けず、ready 後に送る。

```bash
# 対話セッション
mise x -- env -u ACP_BACKEND devin --permission-mode dangerous --respect-workspace-trust false --model "$DEVIN_MODEL_ID"

# セッションを探して再開
mise x -- env -u ACP_BACKEND devin list
mise x -- env -u ACP_BACKEND devin --permission-mode dangerous --respect-workspace-trust false -r <session-id>
```

再開時は保存されたモデルを引き継ぐ。変更するときだけ `--model` を付ける。

追加指示・長い依頼も、起動済み terminal に `terminal send --text ... --enter` で送る。回答後も session を残す。`-p` / `--print` は処理後に終了する非対話モードなので、ユーザーが one-shot を明示した場合だけ使う。

## 詰まったとき

- `ACP_BACKEND` があるとローカル認証を無視するため、上のコマンドでは外している。
- 認証は `devin auth status`、診断は `devin doctor`。これらも `mise x -- env -u ACP_BACKEND` 経由で実行する。
- `--respect-workspace-trust false` は非対話で必須。trust の確認画面を出せず、trust 未確認の worktree では起動に失敗する。対話にも揃えて付ける（Orca の launcher 既定と同じ組み合わせのため）。
- 権限モードは [delegate](../SKILL.md) の「起動時の権限モード」に従う。再開時にも指定する。

設定・rules・hooks の説明は [dev-env の Devin reference](../../dev-env/references/devin-cli.md) を読む。
