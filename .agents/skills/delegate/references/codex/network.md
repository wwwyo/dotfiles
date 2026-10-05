Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## ネットワークアクセス

子 Codex は delegate の共通ルールに従い bypass mode で起動する。
URL の取得可否は、実行環境の network policy・接続状態・認証にも依存する。
[公式の権限説明](https://developers.openai.com/codex/agent-approvals-security)も参照する。

取得を頼むときは、実行結果を要求する:

```
ネットワークが許可されている場合は curl で実際に取得して。
失敗したら実行したコマンドとエラーをそのまま報告して。推測禁止。
```

まず policy とエラーを確認する。network が許可され、一時的な DNS 失敗だった場合だけ
1回再試行する。policy による拒否を同じ設定の再実行で回避しようとしない。
取得できない場合は親が許可済みの手段で取得し、必要な内容を prompt に渡す。
private repo など認証が必要な内容は、親の `gh pr diff` 等で取得して渡す。
