# Design Doc ガイドライン

Google の公開書籍 [Software Engineering at Google — Design Docs](https://abseil.io/resources/swe-book/html/ch10.html#design_docs) の指針を基に、設計をレビューするための文書を作る。付属の [テンプレート](../assets/design-doc.md) は、この repo 向けに構成したもので、Google の公式テンプレートの転載ではない。

## 公開資料に基づく指針

設計の目標、実装方針、主要な判断とそのトレードオフを書く。代替案の長所と短所も示し、採用案を選んだ理由をレビューできるようにする。セキュリティ、プライバシー、保存容量、国際化など、設計に関係する懸念を検討する。承認後も意思決定の記録として保管し、リリース前に目標との整合を確認する。Google の書籍では、各チームが承認したテンプレートを使う実践が説明されている。[出典](https://abseil.io/resources/swe-book/html/ch10.html#design_docs)

読者と文書の対象範囲を定め、冒頭で要点を伝える。対象外にする事柄は、読者が対象に含まれると期待しそうなものに絞る。[Google Technical Writing — Documents](https://developers.google.com/tech-writing/one/documents)

## この repo での構成

以下は公開指針を適用するためのローカルな構成ルール。文書の長さやレビュー会議の開催を一律には指定しない。

- **Summary**: 解決する問題、提案する方針、レビューで決めたいことを短く書く。
- **Goals / Non-Goals**: 達成したい結果と、今回の対象範囲を定める。
- **Background**: 現状、制約、設計に必要な前提を示す。関連する PRD や既存設計はリンクする。
- **Design**: 全体像と主要な設計判断を説明する。関係が複雑なら図を添え、必要な API・データの契約を示す。
- **Alternatives Considered**: 現状維持も含め、現実的な代替案と採否の理由を比較する。
- **Cross-Cutting Concerns**: 関係する懸念と対策を示す。対象外と判断したものには、その理由を書く。

必要に応じて **Validation / Rollout** と **Open Questions** を追加する。前者には目標を確かめる方法と移行・切り戻しの方針を、後者には未確定事項と解決に必要な確認を書く。未確認の事実を確定事項として埋めない。

テンプレートの記入案内は、実際の文書を仕上げる際に削除する。設計判断に関係しない実装の細部はコードや別の reference に置き、文書には判断に必要な情報を残す。

## 配置と更新

置き場は `{docs|.agent}/prd/<topic>/dd.md`。対応する PRD があれば同じ topic に置き、`docs` と `.agent` の選択は `prd` skill の配置規約に従う。このパスは Google の指定ではなく、この repo の規約である。

文書には担当者、更新日、状態を記載する。レビューで決まった内容を反映し、実装時に設計が変わった場合も更新する。
