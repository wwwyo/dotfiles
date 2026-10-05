# pi にタスクを委譲する

pi は opencode Go サブスク（月 $10、5時間 $12 / 週 $30 / 月 $60 のドル建て枠）を叩く別プロセスの coding agent。codex とは別の quota なので、codex が rate limit に当たったときの逃がし先として使う。

## Routing

| やること | 読む reference |
| --- | --- |
| 設定を変える / 動かない / モデルや課金先を確認する | [pi の設定・認証](../../dev-env/references/pi.md) |

## モデル選択

[delegate](../SKILL.md) の「Agent・モデルの共通設定」で、役割とデータ区分から候補を選ぶ。モデル名・thinking・fallback の候補順はこの skill に持たせない。別 harness が先行して利用可能ならその harness を使う。以下は pi の候補を使う場合の手順で、`MODEL`・`EFFORT` にその候補の値を代入してから実行する。

## 実行

[delegate](../SKILL.md) の「起動時の権限モード」に従い、`--no-sandbox` を付けて実行する。`OPENCODE_API_KEY` の env 注入は不要 — `~/.pi/agent/auth.json` の `!` command credential が mise から都度解決する（[設定・認証](../../dev-env/references/pi.md)を参照）。

以下の実行例は、この環境で登録済みの `pi-sandbox` extension を読み込む前提。`pi --help` の Extension CLI Flags に `--no-sandbox` が出ることを確認する。出なければ [設定・認証](../../dev-env/references/pi.md)で extension の読み込みを確認し、未知の引数を付けたまま解除済みと判断しない。sandbox extension 自体を使用していない環境では、解除用の引数は不要。

```bash
cd <作業ディレクトリ>
pi --no-sandbox --model "$MODEL" --thinking "$EFFORT" -p "<task>" --no-session
```

出力は stdout にそのまま返るので、パイプで受けてよい。構造化したいときは `--mode json`。

一発で終わらない task は session を張れば往復できる。`--session-id <name>` は同名のセッションが無ければ作り、あれば継続する。名前を分ければ複数の task を並行して進められる。

```bash
pi --no-sandbox --model "$MODEL" --thinking "$EFFORT" -p "<task の前半>" --session-id refactor-auth
pi --no-sandbox --model "$MODEL" --thinking "$EFFORT" -p "<前の結果を踏まえた指示>" --session-id refactor-auth   # 文脈が残っている
```

直前のセッションを継続するだけなら `-c`、途中から枝分かれさせるなら `--fork`。使い捨てで文脈を残したくないときだけ `--no-session` を付ける。

`--no-tools` を付けてはいけない。skill が読み込まれなくなる（理由は reference）。

resume・同じ session の継続では、初回の `MODEL`・`EFFORT` を引き継ぐ。

## 何を投げるか

向くもの。

- codex の quota 切れの肩代わり
- 安いモデルで足りる調査・要約・機械的な修正
- 独立していて並列に回せる作業

向かないもの。

- 方針決定や判断を委ねる設計相談。global 設定の `Operator` として選ぶ
- 人間の確認を挟みながら進めたいもの。往復自体は session で可能だが、間に立つのはこちらになる

## 委譲するときのプロンプト

pi は `~/.pi/agent/AGENTS.md`（`.codex/AGENTS.md` への symlink）と `.agents/skills/` を読む。こちらの規約は既に効いているので、プロンプトで作法を繰り返す必要はない。task と完了条件だけ渡す。

結果は pi の最終出力がそのまま返る。検証可能な形（ファイルを書かせる、判定語を返させる）で頼むと受け取りが楽になる。
