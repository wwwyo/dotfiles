Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## 日本語タイポグラフィ（対象が日本語UIの場合）

欧米サービス中心のチェックリストだけでは日本語UIの仕様が欠落する。日本語UIには根本的に異なるタイポグラフィ仕様が要る — これを外すとエージェントは間違ったフォント・詰まった行間・壊れた禁則処理の画面を生成してしまう。

対象が日本語UIなら、設計・抽出どちらの経路でも以下を必ず確認し design.md に反映する:

- 和文フォントのフォールバックチェーン: `font-family` は和文 → 欧文 → generic の順（例: `"Hiragino Sans", "Noto Sans JP", "Yu Gothic", "Helvetica Neue", sans-serif`）。和文フォント単体指定は環境依存になるため不可
- 行間 (line-height): 日本語本文は 1.5〜2.0 が標準。欧文の1.4〜1.5とは異なるので、既存サイトの実測値をそのまま欧文の感覚で「狭い」と誤判定しない
- 字間 (letter-spacing): 本文は 0.04em〜0.1em 程度が可読性を上げる。全角文字が主体のため欧文とは効き方が異なる
- 禁則処理・改行: `line-break` / `word-break` / `overflow-wrap` の設定を確認する。句読点・括弧類の行頭・行末禁止（禁則）が実サイトで効いているか見る
- OpenType機能: `font-feature-settings: "palt"`（プロポーショナル字詰め、見出し・ナビ向き）、`"kern"`（和欧混植時のカーニング）。本文には `palt` を適用しない方が可読性が高いことがある点に注意
- 混植ルール: 和文と欧文が混ざる箇所（価格表記、英数字混じりの見出し等）でフォントサイズ・ベースラインがどう揃えられているかを見る

上記は design.md の custom property・font-family にそのまま乗る:

```css
:root {
  --font-family-jp: "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic", "Helvetica Neue", Arial, sans-serif;
  --line-height-body: 1.8;
  --letter-spacing-body: 0.04em;
}
```

```css
.text-body {
  font-family: var(--font-family-jp);
  line-height: var(--line-height-body);
  letter-spacing: var(--letter-spacing-body);
  line-break: strict;
  word-break: normal;
  overflow-wrap: break-word;
}

.text-heading {
  font-family: var(--font-family-jp);
  font-feature-settings: "palt";
  word-break: keep-all; /* 見出し・製品名など短い文字列専用 */
}
```

`word-break: keep-all` は見出し・製品名など短い文字列にだけ使う。本文には使わない — `keep-all` は CJK 文字同士の間の改行も抑制するため（MDN仕様上、非CJKの単語内改行を防ぐだけでなく、CJK文字間の自然な折り返しごと止めてしまう）、分かち書きのない日本語の塊に適用すると禁則どころか行が折り返せなくなり得る。

参考: [awesome-design-md-jp](https://github.com/kzhrknt/awesome-design-md-jp) — 欧米中心の既存コレクション（awesome-design-md）に欠けていた日本語タイポグラフィ仕様を補うプロジェクト。実例集として `examples/design.md` の作成時にも参照した。
