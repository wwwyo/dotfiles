# Comparison: pr-merge-lane orchestration

3 variant の横並び比較（judge 評価 + 著者所見）。詳細は各 design.md、judge 記録は README.md。

## 構造の違い

| # | Variant | 判定の所在 | tick ごとの LLM 起動 | merge のタイミング |
|---|---------|-----------|---------------------|-------------------|
| 1 | Triage-first | script が全判定を独占。LLM は実行のみ | action がある tick のみ | tick（30分）内 |
| 2 | LLM-conductor | script は facts 収集のみ。判断は全て agent | 毎 tick | tick 内 |
| 3 | Two-cadence | dispatch 判定は script、merge 判定は日次 pass | action がある tick + 日次 | 日次 pass のみ |

## Rubric 比較（judge: pi space-bunny-free、中立ラベル）

| 基準 | v1 | v2 | v3 |
|------|----|----|----|
| 決定性（同入力→同判定） | ◎ script 独占 | ✕ 毎回 LLM 解釈 | ◎ script 側 |
| 監査性 | ◎ 判定が diffable なコード | ✕ 判断根拠が transcript に散る | ◎ |
| 失敗時安全性 | ○ PARTIAL（graft で補強） | ✕ gate が prose | ○ PARTIAL |
| tick コスト | ◎ 無変化時ゼロ | ✕ 毎回 LLM | ◎ |
| merge 直前再 gate | ○ 要 graft | ○ | ◎ 設計に内蔵 |
| レビュー応答の即時性 | ◎ 30分以内 | ◎ | ◎（dispatch のみ） |
| merge の即時性 | ◎ | ◎ | ✕ 最大24h待ち |

## 決定的な分岐点

- v1 vs v3 の実質差は「merge を 30分 tick に含めるか」だけ（骨格は同一）。merge の blast radius を日次に揃える保守性を取るか、応答リズムを取るか
- v2 は「関門は prompt ではなくコードで」の原則と衝突（G2/G3/G5 が構造的 FAIL）。拡張性は最大だが、その拡張性と安全性は裏表
- 採用は **v1** — judge 指摘（人間/bot PR の routing・CI 扱い・starvation・merge/state 順序）は全て graft で吸収でき、PRD の狙い（30分でレビュー応答 + 低リスク merge）に最も忠実
