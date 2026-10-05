# PRD Format

`prd.md` のセクション構成。Problem・導出・Glossary は課題側で prototype の前に、Overview・Acceptance Criteria・必要な非機能要件・Success Metrics は解側で prototype の後に書く。Domain Model は整理した時点から書き、prototype で理解が変わったら更新する。雛形は [templates/prd.md](../templates/prd.md)。

置き場は `{docs|.agent}/prd/<topic>/prd.md`。DD（Design Doc）が必要な場合は同じ topic 配下の `dd.md` に置く。AGENTS.md のディレクトリ構造も `{docs|.agent}/prd/<topic>/{prd|dd}.md` に揃える。`docs` と `.agent` の選択は `prd` skill の「置き場」に従う。

## セクション

1. Problem — 何が問題か、なぜ今解決する必要があるか
2. 導出 — この機能が repo root `AGENTS.md` の `## Story` のどこから出るかを一文で書く
3. Overview — 機能の概要。次の2つを subsection として含める
   - Goals — この機能で達成したいこと (why)
   - Non-Goals — スコープ外を明示する。スコープから外した案の置き場
4. Glossary (必要な場合) — 本文の理解に要る語だけ。この機能内に閉じる語はここが正本。domain model 級の語（複数機能・session を跨ぐ実体の名詞）だけ `AGENTS.md` の `## Glossary` にも置く
5. Domain Model (モデルを整理した場合) — この機能が扱う概念・概念同士の関係・境界・常に成り立つルールを残す。用語の定義は、機能固有ならこの PRD の Glossary、domain model 級なら repo root `AGENTS.md` の `## Glossary` を参照し、ここでは関係や制約を書く。概念と関係は Mermaid の `classDiagram`（クラス図）で表現し、関係名と、確定している多重度を示す。クラスはドメインの概念を表し、理解に必要な属性だけを含める。境界や図だけでは伝わらないルールは文章で補う。DB schema・実装クラスのメソッドや型などの実装方法は含めない。未確定の点は未確定と明記し、多重度も推測で埋めない。一方通行の判断の理由と比較した案は ADR に書き、この節には決定後のモデルと ADR への link を残す。link はこの節内に `[ADR-NNNN: <判断名>](../../adr/NNNN-slug.md)` の形式で置く
6. Acceptance Criteria — この PRD が完了と言える検証可能な条件を、ユーザーストーリー粒度だけでチェックボックスにする。1項目につき「誰が何をして、どんな結果を得られるか」を一文にまとめ、操作手順・画面要素・例外ケースごとには分解しない。機能の利用目的から結果までを扱い、プロダクト全体の `## Story` は再掲しない。技術的なことは省く
7. Non-Functional Requirements (重要な非機能要件がある場合のみ) — rate limit など、プロダクトの成立に重要な制約を1要件1行で簡潔に書く。判定に必要な条件・数値は含め、実装方法や網羅的なチェックリストは書かない。例えば rate limit なら対象・回数上限・時間窓・超過時の振る舞いを短く示す。重要な要件がなければ節ごと省略する
8. Success Metrics (必須) — 次の4点を必ず書く。どれかが書けないなら prototype に戻る
   - コアアクション: ユーザーが実際にやること。「開いた」「ログインした」は不可
   - 期待頻度 (cycle): 日次 / 週次 / 月次 / 年数回 など
   - 数える対象: 自分から開いた人 (アイコン・ブックマーク・URL の直打ち) のうちコアアクションを取った数。通知・メール・リマインド経由の来訪は除く
   - 主指標: onboarding 後の翌日・翌週にコアアクションを取って戻ってきた割合。onboarding の完了率は使わない (通過しただけの人を含む)

連続した既存 PRD (前段の続き・同じ領域の派生機能) があるときは、タイトル直下に `関連 PRD: [<prd name>](../<prd name>/prd.md)` の行を置く。既存 PRD 側からも後続が辿れるとよい場合は、既存側にも同じ形式の逆参照を足す。

`## Migration` や `## Breaking Changes` など、変更内容に応じたセクションを足してよい。

## status

`prd.md` の先頭に YAML frontmatter で `status` を持つ。どの PRD が書きかけ・実装可能・対応中・完了かを `rg '^status: '` で repo 横断に一覧するための機械可読な欄。本文のセクションではなく frontmatter に置くのは、状態の更新で本文に diff が出ないようにするため。

- `draft` — 書きかけ。課題側のみ・prototype 往復中・レビュー中を含む
- `ready` — 実装 ready。レビュー反映まで済んだ完成形
- `in-progress` — 実装対応中
- `done` — 実装完了

`draft` → `ready` は PRD を書いた側が完成時に更新する。`in-progress` と `done` は [implement](../../implement/SKILL.md) が更新する (着手時に `in-progress`、PRD全体の実装・検証が完了した時点で `done`。部分実装や未検証があれば `in-progress` のまま)。statusだけの更新はfrontmatterの1行変更でよく、本文の変更・レビューを伴わない。

status を持たない既存の PRD は `draft` 相当として扱う。

## 書き方

日本語本文は `japanese-tech-writing` の規範に従う。読み手はジュニア開発者や AI agent かもしれない前提で、説明なしの専門用語を避け、必要なら具体例を入れる。

- 複雑なフローや構造 (機能のフロー、スコープ境界など) は、本文の前に mermaid 図で全体像を示す
- table はセル内に長文を入れず、比較 (観点 × 案などの属性比較) のときだけ使う。Goals / Non-Goals のような構造の列挙は箇条書きにする

## 検証・Go/Kill 判断を扱う PRD

検証フェーズや撤退判断を扱う PRD では、「検証する」だけでは完了条件にしない。判断を先送りしないため、実行前に以下の検証条件を固定する。検証後の結果と Go/Kill 判断は `result.md` などに残す。

`## 検証条件` を追加して以下の詳細をまとめ、Acceptance Criteria は検証結果から Go/Kill を判断できるという成果単位に留める。

- 検証対象の分母 (例: 業種・brief・シナリオ) と後から追加した場合の記録方法
- Go/Kill 閾値と、閾値を動かす場合に理由を残す欄
- 期限または試行上限。期限切れや材料不足を「判断不能」ではなく判断材料として扱うルール
- 品質改善・チューニングの上限と、判定フェーズに入った後は基準やプロンプトを変えないルール
- 主観評価を使う場合の最低条件。可能なら blind 判定や客観テストを Yes の必要条件にする

Go は本番化の許可ではなく、次の検証へ進む許可として書く。品質検証なら、品質が良くても需要や流通の検証は別問題だと明示する。
