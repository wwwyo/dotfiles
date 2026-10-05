# Prototypes: pr-merge-lane orchestration shape

Brief: 10分間隔の軽い見回り（レビュー応答の routing・低リスク lane の merge・merge 済み worktree 削除）と日次の深いレビューを、既存 `pr-auto-merge` automation（流用・workspace_path 固定化）の中でどう構成するか。判定の所有権（script vs LLM）をどう分けるかが本質。

PRD: [../prd.md](../prd.md)

## Frozen rubric

### Gates（全 variant 必須）

- G1: 無変化の tick で LLM/session を起動しない経路が明示されている
- G2: 「絶対に merge しないもの」を lane が上書きしない構造になっている
- G3: state による冪等性（同じ指摘・同じ merge を二重処理しない）
- G4: reviewer agent は PR 上で何もしない（コメント投稿のみ、push/resolve/merge 権限なし）
- G5: worktree 削除が `liveTerminalCount==0` + clean + merged head 一致の条件を含む
- G6: 「作った agent が直す」原則（Pullfrog PR → Pullfrog、session PR → その session または専用 spawn、人間 PR → 報告のみ）

### Judgment criteria（1/3/5 anchors）

- J1 決定性: 同じ入力に同じ判定が返るか（1 = LLM の裁量に依存 / 3 = 一部機械化 / 5 = script が判定を独占）
- J2 監査性: 後から「なぜ merge/dispatch したか」を追えるか（1 = ログなし / 5 = 判定根拠が diffable な記録に残る）
- J3 失敗時の安全性: script 死亡・gh/orca 失敗・session 応答なしで破壊的副作用が出ないか
- J4 コスト: tick あたりの LLM 呼び出し量（1 = 毎 tick LLM / 5 = 無変化時ゼロ）
- J5 拡張性: deny path・lane 条件・新しいレビュアー bot の追加がどこに効くか

### Fixed（全 variant 共有の決定事項）

- Lane 対象は agent/人間の PR のみ（dependabot は従来ルール）
- `pullfrog-approval` が現在 head SHA に必須
- 低リスクは path deny + 変更種別で絞る（行数不問）
- 未対応 = 未解消 review thread または最終活動より新しい CHANGES_REQUESTED
- 無所属 PR は専用 worktree を立てて spawn
- worktree 削除は liveTerminalCount==0 のみ
- report `daily/<date>/pr-watch.md` + `pr-watch.jsonl`
- automation は既存 `pr-auto-merge` を流用（repo_path → workspace_path 変更・頻度化。評価時は10分間隔 → 採用決定で30分に変更）

### Free（variant が分岐する点）

- 判定ロジックを script / LLM / cadence のどこに置くか
- merge を 10分 tick に含めるか
- state の持ち主（script が書くか agent が書くか）

## Variants

| # | Variant | Axis | Design |
|---|---------|------|--------|
| 1 | Triage-first | script が全判定を独占 | [design.md](./triage-first/design.md) |
| 2 | LLM-conductor | script は facts 収集のみ、判断は LLM | [design.md](./llm-conductor/design.md) |
| 3 | Two-cadence | dispatch は10分、merge は日次 pass に集約 | [design.md](./two-cadence/design.md) |

## Check commands

- 各 design.md の mermaid 構文確認: 目視（自動チェック無し）
- Gate 充足: judge subagent のレビュー結果を下記に記録

## Judge observations

Judge: pi `opencode-go/space-bunny-free`（別家系モデル、v1/v2/v3 の中立ラベルで評価）。

### Gate 判定

| Gate | v1 triage-first | v2 llm-conductor | v3 two-cadence |
|---|---|---|---|
| G1 no-change path | PASS | PASS | PASS |
| G2 never-merge 非上書き | PARTIAL | **FAIL** | PARTIAL |
| G3 state 冪等 | PARTIAL | **FAIL** | PARTIAL |
| G4 reviewer は comment のみ | UNADDRESSED | UNADDRESSED | UNADDRESSED |
| G5 worktree 削除3条件 | PASS | **FAIL** | **FAIL** |
| G6 author-fixes | PARTIAL | UNADDRESSED | PARTIAL |

### Judge の主要指摘（勝者に graft すべき修正点）

1. **人間 authored PR の routing が全 variant で欠落** — unmatched → spawn だと人間の PR にも agent が spawn される。「人間 PR は報告のみ」の分岐が matcher に要る
2. **CI-less repo 表の扱いが v1 に無い** — 「CI green」が dotfiles/me 等の CI 無し repo で恒真 or 恒偽に化ける。既存の「CI 無しで merge してよい repo」表を lane でも使うか決める要
3. **dispatch 上限 3 回の starvation** — 打ち切り後は `⚠️` を報告に書くだけで、誰も読まなければ指摘が永久放置。上限到達時の escalation 先を明示する要
4. **merge と state 書き込みの順序が未定義** — merge 成功後に state 書き込みが死ぬと重複 merge attempt の恐れ
5. **v1/v2 は骨格が同一**（script → executor session → deep pass）。真に分岐するのは「merge を 10分 tick に含めるか」の一点だけ
6. **brief 自体の不備**: Fixed リストの削除条件が G5（3条件）より弱かった。次 round では Fixed を G5 に揃える


## 採用決定（2026-09-29）

採用: **triage-first**（script が判定を独占）。比較のまとめは [comparison.md](./comparison.md)。ただし次の変更・graft を適用して prd.md の Overview に反映済み。

gate 充足の最終確認（採用設計での状態）:

- G1 無変化 tick で LLM 非起動: script が snapshot 差分で判定するため PASS
- G2 never-merge 非上書き: deny path を二分化し「常に hold」は judge にも回さない → PASS
- G3 state 冪等: dispatch は (PR, head SHA) キーで記録、merge は intent 永続化 + reconcile → PASS
- G4 reviewer は comment のみ: Non-Goals に「reviewer agent に push・resolve・merge 権限を持たせない」として明記 → PASS
- G5 worktree 削除3条件: merged・liveTerminalCount==0・clean・head 一致・agent 非活動 + 削除直前の `ps` 再取得 → PASS
- G6 author-fixes: routing で author session / 専用 worktree に送る → PASS

- 周期は 10 分 → **30 分**に変更
- deny path は二分化: **常に hold（`.github/`・secrets・`AGENTS.md` 等）は judge にも回さず常に hold**、要判定 path（migration・infra・非 bot の依存 manifest 等）と whitelist 候補（nits/typo・codemod・bot 依存更新）だけが LLM judge に渡る。script の hard gate は merge 直前に再検証し、LLM の「可」判定だけでは merge を発行しない
- judge 指摘の graft（採用後のユーザー判断を含む最終形）: session 無しの PR は author が `wwwyo` または bot なら専用 worktree spawn（それ以外の author は触らない）/ CI の有無は lane の条件にしない（required check fail/pending のみ hold）/ dispatch 3 回打ち切り後は PR へ escalation コメント / merge は intent を state に永続化してから発行し record 欠落を reconcile
