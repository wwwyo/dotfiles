# sessions.md を廃止し、daily-end は Langfuse の score + comment を読む

Status: accepted

session 要約の吐き出し先を `wwwyo/me/daily/<date>/sessions.md`（hook による追記）から、Langfuse の score + comment に移す。同じ情報を2箇所に書くと片方だけ更新される不整合が起きるため、score が集約される Langfuse を SSOT にし、daily-end（wwwyo/me 側）は sessions.md の代わりに Langfuse API から当日分を引く形に改修する。

## Considered Options

- **sessions.md を sync job で生成し続ける**: 後方互換は保てるが「読みは Langfuse、書きは2重」で恒久的な移行コストを抱える。ファイルは一度生成されると stale な複製として残るため不採用
- **Langfuse を読まず daily-end が session transcript を自前で要約する**: 評価と振り返りの2重 LLM 呼び出しになり、score による「どの session を見るべきか」の絞り込みも失われるため不採用

## Consequences

- hook 廃止（dotfiles）と daily-end の入力切替（wwwyo/me）は別 repo で進むため順序を固定する: **eval batch の稼働開始 → daily-end を Langfuse 読みに切替 → 安定を確認して hook 廃止・sessions.md 停止**。逆順にすると daily-end の入力が空になる期間が生まれる
- sessions.md は新規生成されなくなる。過去分は git 履歴として残る
- daily-end の入力源が外部 SaaS 依存になる。Langfuse が落ちている日は振り返りの材料が減る（fail-open で当日分をスキップする扱い）
- `has_signal` で絞り込めるため、daily-end が読む量は旧形式より減る見込み
