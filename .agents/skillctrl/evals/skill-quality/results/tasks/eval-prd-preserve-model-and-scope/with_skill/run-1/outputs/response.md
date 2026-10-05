PRD を作成しました。

**変更したファイル（fixture 内のみ）**

- `docs/prd/collection-share/prd.md` — 完成 PRD（`status: ready`）
  - Problem / 導出 / Overview（Goals・Non-Goals）/ Glossary / Domain Model / Acceptance Criteria / Success Metrics
  - Non-Goals に除外4件（共同編集・閲覧者本人確認・通知・共有履歴の分析）をそのまま記載
  - Domain Model は classDiagram + ルール（メモ0件以上・メモの単一所属・リンクは1コレクション対象・所有者だけが発行/失効）で、**同時に有効にできるリンク数は「未確定」と明記し多重度を省略**（推測で埋めていません）
  - 既存決定は ADR-0001 への linkとして `[ADR-0001: メモの所属を1つにする](../../adr/0001-single-collection.md)` を配置（ADR は既存のものを参照のみ、新規作成なし）
  - Non-Functional Requirements は「重要な追加 NFR なし」なので節を削除
  - Success Metrics は4点すべて記載、主指標の目標値は未確定と明記
- `docs/prd/collection-share/prototype/index.html` — 合意済み prototype の成果物を設置（再配布不能素材なしのため README は不要）
- `AGENTS.md` — `## Glossary` に **共有リンク（ShareLink）** を追加（domain model 級・複数共有機能をまたぐ実体）。**『匿名閲覧』は機能固有の語なので prd.md の Glossary にのみ**記載。コレクションには所有者を持つ旨を追記

**行わなかったこと（指示どおり）**: 再ヒアリング、prototype の再作成、`codex` による外部レビュー、実装、commit/push。`prd.md` の上書き確認は fixture 内に `docs/prd/` が無いため新規作成で問題なし（既存 PRD なし＝重複なし）。また、ブラウザ/シェル等のツールはこの環境に無いため、mermaid の描画確認や lint は実行していません。