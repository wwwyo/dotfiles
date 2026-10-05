# session 評価から学び還元を分離し、repo/wiki 単位の consolidation batch にする

Status: accepted

ADR 0001 では evaluator subagent が「判定 → score 書き戻し → signal あればそのまま session-retro（worktree → 追記 → draft PR）」を 1 run で行う設計だった。これを2つの batch に分ける:

- **session-eval**（この PR）: session 単位。transcript を読んで記録 comment（`## 事実` / `## 解釈（evaluator 所見）`、解釈側の末尾は `学習候補`）+ `evaluated_until` score を書き戻すだけ。repo への write・`git`・`gh` は持たない。（当初は `has_signal` + `session_summary` score だったが、track 分類は消費側不在の解釈を score に埋め込む形になるため 2026-09-26 に comment 記録へ変更）
- **session-consolidate**（後続）: repo + wiki 単位。未処理の評価済み session の記録 comment から `学習候補` を集めて（必要なら transcript まで drill down）skill/wiki/AGENTS をまとめて更新し、repo ごとに draft PR を出す。1日ではなくもう少し広い間隔で回す

分ける理由:

- **共存期の二重 retro**: rollout 第1段では SessionEnd hook がまだ signal session ごとに retro を回している。evaluator 側も retro すると同じ学びが hook/batch の両方から PR になる
- **session 単位 PR の衝突と文脈の断片化**: 同日の複数 signal session がそれぞれ別 worktree で同じ skill/AGENTS を触れば merge conflict する。学びは session をまたいだパターン（同じ摩擦の再発）の方が本質的で、session 粒度の還元は局所最適に落ちやすい
- **権限境界の縮小**: untrusted transcript を食べる evaluator が repo write を持たなくなる（ADR 0001 が引き継ぐと書いた prompt injection リスクのうち、最も危ない部分を evaluator 側から消せる）

## Considered Options

- **現行どおり evaluator が retro まで行う**: session 単位だと新鮮な context で学びを書ける利点はあるが、上記の衝突・断片化・権限の問題を引く。consolidate 側も `session_eval.py transcript` で生 trace に drill down できるため、context 損失は軽減可能と判断して不採用
- **evaluator の結果を溜めず、都度 consolidate に横流しする**: 事実上の現行設計と同じで、まとめて見る利点が消える

## Consequences

- evaluator は Langfuse への comment/score 書き込みだけを持つ read/record 専用の subagent になる。unattended 実行でも repo に副作用を持たない
- 記録の `## 解釈` 節が `学び PR` → `学習候補` を持つ。学び候補は「どこに何を書くと次が速くなるか」の箇条書きで、consolidate の入力 payload になる。採否は consolidate が記録を読んで判断する — evaluator は分類値を書かない
- consolidate の対象 predicate は「`evaluated_until` があり、記録 comment に `学習候補` の記述があり、`consolidated`（仮名）score が無い session」を repo で束ねる形を想定。実行間隔は自由 — 溜まった分を処理するだけ
- PRD の AC「評価済み session の `学習候補` に対して session-consolidate の還元フローが自動で走る」はこの batch ではなく session-consolidate の AC に移る
- 学び還元の即時性は失われる（session 直後 → 次回 consolidate run）。学びループは元来 daily-end 経由の非即時フィードバックなので許容する
