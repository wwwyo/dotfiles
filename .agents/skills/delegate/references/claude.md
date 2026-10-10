# Claude Code

Claude Code の通常の対話 session を Orca に開き、レビュー・点検を依頼する。

## モデル選択

[delegate](../SKILL.md) の「Agent・モデルの共通設定」で、役割とデータ区分から候補を選ぶ。モデル名・effort・fallback の候補順はこの skill に持たせない。`--model` には alias（`opus` = Opus 5.5、full name は `claude-opus-5-5`）または full name を渡す。以下の `MODEL`・`EFFORT` は、選ばれた候補の値を代入してから実行する。

## 対話 session の起動・再開

以下を対象 worktree の Orca `terminal create --command` に渡す。起動時には prompt を付けず、`terminal wait --for tui-idle` の `satisfied: true` を確認してから `terminal send --text ... --enter` で依頼を送る。具体的な terminal 操作は [delegate の Orca 手順](../SKILL.md#起動連携は-orca-経由) と `orca-cli` に従う。

```bash
# 新規の対話 session
claude --dangerously-skip-permissions --model "$MODEL" --effort "$EFFORT"

# process 終了後、対象 session を対話モードで再開
claude --dangerously-skip-permissions --resume <session_id>
```

追加指示は起動済みの同じ terminal / session に送り、回答後も session は残す。session ID は初回に控え、別 project の session を拾い得る `-c` / `--continue` に頼らない。model・effort を変えるときは再開時にも指定する。生きている session と並行して resume を立てない。

権限モードは [delegate](../SKILL.md) の「起動時の権限モード」に従う。bypass は権限確認を止める指定であって、触ってよい範囲の宣言ではない。点検・調査でファイル変更が不要なら、変更しないことを依頼文に明記する。

## 結果の確認

Orca の `terminal read` または監督下の報告経路で回答を確認する。送信受付と turn 開始を区別し、開始が未確認の prompt を重複送信しない。実行後は対象ディレクトリの `git status` / `git diff` で差分を確認し、依頼文で変更を許可した範囲外の変更がないことを確かめる。点検ではあらゆる変更が範囲外になる。
