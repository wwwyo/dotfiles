# Guideline 型

実装機構（言語規約・レイヤー配置・ビルド/テスト/デプロイ・PR 運用）の慣例とパターンを持つ型。判断はコードの書き方・置き場所・検証手順に関するもので、UI/UX の見た目の判断は含まない。

## いつこの型か

- 言語の書き方・ディレクトリ/レイヤー配置・API 設計・マイグレーション・PR 運用など、実装機構そのものの規約を蓄積したいとき選ぶ
- UI/UX の見た目・文言の判断は [product-design 型](product-design.md)、原因調査の手順は [investigation 型](investigation.md) が対象。同じ領域で機構とデザイン判断の両方が育つなら、型を分けて共存させる

## SKILL.md の routing 骨格

対象範囲（どの path・どの層に適用されるか）を routing の前に表で示すと発見性が上がる。

| Path | 役割 |
| :--- | :--- |
| （対象ディレクトリ・レイヤー） | （そこで何をする層か） |

| やること | reference |
| :--- | :--- |
| レイヤー配置の正本（ディレクトリスタイル） | directory-handbook |
| 言語の書き方の規約（命名・doc・null 表現） | conventions |
| レイヤー責務とエラーの扱い | layers-and-errors |
| データアクセス層を作る | repository |
| テストを書く | testing |
| スキーマ変更を書く | migration |
| API を設計・生成する | api-design |
| 設計文書を書く | 下記に inline section（reference にするまでもない小トピック） |
| PR / stack を運用する | 下記に inline section |

## references の切り方

1 reference = 1 やること（実装機構の一手順）。mode ではなくタスク単位で切る点が product-design 型と異なる。reference にするほどの分量がないトピック（設計文書の書き方、PR 分割の基準など）は SKILL.md 内の inline section で持ってよい。

## tools / evals

lint は持つが、専用の `tools/` ディレクトリを新設しない — 既存のビルド/テスト/lint コマンド（言語標準のビルドツール・linter）をそのまま検証コマンドとして AGENTS.md に明記する。判断が必要な逸脱（既存コードとの一貫性・命名の妥当性）はコマンドで検出できないため reference 側に残す。evals は持たない — guideline 型が扱うのは確立した規約であり、未見の題材への汎化を測る対象ではない。

## governance

AGENTS.md に review loop の evidence 源を書く。随時（実装/レビュー/設計文書作成中に得たもの）＋週次集約（PR review コメント・チャットの議論）の 2 経路。近傍の既存コードが最適でないパターンを使っていても追従せず、自分が触っている箇所は改善する方針（Boy Scout Rule）を明記する。

