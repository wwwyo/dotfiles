# Codex

Codex CLI を使用して相談・調査を実行する手順。

## モデル選択

[delegate](../SKILL.md) の「Agent・モデルの共通設定」に従う。設計・方針の相談は `Operator`、成果物の点検は `review`、具体的な調査・修正は `worker` とし、扱うデータの区分を選ぶ。以下の `MODEL`・`EFFORT` は、選ばれた Codex 候補の値を代入してから実行する。

## 相談・調査（codex exec）

共通設定で Codex の候補を選んだ文言検討、設計相談、バグ調査には `codex exec` を使用する。

### コマンド形式

```
# 短い prompt (引数渡し) — 答えは stdout、トレースは err.log に退避
codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox -m "$MODEL" -c "model_reasoning_effort=$EFFORT" --cd <project_directory> "<request>" < /dev/null 2>"$TMPDIR/codex-err.log"

# 長い prompt / 特殊文字 (backtick, $ 等) を含む prompt → 一時ファイル + stdin pipe
cat <prompt_file> | codex exec --skip-git-repo-check --dangerously-bypass-approvals-and-sandbox -m "$MODEL" -c "model_reasoning_effort=$EFFORT" --cd <project_directory> - 2>"$TMPDIR/codex-err.log"
```

`2>&1` は使わない（理由は[出力と監視](codex/output-monitoring.md)）。

### stdin

引数で prompt を渡すときは `< /dev/null` を付ける。出力が空で固まる場合は [stdin の手順](codex/stdin.md) を読む。

### パラメータ

| パラメータ                   | 説明                                                         |
| ---------------------------- | ------------------------------------------------------------ |
| `-m "$MODEL"` | delegate で選んだ候補のモデルを明示する |
| `-c "model_reasoning_effort=$EFFORT"` | delegate で選んだ候補の effort を明示する |
| `--dangerously-bypass-approvals-and-sandbox` | delegate の共通ルールに従い、承認待ちなし・sandbox 解除で起動する |
| `--skip-git-repo-check`      | Git リポジトリの存在をチェックしない                         |
| `--cd <dir>`                 | 対象プロジェクトのディレクトリ                               |
| `"<request>"` または `-`     | prompt を引数で渡す / `-` で stdin から読む                  |
| `-o <file>`                  | `--output-last-message`。最終回答を file にも書き出す（stdout は抑制されない。background で確実に答えファイルを得たい時） |

権限モードは [delegate](../SKILL.md) の「起動時の権限モード」に従い、再開時にも指定する。`--sandbox read-only` の併記は意味を持たない — bypass 指定があると codex exec は sandbox 値を捨てて full access で起動し、併記しても read-only にはならない。権限は Orca の launcher 既定（bypass）と揃え、書き込みの制御は依頼文の範囲指定と実行後の差分確認で行う。相談・調査でファイル変更が不要なら、変更しないことを依頼文に明記する。

実行後は対象ディレクトリの `git status` / `git diff` で差分を確認し、依頼文で変更を許可した範囲外の変更がないことを確かめる。相談・調査ではあらゆる変更が範囲外になる。

### 長い prompt は stdin pipe を使う

heredoc を引数に埋める形 (`"$(cat <<'EOF'...EOF)"`) はバッククォートやドル記号を含む prompt で
shell 解釈が壊れたり、prompt が長いと argv 長制限にかかったりする。一時ファイルに書いて stdin で渡す:

```bash
cat > "$TMPDIR/codex-prompt.txt" <<'EOF'
ここに調査内容...
EOF

cat "$TMPDIR/codex-prompt.txt" | codex exec --dangerously-bypass-approvals-and-sandbox -m "$MODEL" -c "model_reasoning_effort=$EFFORT" --skip-git-repo-check --cd /path/to/project - 2>"$TMPDIR/codex-err.log"
```

prompt を作るコマンドと `codex exec` で sandbox の有効・無効を切り替える場合、`$TMPDIR` の値は
一致しないことがある。別の sandbox 境界から同じ一時ファイルを読むなら、workspace 配下または
`/private/tmp/<task-name>/` のような両方から見える絶対パスを使う。`$TMPDIR` に作ったファイルを
固定パスへ移さず sandbox 外から参照すると、ファイルが存在しないように見える。

### 出力と監視

stdout は答え、stderr はトレースとして分離する。stderr は呼び出しごとに固有の log へ保存し、初回の session id を控える。background 実行・出力異常・エラー時は [出力と監視](codex/output-monitoring.md) を読む。

## 未解決の反論を残さない

回答を主張ごとに分類する。最終結論・実装・リスク評価に影響する反論があれば、[反論への対応](codex/disagreement.md) を読んで同じ session に根拠を返し、その応答を受けてから終了を判断する。事実の対立は一次情報で検証し、LLM 同士の合意だけで解決しない。

## ネットワークアクセス

外部URLの取得・取得不可の調査には [ネットワークアクセスの診断](codex/network.md) を読む。認証が要る資料は親が取得して prompt に渡す。

## 実行手順

1. ユーザーから依頼内容を受け取る
2. prompt が長い or 特殊文字を含むなら一時ファイル + stdin pipe で渡す。短ければ引数渡しで OK
3. `-m "$MODEL" -c "model_reasoning_effort=$EFFORT"` を付ける（resume では元のセッションの値を引き継ぐ）。起動・再開とも `--dangerously-bypass-approvals-and-sandbox` を付け、触ってよい範囲を依頼文に明記する。
4. 外部 URL を渡すときは「curl で取得して。web search は使わないこと」を添える（`取得不可` の空振りを防ぐ）。
   認証が要るものは自分で取得して prompt に含める
5. stderr は `2>"$TMPDIR/codex-err.log"` に退避する（`2>&1` で統合しない / `2>/dev/null` で捨てない）。答えは stdout から取り、エラー時のみ err.log を Read する
6. 引数渡しなら `< /dev/null` を付ける（stdin 待ちでのブロック防止。「引数渡しのときは」節）。
   stdout を `| tail` 等にパイプしない（完了までバッファされ、timeout 時に何も残らない）
7. background 実行なら 60 秒経っても答えが出ない場合、まず err.log を Read する。
   `Reading additional input from stdin...` で止まっていれば `< /dev/null` 忘れ。
   err.log が 0 bytes なら `pgrep -fl codex` で死活確認し、居なければ kill して foreground で投げ直す
8. **err.log から session id を控える**（往復する可能性が常にあるため、初回時点で必ず）
9. 回答を**主張ごとに**分類する（[反論プロトコル](codex/disagreement.md)の表）。事実に疑義があるものは
   先に自分で検証する。**実質的な反論が残っているなら `resume` で返す**。自己判断で棄却して報告に進まない
10. 反論を提示しその応答を得た後で終了判定する。終了条件を満たしたらユーザーに報告する。
   打ち切った場合は争点・双方の根拠・ユーザーが決めるべき点を並べて出す
