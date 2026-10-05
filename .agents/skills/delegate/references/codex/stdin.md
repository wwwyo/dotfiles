Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

### 引数渡しのときは `< /dev/null` を必ず付ける

prompt を引数で渡す形でも、**stdin が開いたままだと `codex exec` は追加入力を待ってブロックする**。
非対話・background 実行では stdin が EOF にならない pipe のままなので、モデルを呼ぶ前に
永久停止し、`Reading additional input from stdin...`（stderr）だけ出して出力が空になる。
`< /dev/null` で即 EOF を返せば処理に進む。

stdin pipe 形式（`cat ... | codex exec ... -`）は pipe が閉じて EOF が来るので不要。

この症状は `2>/dev/null` や `| tail` と組み合わせると完全に見えなくなる（待機メッセージは
stderr、stdout は pipe でバッファされ timeout 時に消える）。「出力が空で固まる」を見たら
まず stdin を疑う。
