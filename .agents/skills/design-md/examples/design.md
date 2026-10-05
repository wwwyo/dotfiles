# Design — しずく会計

小規模事業者向けクラウド経費精算 SaaS（架空）の design.md 記述例。日本語タイポグラフィの書き方を示す。

## System

- Genre · editorial（実務的・静粛）
- Theme · 中立トーン基調 + 深い緑の単一アクセント
- Vibe · 静粛、実務的、信頼感、控えめな緑

## Tokens

```css
:root {
  /* Surfaces */
  --background: #f7f8f6;
  --foreground: #1f2421; /* 純粋な黒ではなく、わずかに緑を帯びた墨色 */
  --card: #ffffff;
  --card-foreground: #1f2421;
  --popover: #ffffff;
  --popover-foreground: #1f2421;

  /* Brand — 主役色は --primary（--accent は subtle surface で別物） */
  --primary: #1b6e5c;
  --primary-foreground: #ffffff;
  --primary-hover: #154f42;

  --secondary: #e3f1ec;
  --secondary-foreground: #1f2421;
  --muted: #f7f8f6;
  --muted-foreground: #5c6b66;
  --accent: #e3f1ec;
  --accent-foreground: #1f2421;

  /* Semantic — 拡張 token も -foreground ペア規約に従う */
  --destructive: #d14343;
  --destructive-foreground: #ffffff;
  --warning: #8a5310;
  --warning-foreground: #ffffff;
  --success: #1f6e48;
  --success-foreground: #ffffff;
  --disabled: #eceeeb;
  --disabled-foreground: #a8b0ac;

  /* Borders & focus */
  --border: #d8ded9;
  --input: #d8ded9;
  --ring: #1b6e5c;

  /* Radius — upstream scale の lg は base そのものなので、独自の派生は別名にする */
  --radius: 6px;
  --radius-card: calc(var(--radius) * 2);

  /* Typography — 和文ゴシック統一。数字列だけ mono で桁を揃える */
  --font-family-jp: "Hiragino Kaku Gothic ProN", "Noto Sans JP", "Yu Gothic", "Helvetica Neue", Arial, sans-serif;
  --font-family-mono: "SFMono-Regular", Consolas, Menlo, monospace;

  --font-size-h1: 1.5rem;
  --font-size-body: 15px;
  --font-size-caption: 0.8125rem;
  --font-size-mono: 0.9375rem;

  --line-height-h1: 1.6;
  --line-height-body: 1.8; /* 日本語は欧文より広い行間が前提。「間延び」と誤読しない */
  --line-height-caption: 1.6;
  --line-height-mono: 1.5;

  --letter-spacing-body: 0.04em; /* 全角主体の行に軽い抜けを作る */
  --letter-spacing-caption: 0.05em;

  /* Spacing — 5段階 */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 40px;

  /* Elevation — ほぼフラット */
  --shadow-sm: 0 2px 6px rgba(0, 0, 0, 0.08);
}
```

## Components

```css
.text-h1 {
  font-family: var(--font-family-jp);
  font-size: var(--font-size-h1);
  font-weight: 700;
  line-height: var(--line-height-h1);
  font-feature-settings: "palt"; /* 見出しにのみ適用。本文には付けない */
  word-break: keep-all;
}

.text-body {
  font-family: var(--font-family-jp);
  font-size: var(--font-size-body);
  font-weight: 400;
  line-height: var(--line-height-body);
  letter-spacing: var(--letter-spacing-body);
  line-break: strict;
  word-break: normal; /* 本文には keep-all を使わない。行が折り返せなくなるため */
  overflow-wrap: break-word;
}

.text-caption {
  font-family: var(--font-family-jp);
  font-size: var(--font-size-caption);
  line-height: var(--line-height-caption);
  letter-spacing: var(--letter-spacing-caption);
  color: var(--muted-foreground);
}

.text-mono {
  font-family: var(--font-family-mono);
  font-size: var(--font-size-mono);
  font-weight: 500;
  line-height: var(--line-height-mono);
}

.btn-primary {
  background: var(--primary);
  color: var(--primary-foreground);
  border-radius: var(--radius);
  padding: 10px 20px;
  border: none;
}

.btn-primary:hover {
  background: var(--primary-hover); /* 色相を変えずに沈める */
}

.input {
  background: var(--card);
  color: var(--foreground);
  border: 1px solid var(--input);
  border-radius: var(--radius);
  padding: 10px 12px;
}

.input:focus {
  border-color: var(--ring);
}

.input-disabled {
  background: var(--disabled);
  color: var(--disabled-foreground);
  border-radius: var(--radius);
  padding: 10px 12px;
}

.card {
  background: var(--card);
  border-radius: var(--radius-card);
  padding: var(--space-lg);
}

.table {
  border-collapse: collapse;
  width: 100%;
}

.table th,
.table td {
  border-bottom: 1px solid var(--border);
  text-align: left;
  padding: var(--space-sm) var(--space-md);
}

.badge {
  display: inline-block;
  font-family: var(--font-family-jp);
  font-size: var(--font-size-caption);
  border-radius: var(--radius);
  padding: 2px 8px;
}

.badge-success {
  background: var(--success);
  color: var(--success-foreground);
}

.badge-warning {
  background: var(--warning);
  color: var(--warning-foreground);
}

.badge-danger {
  background: var(--destructive);
  color: var(--destructive-foreground);
}
```

## Icons

- lucide で統一（24px grid、stroke 1.5、fill なし）。数字・単位（¥・%）は icon にせず `.text-mono` のタイポグラフィで表す
- 例外: 銀行・クレジットカード等の外部サービス連携 logo は各社の公式 asset のみ使用可

## Logo

- Logomark: 一滴のしずくを24px grid・単色の塗りで描く。外形は円と直線の組み合わせで、滴の高さ対幅は3:2（黄金比は外形に当てると細長くなりすぎたため内部の分割にも外形にも使わない）。単体アイコンに使い、16pxでも輪郭が読める形にする
- Wordmark: 「しずく会計」を `var(--font-family-jp)` weight 700 で組む。字幅はフォント標準のプロポーション（個別の幅補正なし）。全隣接ペアを実サイズで目視確認した上で tracking 0em とし、個別の kerning 補正はなし。`palt` は掛けず、途中改行は禁止する
- Usage: 単体アイコンには logomark、名前を示すヘッダーには wordmark を使う。最小使用サイズは logomark 16px・wordmark 字高 12px。しずくの丸みと和文のゴシック体を共通の穏やかな造形方針とし、実サイズと拡大表示で確認する
- Assets: 色は面の前景色に従う。clearspace は logomark のマークの高さ、wordmark の字の高さをそれぞれ基準に、上下左右に 1/2 以上

## Motion

- silent — 状態変化は色の即時切替のみ。transition を前提にしない設計
- reduced-motion fallback · 常に同等（motion を情報伝達に使わない）

## Exports

- `tokens.css` / `globals.css` の `:root` / Tailwind `@theme` 等の派生物はこのファイルの
  `## Tokens` から生成する。直接編集しない

## Notes

- 架空プロダクトの記述例。実プロダクトでは選定の理由・却下した案・抽出元（URL / ツール / 日付）をここに書く
- `--disabled` ペアの低コントラスト（実測 1.9:1）は意図的。WCAG AA は incidental な disabled 状態を免除するが、checker は warning として報告する（error ではないので exit 0 になる）
