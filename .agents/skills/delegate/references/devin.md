# Devin CLI

対象の作業ディレクトリで実行する。Orca の terminal 操作は `orca-cli`、別 repo・独立したセッションへの委譲は `delegate` を使う。

委譲起動では `DEVIN_PERMISSION_MODE` の既定値（mise は smart）に依存せず、delegate の共通ルールに合わせて `--permission-mode dangerous` を毎回指定する。委譲先は確認プロンプトに応答できず、smart が必ず確認させる操作で止まるため。deny / ask ルールは mode を問わず効く。この環境では `Exec(terraform)` が ask にあり、委譲先はその確認で止まる。terraform の実行が要件に含まれる依頼は委譲せず、確認が要る旨を報告する。

## モデル選択

[delegate](../SKILL.md) の「Agent・モデルの共通設定」に従う。`devin models list --format json` で使用可能な model UID を確認し、以下の `DEVIN_MODEL_ID` に代入する。Devin は effort を含む UID で指定する（例: `swe-2:medium` → `swe-2-medium`）。

## 基本コマンド

```bash
# 対話セッション
mise x -- env -u ACP_BACKEND devin --permission-mode dangerous --respect-workspace-trust false --model "$DEVIN_MODEL_ID"

# 非対話で実行して終了
mise x -- env -u ACP_BACKEND devin --permission-mode dangerous --respect-workspace-trust false --model "$DEVIN_MODEL_ID" -p "<タスクと完了条件>"

# 長い依頼はファイルから渡す
mise x -- env -u ACP_BACKEND devin --permission-mode dangerous --respect-workspace-trust false --model "$DEVIN_MODEL_ID" --prompt-file <prompt-file> -p

# セッションを探して再開
mise x -- env -u ACP_BACKEND devin list
mise x -- env -u ACP_BACKEND devin --permission-mode dangerous --respect-workspace-trust false -r <session-id> -p "<追加の指示>"
```

再開時は保存されたモデルを引き継ぐ。変更するときだけ `--model` を付ける。

## Orca で起動・継続を確認する

ready 後に送信する順序は [delegate の handoff 手順](../SKILL.md#devin--pi-への-handoff) に従う。Orca が `provider: "unsupported"` を返す場合、`accepted: true` は入力受付の証拠だけで、ターン開始や実 model の証明にはならない。`terminal read` の描画と以下の native evidence を併用する。送信前の step / 生成時刻を控え、送信後に新しい user input とその後の agent generation があることを確認する。古い最後の agent step を今回の送信成功に使わない。

読み込んだ delegate skill directory の絶対パスを `DELEGATE_SKILL_DIR` に設定して、[読み取り専用 helper](../scripts/devin-evidence.py) を使う。Python 標準ライブラリだけで動き、session を再開せず、会話本文・reasoning・tool 引数・config・生ログを出さない。

```bash
: "${DELEGATE_SKILL_DIR:?Set the absolute path of the loaded delegate skill directory}"

# 保存済み native ATIF。--after-step は送信前の last_step_id
python3 "$DELEGATE_SKILL_DIR/scripts/devin-evidence.py" --session <session-id>
python3 "$DELEGATE_SKILL_DIR/scripts/devin-evidence.py" --session <session-id> --after-step <last-step-id>

# transcript がまだ無い / 更新されていない稼働中 session の native DB
python3 "$DELEGATE_SKILL_DIR/scripts/devin-evidence.py" --session <session-id> --database "$HOME/.local/share/devin/cli/sessions.db"
python3 "$DELEGATE_SKILL_DIR/scripts/devin-evidence.py" --session <session-id> --database "$HOME/.local/share/devin/cli/sessions.db" --after-time <前回の生成時刻>

# 対象 session のものと確認した CLI log の既知 transport event だけ追加
python3 "$DELEGATE_SKILL_DIR/scripts/devin-evidence.py" --session <session-id> --log <対象logの絶対パス>

# transcript がまだ無い場合も、明示した log だけを読む
python3 "$DELEGATE_SKILL_DIR/scripts/devin-evidence.py" --log <対象logの絶対パス>
```

`--transcript <path>` で native ATIF を明示指定してもよい。helper の `ok: false` / exit 1 は読取失敗であり、空の成功と区別する。指定した transcript/DB が読めない場合は自動で log-only 成功へ切り替えない。ATIF/DB schema が変わった場合は生 dump に切り替えず、必要 field だけを再確認する。ATIF の省略可能な時刻は null のまま返し、step ID で増分を確認する。log の時刻不正行は件数を示して除外し、DB の model 不明件数は既知 model の集計と分ける。既知 event 0件は接続正常の証明ではなく、明示した log の session 帰属は別に確認する。書出し条件・DB の重複・model 欄の意味は [native evidence の制約](../../dev-env/references/devin-cli.md#native-evidence-で実-modelturn停止を区別する) を参照。

## Connection error で turn が止まったとき

1. coordinator は `terminal read/show` と対象 log を確認する。`Exhausted inference retries; stopping turn` や `Connection error, send a message to continue retrying` は turn 停止の根拠になる。PTY が live なだけ、無反応、`unsupported`、transcript 不在だけでは停止と判断しない。
2. 停止が確認でき、同じ agent が入力を受けられる場合に、同 session へ継続 prompt を1回送る。Task/Dispatch、現在の cwd/変更保持、mailbox と最新 brief の読み直し、現在の到達点の status 報告を含める。元タスク全体の二重送信や自動再送はしない。曖昧な送信失敗は [orca-cli が読み込む version-matched guide](../../orca-cli/SKILL.md#load-the-version-matched-guide-before-running-orca-commands) の receipt / retry 手順に従う。
3. native evidence の新 user input と agent generation で継続を確認し、再び止まったら別の接続失敗として時刻・attempts を記録する。CLI process が終了した場合の再開は [orchestration が読み込む version-matched guide](../../orchestration/SKILL.md#load-the-version-matched-guide-before-running-orca-commands) の supervised Dispatch recovery 手順を coordinator が判断する。生きている process と並行して `devin -r` を立てない。

接続停止と候補の品質不一致は別の記録にする。候補提出・独立検査待ち・候補固定は対象 repo の既存手順に従う。監督下の follow-up は durable enqueue や nudge だけでは読まれたと扱わず、worker の `check` と受領報告を確認する（[Orca の mailbox 補足](../../dev-env/references/orca.md#orchestration-worker-が自分の-mailbox-を読むとき)）。

監督タスクの開始仕様には、最初の作業を「live preamble の自 inbox を読み、現在 Task/Dispatch と所有範囲の受領 status を coordinator へ返す」と具体化する。受領確認までの無反応だけで停止・重複起動はしない。起動後の新しい native user input / generation と worker の受領 status は別々に確認する。skill の discovery 成功や初回の受領は、その後の checkpoint で follow-up が読まれる保証にはならないため、後続の受領も追跡する。

## 詰まったとき

- `ACP_BACKEND` があるとローカル認証を無視するため、上のコマンドでは外している。
- 認証は `devin auth status`、診断は `devin doctor`。これらも `mise x -- env -u ACP_BACKEND` 経由で実行する。
- 認証/doctor 成功は、その後の推論 stream の健全性を保証しない。EOF・HTTP status・CLI retries の根拠を [native evidence の制約](../../dev-env/references/devin-cli.md#native-evidence-で実-modelturn停止を区別する) で切り分け、model・認証・context の問題へ根拠なく置き換えない。
- `--respect-workspace-trust false` は非対話で必須。trust の確認画面を出せず、trust 未確認の worktree では起動に失敗する。対話にも揃えて付ける（Orca の launcher 既定と同じ組み合わせのため）。
- 権限モードは [delegate](../SKILL.md) の「起動時の権限モード」に従う。再開時にも指定する。

設定・rules・hooks の説明は [dev-env の Devin reference](../../dev-env/references/devin-cli.md) を読む。
