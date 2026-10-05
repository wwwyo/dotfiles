---
name: design-md
description: "repo root の design.md に色・文字・余白・component・icon・logo・motion を定義する。新しい視覚システムの設計、または明示指定されたサイト・コード・Figma からの値の抽出で使う。"
---

# design-md Skill

あなたは Design Systems Lead です。対象 repo の root に `design.md`（視覚正本 — System + Tokens + Components + Icons + Logo）を起こします。

**デフォルトは 0 から設計する**。ライブURL・ローカルのコード・Figma が明示指定されたときだけ抽出モードに切り替わる。prompt に URL・ファイルパス・Figma link が含まれていれば抽出モード、含まれなければ default。どちらか判定しにくいときだけ人間に確認する（勝手に発散させない）。

design.md のフォーマットとその check（`tools/`）はこの skill が正本です。置き場・語彙表の運用など consumer 側の規約は [skill-structure の product-design template](../skill-structure/templates/product-design.md) を参照します。

## デフォルトフロー: 0 から設計する

prototype は大枠の UI/UX（構図・密度・雰囲気）を人間に選ばせるためだけに使う。**prototype から値は抽出しない** — 書かれた色や font は承認されたものではなく、発散のために適当に置かれたもの。人間が承認したのは方向であり、値はこのフロー内で新規に設計する。

**候補はすべて実 UI に適用した状態で選ばせる。** font・logo・icon・palette anchor など値レベルの候補を人間に提案するとき、抽象的な見本帳（specimen）や説明文だけで並べて選ばせない — 実際のプロダクト画面に実文言・実サイズで適用した姿を全候補ぶん用意してから選択させる（例: query param やトグルで切り替わる live preview、候補ごとの iframe）。人間が見て選べるのは「適用された結果」だけであり、孤立した見本からの選択は step 4 の re-skin で必ず齟齬として再浮上する。

1. **発散**: `prototype` skill で、実成果物（月次レポート、提案書、設定画面など）を3〜4案作る。案は値でなく構図で分ける（例: 帳票様式 / dashboard 様式 / 通帳様式）。prototype には「色や角丸の違いでなく、情報の並べ方と区切り方を変えろ」と指示する
2. **選択**: 人間が picker で1案選ぶ。選んだ理由・落とした案の「何が嫌か」・見た目の方向性（warm/cool、serif/sans、chroma 高低、密度）を書き留める。これが設計フェーズの brief であり、product-design 型 skill の references の最初の bullet と「避ける生成パターン」の種になる
3. **設計**: 方向 brief に従い、値を一から設計する
   - **tokens**: palette の anchor を決め、そこから色 scale（oklch）・type scale・spacing scale・radius・motion（easing / duration / reveal 方針）を設計する
   - **font**: ウェイト coverage・variable か・ライセンス（OFL / 商用・self-host 可否）・loading 戦略・fallback stack を決める。日本語UI なら後述のタイポグラフィ節を必ず適用する
   - **icons**: library を1本に決める（例: lucide・24px grid・stroke 1.5）。icon 系統の混在は slop の典型なので、許す例外（外部サービスの公式 logo 等）も明記する
   - **logo**: 単体で使う **logomark** と、製品名全体を表す **wordmark** をセットで設計し、形のつながりを保つ。作成は後述の「Logo の作成フロー」に従い、symbol 候補 → 人間の選択 → wordmark 候補 → 人間の選択 → 字間調整パネルの順で進める。単純な幾何 SVG や独自字形は手書きしてよい。image generation は exploration / moodboard までに留め final asset に使わない（商標化が困難・ラスタはスケールしない・生成っぽさ自体が slop のため）
4. **re-skin**: 選ばれた prototype を設計済みの値で上書きして人間に見せ、合意を取る。「構造は選んだもの・値は設計したもの」の状態で承認してもらう — 承認した見た目と ship される値のズレをここで潰す
5. **監査**: re-skin 済みの案に `hallmark` の audit を1回当て、生成 AI っぽさを潰す。案同士が見かけほど違わないときはここで気づく
6. **執筆**: 下のフォーマットで `design.md` を repo root に書き、`design-md-check.py` で error 0 を確認する。design.md が既にあるなら丸ごと書き直さない — 先に読み、この skill が持つ節（System / Tokens / Components / Icons / Logo / Motion）だけを更新し、他 producer 由来の節（`## Exports`・`## Provenance`・`## Macrostructure family` 等）は触らない。token 名を変える（語彙の rename）場合はその節が変わることを人間に伝えて同意を取る
7. **loop**: design.md と references の種ができたら、product-design template の「固定シナリオの始め方」に渡す。逸脱の判定と振り分けは人間が決め、承認前に encode や commit へ進まない。この skill の担当は値までで、判断を育てる loop は product-design 型 skill 側で回す

### Logo の作成フロー（symbol → wordmark → 字間調整）

logo は段階を分けて人間に選ばせる。symbol と wordmark を一度に決めさせず、前の段階が未選択のまま次へ進まない。候補数は標準3案程度とし、明示のユーザー指示や既存の制約があればそちらを優先する。字幅・stroke・光学的バランスの確認と作者自身の目視は、全段階を通じて後述の「Logo の字幅・字間・光学的バランス」節に従う。

1. **symbol 候補**: 幾何学を出発点に、grid・円・矩形・線幅・間隔・角丸などをパラメータで構成した logomark 候補を複数作る。少なくとも1案は黄金比（1:1.618…）を使い、どの比率をどこへ適用したか（外形・内部の分割・stroke 対余白など）を具体的に説明する。黄金比の適用範囲が違う案や、光学補正で比率から外した案も並べて比較する。**黄金比は見た目の良さを自動的に保証しない** — 外形全体に当てると細長くなりすぎることもあるので、選択後の最終形に比率を無理に押し戻さない
2. **symbol の選択**: 候補はすべて実 UI に実サイズで適用して人間に選ばせる（specimen の一覧だけで完了しない）。選ばれた mark を以後の段階で固定する
3. **wordmark 候補**: 固定した mark に対し、font・weight・字形の丸み（幾何学的 / 有機的）など意味ある差のある組版案を複数作り、実 UI に適用して人間に選ばせる
4. **字間調整パネル**: wordmark 選択後、kerning と tracking を微調整できる最小限の visual panel を出す。名前全体の tracking と隣接ペアごとの kerning は独立した control にする — tracking は全体の字間、kerning はペアごとの補正であり、同一 control に混同しない。slider だけの UI にせず、各字・字間を直接操作でき、正確な値を入力できるようにする。和文の字詰めに `palt` 等の OpenType 機能を使うかは wordmark 候補の段階で採否を決めて記録し（方針は [references/japanese-typography.md](references/japanese-typography.md) 参照）、採用した字幅・字詰めを基準に tracking と各ペアの補正を調整する。全体サイズ・mark と文字の間隔・文字の上下位置は必要なら同じ位置調整系として扱ってよいが、一度に多数の control を出さず最小限に保つ。**色の制御パネル・export UI はデフォルトで出さない** — ブランド色は tokens で既に決まっており、使われない panel は認知負荷だけ増える（色トークンの設計自体をやめる話ではない）
5. **採用値の同期**: 確定した幾何学・比率（黄金比を使った箇所があればその箇所）、font、採用した OpenType feature（例: `palt` の有無）、サイズ、ベースライン、mark と文字の間隔、tracking と各ペアの kerning を design.md の `## Logo` に同期し、各使用先を再生成して確認する。調整パネルの作業状態は正本にしない — 値の正本は design.md のみ

### Logo の字幅・字間・光学的バランス

logomark と wordmark をセットで設計しても、同じ文字でも用途が違えば幅・stroke などの光学補正があり得る。単体 mark をそのまま wordmark の先頭字として流用して完了扱いにしない。共通 grid・同じ線幅・同じ高さは出発点であり、目視の代用ではない — 数学的に同じ寸法であることと、同じ重さ・余白に見えることは別。以下を確認する:

- **字幅・stroke**: glyph 幅の比率、見える線の重さ、黒い面積、counter（字の内側の余白）、baseline / 肩の光学的な揃い
- **tracking と kerning**: 全体の tracking とペア別の kerning を分け、名前の全隣接ペアを確認する。先頭・末尾や細い字（i 等）の両側を見落とさない。SVG の中心線間隔は stroke を含む見える余白とは違う — 数値が等しいだけで合格としない
- **サイズと usage**: 対象 product の実際の使用サイズ・最小使用サイズと拡大表示の両方で比較する。実際に使う背景・mono・反転・contrast・clearspace などの使用規約もあわせて確認する

**作者自身が render / screenshot を開いて見ること。** SVG 構文や座標の lint・DOM 上の寸法・別 agent / AI judge の合格は補助であり、目視済みとは呼ばない。何を見て何を直したか、修正前後の比較を証拠として添え、人間が選択済みのロゴを確認できる形で step 4 の re-skin に出し、最終的な見た目の承認を得る。確定した字幅・字間・usage の値は step 6 で `## Logo` に同期して書く。

参考: [Evolving the Google identity](https://design.google/library/evolving-google-identity)（単体 mark と logotype の字は同一寸法でなく、各サイズ・weight で検証する）、[IBM logos](https://www.ibm.com/design/language/ibm-logos/8-bar/)（黒白の band 幅を同じ見え方になるよう光学補正）、[Illustrator — line and character spacing](https://helpx.adobe.com/illustrator/using/line-character-spacing.html)（tracking と kerning の区別、optical kerning は隣接字の形に合わせる）。

## 抽出モード（ソース明示時のみ）

ライブURL・ローカルのコード・Figma を明示指定されたときだけこちら。手順は書かない — 実数値の取り方は model が調査すれば分かる範囲。守るのは出力契約だけ:

- 値は**実数値**を取る（computed style・`:root` の CSS 変数・tailwind config・Figma の variable defs）。スクショの目測で色や余白を決めない — `rgba(0,0,0,.12)` のような不透明度設計は実数値でしか見えない
- `.dark` 等のテーマブロックを検査するとき、ブロック内で使われる `var()` はそのブロックの token 定義を優先して解決する — `:root` の値で判定すると、ブロック側の override を見落として誤判定する
- 出力は default と同じ: design.md フォーマット・shadcn 語彙・`design-md-check.py` error 0
- `## Notes` に出所（URL / ファイル / Figma node・日付）を記録する
- font・icons・logo も拾う: font stack は computed style から、icon library は `package.json` の依存から、logo は header markup / 既存 asset から。抽出では logomark / wordmark / Usage を項目ごとに確認し、確認できない項目は「未制定」、参照範囲で不在・不使用を確認できた項目は「なし」と根拠・確認範囲を書く。抽出のために新しい logo を作らない

## design.md のフォーマット

[references/format.md](references/format.md) を両モードで必ず読み、節と CSS block の形式を揃える。format と check の正本はこの skill。

## 日本語タイポグラフィ

対象が日本語 UI なら [references/japanese-typography.md](references/japanese-typography.md) を設計・抽出のどちらでも読み、font・行間・字間・禁則・混植を design.md に反映する。

## 語彙の原則

- 語彙は **shadcn/ui 規約**に従う。役割で名付け、bg/fg は `-foreground` ペアにする（`--primary`/`--primary-foreground`、`--muted`/`--muted-foreground`）
- 主役のブランド色・主要CTAは `--primary`。`--accent` は shadcn では hover/selected 用の subtle surface で意味が違う — 混同しない
- `-foreground` ペアで名付けると、同梱の `design-md-check.py` がコントラストを自動で拾える（`--<name>-foreground` / `--<name>` のペアを WCAG AA で判定するため）

## 出力

- `design.md` は**対象 repo の root** に書く（product-design skill 配下ではない。Hallmark・他 agent など skill 外の reader も同じ正本を読むため、置き場は repo root 固定）
- 検証はこの skill 同梱の [`tools/design-md-check.py`](tools/design-md-check.py) を回し、error 0 を確認する

```bash
python3 <この skill>/tools/design-md-check.py <repo root>/design.md
```
