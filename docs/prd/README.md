# PRD

機能ごとの要件と、その判断材料を置く。

```
prd/
└── <topic>/           機能ごとの dir（短い kebab-case）
    ├── prd.md         要件（status: draft → ready → in-progress → done）
    ├── dd.md          必要な場合だけ置く設計書
    └── prototype/     判断に使った試作品（README に比較・再現方法）
```

書き方は `prd` skill、設計書は `document` skill に従う。戻すのが難しい判断は [ADR](../adr/README.md) に置く。
