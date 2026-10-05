---
name: prd
description: "機能の課題・目的・要件・ドメインモデルを PRD にまとめる。「PRDを作る」「要件をまとめて」「この機能を企画して」で使う。実装の設計書は document、repo の初期化は project-setup を使う。"
user-invocable: true
---

# PRD

PRD は、機能の why (なぜ作るのか) と what (何を作るのか) を関係者で合意するためのドキュメント。how (どう作るか) は扱わない。

PRD は課題側と解側の2段で書く。課題側 (Problem・導出・Glossary) は prototype の前に書き、解側 (Overview・Acceptance Criteria・必要な非機能要件・Success Metrics) は prototype で解の形を触って決めてから書く。触る前に解側を書くと、検証していない仮定を細かく書き込むことになる。ドメインモデルはヒアリングで整理した時点から Domain Model 節に書き、prototype で理解が変わったら更新する。節の中身は [references/prd-format.md](references/prd-format.md)、story の形式と判定は [references/story-format.md](references/story-format.md)。

## 置き場

| 成果物 | 置き場 |
|---|---|
| PRD | `<base>/prd/<prd name>/prd.md`。雛形は [templates/prd.md](templates/prd.md) |
| PRD の日本語版（英語 PJ） | `<base>/prd/<prd name>/prd.ja.md`。英語版と同じディレクトリに置く |
| DD（Design Doc、必要な場合） | `<base>/prd/<prd name>/dd.md`。対応する PRD と同じディレクトリに置く。作成時は `document` skill を参照 |
| story | repo root `AGENTS.md` の `## Story` 節。プロダクトに1つ。雛形は [templates/story.md](templates/story.md) |
| 用語集 | domain model 級の語だけ repo root `AGENTS.md` の `## Glossary` 節（形式は `domain-modeling` の `references/glossary-format.md`）。機能固有の語は `prd.md` の Glossary 節に閉じる |
| ADR | `<base>/adr/NNNN-slug.md`。形式・採番は `domain-modeling` の `references/adr-format.md` |
| prototype | 作業中は `prototype` skill の置き場。本番コードにしない。**解の形が決まった時点で成果物を `<base>/prd/<prd name>/prototype/` にコピーして残す**（さもないと「何を作って決めたか」が PRD から辿れない）。容量の大きい素材・再配布できない原典の写しは除外し、除外したものと再現方法をコピー側の README に書く |

`<prd name>` は機能を表す kebab-case の短い名前 (例: `task-status-filter`)。

AGENTS.md に描くディレクトリ構造も `{docs|.agent}/prd/<topic>/{prd|dd}.md` に揃える（`<topic>` は `<prd name>`）。DD を作る場合は同じ topic 配下に置き、別のディレクトリや `.agent/design-doc-<title>.md` へ分散させない。DD の作成は必須ではない。

`<base>` は `.agent` (gitignore された下書き。自分だけが読む) か `docs` (commit してチームで共有) のどちらかで、PRD と ADR で混ぜない。既存の codebase に `docs/prd/` か `docs/adr/` があれば `docs`、`.agent/prd/` か `.agent/adr/` があれば `.agent`。両方ある、またはどちらも無いときは2択と違いを示してユーザーに聞く。ヒアリング前に決める (`grill-with-docs` がヒアリング中に ADR を書くため)。

用語集は `<base>` が `.agent` のときも AGENTS.md に書く。ただし **AGENTS.md に入れてよいのは domain model 級の語だけ**——複数の機能・session を跨いで同じ意味で使われ、コードや他の設計が参照する実体の名詞。1つの機能の中だけで使う語（その機能を表す分類名・一時的な状態名・その機能内でしか出ない外部 system の名前）は AGENTS.md に書かず、prd.md の Glossary 節に閉じる。「別の機能でもこの語を使うか？」で切り分ける。使いそうなら昇格、今の機能だけなら prd.md に留める。

AGENTS.md に入れる語はさらに **model 定義と同等の語（モノ・実体の名詞）だけ**に絞る。処理・手順・検査の名前（例: 抽出・復元検査・検査）は入れない——入れると用語集が手順書と混ざり、実体の定義が埋もれる。処理の補足は関連する実体の定義の括弧内に畳み込む（例: PDF 抽出の性質は「取り込み」の注記）。各語にはコード側で使っている英語名を併記する（例: 原典（origin）、正規化（staging））。詳細は `domain-modeling` の `references/glossary-format.md`。

棄却した案は PRD 本文に残さず、行き先を3つに分ける。一方通行の決定 (戻すのに data migration・公開契約変更・全面書き直しが要るもの) に伴う棄却案は、その ADR の Considered Options に書く。スコープから外しただけの案は PRD の Non-Goals に書く。それ以外の戻せる案は記録せず、作って直す。

## やること

1. 機能の説明を受け取る
2. `<base>` を決める
3. story を確認する。`## Story` が story-format の構造を満たしていなければ、この PRD の前に `grill-with-docs` で「誰の生活で何をするか」「ユーザーが実際にやること」「その頻度」の3点だけをヒアリングして書き、判定2つを通す。書くのは初回だけ
4. `grill-with-docs` でヒアリングする。起動時に渡すのは ADR の書き先だけ (`domain-modeling` の既定は `docs/adr/` なので、`<base>` が `.agent` のときは `<base>/adr/` を指定する)。確認する観点は次の4つで、質問の出し方・打ち切りは `grill-with-docs` に委ねる
   - `<prd name>`
   - 解くべき課題や目的
   - スコープの境界
   - story からの導出 (この機能は `## Story` のどこから出るか、一文)。書けない機能は却下対象としてユーザーに伝えて止まる

   `grill-with-docs` が呼ぶ `domain-modeling` で整理した概念・概念同士の関係・境界・常に成り立つルールは、`prd.md` の `## Domain Model` に残す。概念と関係は Mermaid の `classDiagram`（クラス図）で表現し、関係名と、確定している多重度を示す。クラスはドメインの概念を表し、理解に必要な属性だけを含める。境界や図だけでは伝わらないルールは文章で補う。用語の定義を Glossary に書くだけで済ませず、この機能が扱うモデルを後から辿れる形にする。DB schema・実装クラスのメソッドや型などの実装方法は書かない。未確定の点は未確定と明記し、多重度も推測で埋めない。

   境界やルールを決める際に一方通行の判断があれば、その決定理由と比較した案は ADR に書く。Domain Model には決定後のモデルと ADR への link を残す。link は同節内に `[ADR-NNNN: <判断名>](../../adr/NNNN-slug.md)` の形式で置く。ADR を書いた場合も、モデルの内容は PRD から省かない。

5. 既存 PRD との関係を確認する。`docs/prd/` と `.agent/prd/` の既存 PRD を見て、同じ課題・スコープを扱うものがあれば新規作成ではなく既存 PRD への加筆を、連続したもの (前段の続き・同じ領域の派生機能) があれば `関連 PRD` の link をユーザーに提案し、合意を取ってから進む (link の形式は [references/prd-format.md](references/prd-format.md))
6. 課題側と、ヒアリングで整理した Domain Model を `prd.md` に保存する ([templates/prd.md](templates/prd.md) から作る)。モデルを整理していなければ Domain Model 節は省略してよい。英語を標準とする PJ では `prd.md` を英語で書き、日本語版 `prd.ja.md` も追加する。両版を相互リンクし、以降の追記・修正・状態更新でも構成・要件・`status` を揃える
7. `prototype` skill で解の候補を variant として作り、ユーザーに触ってもらう。解の形が決まるまで往復する。触っている間に一方通行の制約に当たったら、その時点で ADR を書く
8. 解側を同じ `prd.md` に追記し、prototype で整理・変更したドメインモデルも Domain Model 節に反映する。prototype の成果物を `<base>/prd/<prd name>/prototype/` にコピーする（置き場の表の除外ルールに従う）

   Acceptance Criteria はユーザーストーリー粒度だけで書く。1項目につき「誰が何をして、どんな結果を得られるか」を検証可能な一文にまとめ、操作手順・画面要素・例外ケースごとには分解しない。ここでの粒度は機能の利用目的から結果までで、プロダクト全体の `## Story` を再掲する意味ではない。重要な非機能要件（例: rate limit）がある場合だけ `## Non-Functional Requirements` を追加し、1要件1行で守る制約と判定に必要な条件・数値を簡潔に書く。実装方法や網羅的なチェックリストは書かない。

9. [delegate](../delegate/SKILL.md) の Codex reference を使い、2観点のレビューを受ける (下記)
10. 指摘を反映する。反映しない項目はユーザーに提示し、記録先は棄却案の3分類に従う。大規模な変更になったら再レビューに戻る。反映が終わったら `prd.md` の `status` を `ready` にする

実装は始めない。出力は `prd.md`・（英語 PJ では）`prd.ja.md`・`## Story`・（domain model 級の新語があるときのみ）`## Glossary`・ADR のみ。prototype の成果物を本番へ移す作業はこの skill の対象外。実装に進む際は [implement](../implement/SKILL.md) を使う。implementが着手時に `status` を `in-progress`、要件全体の実装・検証の完了時に `done` に更新する (定義は [references/prd-format.md](references/prd-format.md))。

## レビュー

解側を書き足した後、[delegate](../delegate/SKILL.md) の Codex reference を使い、次の2つを別々に依頼する。文章面と内容面を分けると、観点が混ざらず各々を深く見てもらえる。

1. 文章の正しさ。`japanese-tech-writing` の規範と、prd-format のセクション構成に沿っているか
2. 内容の red team。Problem と Overview の論理に飛躍がないか、Goals / Non-Goals の境界が曖昧でないか、Domain Model が Glossary・Overview・Acceptance Criteria と矛盾していないか、Acceptance Criteria が検証可能なユーザーストーリー粒度に収まっているか、重要な非機能要件があれば簡潔に記載されているか、how に踏み込んでいないか、抜けている前提・リスクがないか

## 完了チェック

手順を踏んでも漏れうるものだけを挙げる。

- `prd.md` が既に存在するとき、上書きの確認をユーザーに取った
- `<base>` が `.agent` のときに `docs/adr/` を作っていない
- domain model 級の新規用語があれば `AGENTS.md` の `## Glossary` に追記した（機能固有の語は prd.md の Glossary に閉じる。`grep -n '^## Glossary' AGENTS.md`）
- ヒアリングや prototype でモデルを整理した場合、`prd.md` の Domain Model 節に Mermaid の `classDiagram` があり、境界や図だけでは伝わらないルールも残っている（Glossary・ADR のみ、または会話のみで終わっていない）
- Success Metrics の4点が全部書けている。書けないものがあれば prototype に戻っている
- `prd.md` の `status` が `ready` になっている (作成時の `draft` のまま残っていない)
- 英語 PJ では `prd.ja.md` があり、英語版と構成・要件・`status` が一致し、相互リンクできる
- 既存 PRD との重複・連続を確認した (あれば加筆または `関連 PRD` link を提案済み)
