# ADR ガイドライン

ADR（Architecture Decision Record）は、設計判断の背景、選択肢、採用理由を残す文書。
Google Cloud の [Architecture decision records overview](https://docs.cloud.google.com/architecture/architecture-decision-records) を基本にする。
付属の [テンプレート](../assets/adr.md) は公開指針を基にしたローカルな構成であり、Google の公式テンプレートの転載ではない。
文章は [共通方針](../SKILL.md#簡潔で明確に書く) に従う。

## 何を記録するか

製品・技術の選択、構成や設定の方針など、将来の読者が理由を知る必要のある判断を扱う。
判断の根拠が既存文書にない、解決策が共有されていない、複数の選択肢から選ぶ理由を残したい場合に使う。[出典](https://docs.cloud.google.com/architecture/architecture-decision-records#when_to_use_adrs)

1つの ADR では1つの判断を扱う。設計全体をレビューする場合は DesignDoc を使い、ADR から関連する箇所へリンクする。
ユーザーから作成・更新を依頼された場合はその範囲を記録する。設計議論の途中で ADR を提案する条件は [domain-modeling](../../domain-modeling/SKILL.md#offer-adrs-sparingly) に従う。

## Google の公開指針に基づく構成

Google のガイドが示す構成例を基本に、判断に必要な情報を残す。ページ数は固定しない。[出典](https://docs.cloud.google.com/architecture/architecture-decision-records#format_of_an_adr)

- **著者・チーム、日付**: 誰が記録し、いつ判断したかを示す。提案中の日付は作成日とする。
- **Context and Problem**: 背景と解決したい問題を書く。判断に関係する現状と制約を示す。
- **Requirements**: 機能要件・非機能要件のうち、選択を左右する条件と優先順位を書く。
- **Critical User Journey**: 影響する主要なユーザー操作・体験がある場合に書く。該当しなければ節を省く。
- **Options Considered**: 現実的な候補の利点・欠点を同じ評価基準で比較する。現状維持が候補になるなら、変更しない場合の結果も示す。
- **Decision and Rationale**: 採用する案と、要件に照らした採用・不採用の理由を書く。

候補数を埋めるために代替案を作らない。未確認の要件、比較結果、著者、合意を推測で補わない。
未決の判断は提案として書き、未確定事項と決定に必要な確認を明示する。
実装コードや手順の詳細は関連資料へリンクし、判断に必要な契約や設定値だけを示す。

## ローカルな補足

以下は Google の指定ではなく、この skill での運用規約。

- **状態**: `Proposed`（提案中）、`Accepted`（採用済み）、`Rejected`（不採用）、`Deprecated`（適用終了）、`Superseded`（後続 ADR で置換）を使う。採用済みと確認できた判断だけを `Accepted` にする。
- **Consequences**: 判断から生じる利点や受け入れる不利益、運用・移行への影響がある場合に追加する。既出の比較を繰り返さず、必要なら再検討する条件も残す。

## 配置と更新

ユーザーや対象 repo が指定した保存先を優先し、指定がなければ `docs/adr/` に置く。
最初の ADR が必要になった時点でディレクトリを作る。既存の命名規約がなければ `0001-<slug>.md` の形式にし、最大の番号に1を足す。過去の番号は変更・再利用しない。
これらの配置・命名規約はローカルな補足。Google のガイドは、コードに近い場所での Markdown・バージョン管理を勧めている。[出典](https://docs.cloud.google.com/architecture/architecture-decision-records#how_adrs_work)

更新前に関連 ADR を読み、現在の判断と置き換える判断を確認する。
提案中は同じ ADR を編集する。採用後の誤記修正や補足も同じ ADR に反映してよい。
採用した判断を変更する場合は新しい ADR に変更理由を書き、旧 ADR の本文を残して状態を `Superseded` にする。新旧の ADR を相互にリンクする。
判断を廃止し、置き換える判断がなければ `Deprecated` にして理由と日付を残す。
過去の判断と変更理由を残す方針は Google のガイドに基づくが、新しい ADR で置き換える手順はこの skill の規約である。

完成前に、決定と理由が対応していること、比較した案と受け入れる不利益が分かること、状態・日付・関連文書へのリンクが正しいことを確認する。
テンプレートの記入案内は削除する。
