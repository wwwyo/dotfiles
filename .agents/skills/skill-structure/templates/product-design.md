# Product Design 型

プロダクトの UI/UX 判断（コードに残らない rationale）を持つ型。component pattern の選定・form/modal/toast の挙動・デザインとの照合・利用者向け文言・堅牢化を扱う。

## いつこの型か

- UI/UX の判断根拠（なぜそのパターンか）・デザイン正本との照合・利用者向け文言の一貫性を蓄積したいとき選ぶ
- 実装機構（ビルド・テスト・レイヤー配置・PR 運用）は [guideline 型](guideline.md)、ログ調査の手順は [investigation 型](investigation.md) が対象。デザイン判断とそれらが両方要る場合は型を分けて共存させる

## SKILL.md の routing 骨格

| Mode | やること | 読む reference |
| :--- | :--- | :--- |
| **Shape** | 着手前に対象を理解する。ドメイン概念の把握・デザイン正本との照合・既存共有 component の有無確認 | domain-context / figma-fidelity |
| **Implement** | component / form を組む | ui-patterns |
| **Review** | 実装をデザイン規約に照らす | ui-patterns / figma-fidelity |
| **Copy** | 利用者が見る文字列を決める | copy |
| **Harden** | ブラウザ対応・IME・a11y で堅牢化する | harden |
| *(任意)* | 見た目を揃える | design.md（repo root — クラス名と変数名を使う） |

判断が複数 mode にまたがるときは Shape → Implement → Copy → Harden の順に読むと自然。

## references の切り方

1 reference = 1 mode。

- `domain-context` — Shape。判断の土台になるドメイン概念（対象領域固有の用語・階層構造）の整理
- `figma-fidelity` — Shape / Review。デザインの正本の優先順位、正本との照合手順、既存共有 component の再利用判断
- `ui-patterns` — Implement / Review。component / form / modal / toast など UI 実装パターンの規約
- `copy` — Copy。用語・語彙の一貫性、文言の改行、命名規約、エラー・通知文言
- `harden` — Harden。対応ブラウザ、IME ガード、a11y semantics、見た目の退行検知
- `principles` — mode に属さない。パターンが競合して判断が割れたとき／前例のない構造を決めるときだけ立ち返る全社レベルの原則。日常の実装判断では読まない

## 値の層（design.md）

視覚値の正本は **repo root の `design.md`** に置く（skill 配下ではない）。`## Tokens` / `## Components` の fenced ```css block に、色・字・余白・角丸の custom property と header / table / stat strip / button など基盤 component 用のクラスを持つ。語彙は shadcn/ui 規約（`--primary` / `--primary-foreground` の `-foreground` ペア、`--radius`、`.dark` override）。

repo root に置くのは reader がこの skill の agent だけではないため — Hallmark は Step 0 で design.md を検出して生成 pick をそれに従わせるし、skill を持たない agent も同じ正本を読める。skill 直下に置くと consumer ごとに正本が分かれる。

agent には SKILL.md か reference に「視覚値は `/design.md` を読む」と1行書いておき、design.md 自体を読ませる。design.md は 〜200 行を目安に抑える（design-md skill の format 定義が上限の正本）。肥大して語彙表なしでは読めなくなったら、クラス名・変数名の一覧を SKILL.md / reference に畳み、CSS 本体を読ませない形に戻す。

方針は「最も狭い場所に置く」: 判断は references の prose に、再利用できる視覚値は design.md に、機械判定は tools に置く。

値は [design-md skill](../../design-md/SKILL.md) で起こす。デフォルトは 0 から作る（prototype 発散→人間の合意→抽出）。既存プロダクトからの抽出（ライブURL・コード・Figma）はソース明示時だけ。`-foreground` 命名・日本語タイポグラフィ・check の制約はどちらでも同じ。

## tools / evals

両方持つ。

- `tools/` — design.md の check（`design-md-check.py`：未定義 var 参照・コントラスト比、`page-check.py`：生成ページの構図と design.md を通さない直書きの兆候）は **[design-md skill](../../design-md/tools/) が正本**を持つ。コピーせずそこを実行する（コピーは drift するし、product-design skill が未作成でも design-md だけで検証できる）。この skill 自身の `tools/` には repo 固有のルール（誤りやすい prop 名の誤用、非推奨の IME 判定、production コードに残ったテスト用属性など）だけを lint 化して置く — 決定論的に判定できるものに限り、判断が要るルールは reference 側に残す。lint が通ることは規約準拠の証明にはならない旨を明記する
- `evals/` — reference に逐語では書かれていない未見の UI 題材で、reference だけを根拠に正しい判断を再現できるかを検証する。自動採点は持たず、エージェント/人間が回す。どの reference にも紐付かない結果は coverage gap として報告し、reference 追加の候補にする。加えて、固定シナリオ（prompt + mock 入力 + viewport を凍結）で生成したページに `design-md-check.py` を回す層を持ち、design 判断の変更前後で既知失敗の件数を比較する。修正は「判断→reference、視覚値→design.md、機械判定→tools」の最も狭い場所へ入れる。1モデルだけの失敗は再発するまでルール化しない

### 固定シナリオの始め方（references が薄い新規 skill）

references を白紙から育てるときは、harness を作る前に1シナリオで比較を1回回す。

1. その repo で agent に作らせたい成果物を1つ選び、prompt・mock 入力・viewport を凍結する
2. skill を読ませずに1回生成し、ベースラインとして保存する（reroll しない）
3. skill を読ませて同条件で1回生成し、2つを並べて人間に見せる。並べる形は人間が開ける self-contained な HTML か screenshot で、agent の自己申告や「〜が違う」の要約だけで済ませない
4. 逸脱の判定と置き場（reference / design.md / tools）は人間が決める。agent は候補を挙げてよいが、承認前に encode も commit もしない。承認後、逸脱を観測可能な文に直し（「clean に」ではなく「evidence table は使える幅を全部使う」）、最も狭い場所へ入れる
5. 同じシナリオを再実行し、結果をまた人間に見せて消えたか判定してもらう。消えた逸脱が `design-md-check.py` / `page-check.py` で拾えるものなら check にも足す

シナリオは用途が増えたら足す。未テストの用途で失敗が出たら、その用途を新しいシナリオに昇格させる

## governance

AGENTS.md に review loop の evidence 源を書く。随時（実装/レビュー/DD 作成中に得たもの）＋週次集約（PR review コメント・デザインツールの変更・チャットの議論）の 2 経路。ルール化（reference 追記 / lint rule / eval 追加 / design.md の値修正）はいずれも人間承認を経てから反映する。

## 原型

[Vercel の product-design skill](https://vercel.com/blog/teaching-agents-product-design-at-vercel)、[design.md 記事](https://vercel.com/blog/how-our-agents-build-on-brand-pages-with-design-md)
