# ADR

戻すのが難しく、文脈なしでは意外に見える判断を記録する。

```
adr/
└── NNNN-<slug>.md     連番（既存の最大番号 + 1）。1 判断 1 ファイル
```

本文は「何を決めたか・なぜか」を数文で書き、`Status:`（proposed / accepted / deprecated / superseded by ADR-NNNN）を必要に応じて付ける。書き方は `document` skill の `references/adr-format.md` に従う。
