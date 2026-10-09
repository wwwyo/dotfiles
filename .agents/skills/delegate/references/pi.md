# pi にタスクを委譲する

pi は opencode Go サブスク（月 $10、5時間 $12 / 週 $30 / 月 $60 のドル建て枠）を叩く別プロセスの coding agent。codex とは別の quota なので、codex が rate limit に当たったときの逃がし先として使う。

## Routing

| やること | 読む reference |
| --- | --- |
| 設定を変える / 動かない / モデルや課金先を確認する | [pi の設定・認証](../../dev-env/references/pi.md) |

## モデル選択

[delegate](../SKILL.md) の「Agent・モデルの共通設定」で、役割とデータ区分から候補を選ぶ。モデル名・thinking・fallback の候補順はこの skill に持たせない。別 harness が先行して利用可能ならその harness を使う。以下は pi の候補を使う場合の手順で、`MODEL`・`EFFORT` にその候補の値を代入してから実行する。

## 対話 session の起動・継続

[delegate](../SKILL.md) の「起動時の権限モード」に従い、`--no-sandbox` を付けて実行する。`OPENCODE_API_KEY` の env 注入は不要 — `~/.pi/agent/auth.json` の `!` command credential が mise から都度解決する（[設定・認証](../../dev-env/references/pi.md)を参照）。

以下の実行例は、この環境で登録済みの `pi-sandbox` extension を読み込む前提。`pi --help` の Extension CLI Flags に `--no-sandbox` が出ることを確認する。出なければ [設定・認証](../../dev-env/references/pi.md)で extension の読み込みを確認し、未知の引数を付けたまま解除済みと判断しない。sandbox extension 自体を使用していない環境では、解除用の引数は不要。

以下を対象 worktree の Orca `terminal create --command` に渡す。起動時には prompt を付けず、[delegate の handoff 手順](../SKILL.md#devin--pi-への-handoff) で ready を確認してから送る。

```bash
# 新規の対話 session
pi --no-sandbox --model "$MODEL" --thinking "$EFFORT"

# process 終了後、対象 session を対話モードで再開
pi --no-sandbox --model "$MODEL" --thinking "$EFFORT" --session <session-path-or-id>
```

追加指示は同じ terminal に `terminal send --text ... --enter` で送り、回答後も session を残す。再開は session の path / ID を指定し、別タスクを拾い得る `-c` に頼らない。新規 session に名前が必要なら `--name <task-name>` を使う。`-p` / `--print` / `--mode json` / `--no-session` は通常の委譲では使わず、ユーザーが非対話実行を明示した場合だけ使う。

`--no-tools` を付けてはいけない。skill が読み込まれなくなる（理由は reference）。

resume・同じ session の継続では、初回の `MODEL`・`EFFORT` を引き継ぐ。

## 何を投げるか

向くもの。

- codex の quota 切れの肩代わり
- 安いモデルで足りる調査・要約・機械的な修正
- 独立していて並列に回せる作業

向かないもの。

- 方針決定や判断を委ねる設計相談。global 設定の `Operator` として選ぶ
- 人間による認証・署名などが必要なもの。通常の対話 session でも、これらの操作は人間に残す

## 委譲するときのプロンプト

pi は `~/.pi/agent/AGENTS.md`（`.codex/AGENTS.md` への symlink）と `.agents/skills/` を読む。依頼文は [delegate の4項目とテンプレート](../SKILL.md#必ず入れる4項目) に従い、作業ディレクトリ・範囲・タスク・完了条件を渡す。

結果は Orca の `terminal read` または監督下の報告経路で確認する。検証可能な形（ファイルを書かせる、判定語を返させる）で頼むと受け取りが楽になる。
