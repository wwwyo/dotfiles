# Variant: Two-cadence

Axis: **可逆な操作（dispatch）だけを 10 分に載せ、不可逆な操作（merge・worktree 削除）は日次 pass に集約する。**

## Flow

```mermaid
flowchart TD
    A[pr-auto-merge automation<br/>10分間隔] --> B[tools/pr_triage.py<br/>dispatch 判定のみ]
    B -->|unaddressed 無し| Z[exit 0]
    B -->|unaddressed あり| C[devin session]
    C -->|terminal send / worktree create| D[対応 session]
    subgraph 日次 pass（同一 automation の 1日1回分）
        E[deep pass agent] --> F[従来全件レビュー + lane merge + worktree rm]
        F --> G[daily/<date>/pr-watch.md + jsonl]
    end
```

同一 automation を「10分 tick = dispatch のみ」「1日1回 = merge を含む deep pass」と state で分ける。lane merge の判定は「低リスク + pullfrog-approval」の新区分を加えた従来フローに統合される。

## 判定の所在

- **tick（script + 軽い実行）**: unaddressed review の検出と dispatch だけ。mergeable・deny path・approval の評価を一切しない。dispatch の dedup・上限 3 回は script が state で強制
- **deep pass（LLM、1日1回）**: 従来の全件レビューに lane 判定を追加。merge 判定は LLM が SKILL.md の規約（deny path・pullfrog-approval・「絶対に merge しないもの」の優先）を適用し、script は merge 直前の再確認（head SHA・approval・thread 数を最終 gate として機械チェック）だけ持つ

## State

- `dispatched` / `dispatchCount` / `lastDeepRun` は variant A と同じ
- merge record jsonl は deep pass 側が書く。tick は state を dispatch 情報以外書かない

## 強み・弱み

- 強み: merge の判定材料（pullfrog-approval・CI・thread）が「その時点の最新」に揃った1日1回のレビューで決まり、merge の blast radius と監査の cadence が揃う。tick が軽いので script 側の責務が最小（dispatch だけ）になり、誤 merge の機構上の経路が存在しない
- 弱み: 「レビュー対応が10分で回るのに merge は最大24h待ち」という非対称。深夜に全条件が揃っても翌朝まで待つ。merge も10分で流したいという本 PRD の狙い半分が後退する
