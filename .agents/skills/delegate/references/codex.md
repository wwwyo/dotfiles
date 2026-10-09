# Codex

Codex の通常の対話 session を Orca に開き、相談・調査・レビューを依頼する。

## モデル選択

[delegate](../SKILL.md) の「Agent・モデルの共通設定」に従う。設計・方針の相談は `Operator`、成果物の点検は `review`、具体的な調査・修正は `worker` とし、扱うデータの区分を選ぶ。以下の `MODEL`・`EFFORT` は、選ばれた Codex 候補の値を代入してから実行する。

## 対話 session の起動・再開

以下を対象 worktree の Orca `terminal create --command` に渡す。起動時には prompt を付けず、`terminal wait --for tui-idle` の `satisfied: true` を確認してから `terminal send --text ... --enter` で依頼を送る。具体的な terminal 操作は [delegate の Orca 手順](../SKILL.md#起動連携は-orca-経由) と `orca-cli` に従う。

```bash
# 新規の対話 session
codex --dangerously-bypass-approvals-and-sandbox --model "$MODEL" -c "model_reasoning_effort=$EFFORT" --cd <project_directory>

# process 終了後、対象 session を対話モードで再開
codex resume <session_id> --dangerously-bypass-approvals-and-sandbox --cd <project_directory>
```

追加指示は起動済みの同じ terminal / session に送り、回答後も session を残す。再開では保存された model・effort を引き継ぎ、変更するときだけ指定する。session ID は初回に控え、別の相談を拾い得る `--last` に頼らない。生きている session と並行して resume を立てない。

権限モードは [delegate](../SKILL.md) の「起動時の権限モード」に従う。bypass に `--sandbox read-only` を併記しても read-only にはならない。触ってよい範囲を依頼文に明記し、相談・調査でファイル変更が不要なら変更しないことを書く。

## 結果の確認

Orca の `terminal read` または監督下の報告経路で回答を確認する。送信受付と turn 開始を区別し、開始が未確認の prompt を重複送信しない。実行後は対象ディレクトリの `git status` / `git diff` で差分を確認し、依頼文で変更を許可した範囲外の変更がないことを確かめる。相談・調査ではあらゆる変更が範囲外になる。

## 未解決の反論を残さない

回答を主張ごとに分類する。最終結論・実装・リスク評価に影響する反論があれば、[反論への対応](codex/disagreement.md) を読んで同じ session に根拠を返し、その応答を受けてから終了を判断する。事実の対立は一次情報で検証し、LLM 同士の合意だけで解決しない。

## ネットワークアクセス

外部URLの取得・取得不可の調査には [ネットワークアクセスの診断](codex/network.md) を読む。認証が要る資料は親が取得して prompt に渡す。

## 明示された非対話実行の診断

ユーザーが one-shot / 非対話実行を明示した場合だけ `codex exec` を使う。通常の相談・短いレビュー・fallback には使わない。stdin 待ちで止まる場合は [stdin の手順](codex/stdin.md)、stdout / stderr の取得・background 監視は [非対話実行の出力と監視](codex/output-monitoring.md) を読む。これらの診断手順を対話 session の起動に適用しない。
