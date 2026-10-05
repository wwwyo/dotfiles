Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

### 出力の扱い: stdout（答え）と stderr（トレース）を分離する

`codex exec` は通常実行で **stdout に最終回答のみ**（`--json` 指定時のみ stdout が JSONL events になる）、**stderr にトレース全部**（起動 banner・reasoning・実行コマンド・`tokens used`・model refresh / mcp 等の ERROR 行）を出す。

- `2>&1` で統合すると、成功時でも毎回トレース全文が context に流れ込む（= 大量 output の原因）
- 逆に `2>/dev/null` で捨てると startup 失敗・auth・deprecation の重要シグナルが消える
- → **統合も破棄もせず、stderr は別ファイル (`2>"$TMPDIR/codex-err.log"`) に退避する**

運用:

- 答えは **stdout** から取る（または `-o <file>` の last-message file）
- err.log は **初回だけ session id 行を確認**する（往復に備える。[未解決の反論を残さない](disagreement.md)）。
  それ以外は普段読まない。**exit≠0 / 出力が空・異常なときだけ** Read して ERROR を確認する
- トレース（reasoning・実行ログ）を見たいときだけ err.log を `tail` する

reasoning が重いタスクほど stderr 側だけが膨らむ（実測例では複雑な調査で stderr が **80KB / 1000行** 超になった一方、stdout は回答の長さにしか比例しない）。退避の効果はこの差ぶん。

**複数を並列・連続・background で走らせるときは err.log を invocation ごとにユニーク名にする**
（`mktemp` か `codex-err-<topic>.log` 等）。固定名だと上書きされ、どの回答に対応する trace か追えなくなる。

### Background 実行時の生存監視

background で投げる場合（自身の background 実行機構か shell の `&`）、**stderr を err.log にリダイレクトし、その err.log で死活確認する**
（banner も `tokens used` も stderr 側に出るため、stdout を見ても進行はわからない）:

| 観測                                      | 解釈                         | 対応                                                                       |
| ----------------------------------------- | ---------------------------- | -------------------------------------------------------------------------- |
| err.log が 0 bytes のまま **60 秒** 以上  | startup すらしてない疑い     | `pgrep -fl codex` で process 確認 → 居なければ kill して foreground で再実行 |
| err.log に banner / 進行ログあり & 生存   | 正常進行                     | そのまま待つ (大規模調査は 5-10 分かかることもある)                          |
| err.log に `tokens used` 行が出た         | 完了                         | stdout（or `-o` file）の答えを読む                                          |

codex は startup 時に banner (`OpenAI Codex v... / workdir: ... / model: ...`) を即 **stderr に** 書く。
zero-byte = "buffer 中" と決め込まず、まず `pgrep` で process を確認すること。

---
