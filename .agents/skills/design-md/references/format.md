Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## design.md のフォーマット

対象 repo の root に書く。目安は 〜200行 — skill の読み物ではなく、agent が毎回読めるサイズに収める。css block は最小限の基盤に絞り、component のバリエーションが育って超えそうなら詳細は consumer 側（product-design skill の references）へ畳む。`## Tokens` / `## Components` の中身は fenced ` ```css ` block で書き、check が機械的に読める形にする。

````markdown
# Design — <プロダクト名>

Locked design system。この repo の視覚値の正本。product-design skill はこれを参照し、
Hallmark は検出すると pick をこれに従わせる。値を変えるときはこのファイルだけを編集し、
派生物は再生成する。

## System
- Genre · <editorial / modern-minimal / atmospheric / playful>
- Theme · <palette の方針と anchor を一文で>
- Vibe · <4〜8語>

## Tokens

shadcn/ui の語彙で `--background` / `--foreground`、card・popover・primary・secondary・muted・accent・destructive の各 `-foreground` ペア、`--border` / `--input` / `--ring` / `--radius` を宣言する。ブランド色は `--primary`、hover/selected の控えめな面は `--accent`。font・text・space・ease・duration、warning・disabled 等の拡張も必要に応じて宣言する。派生 radius は upstream scale に沿うか `--radius-card` 等の独自名にし、予約名に別倍率を当てない。

下記は有効な CSS の最小例。実際の出力では設計・抽出した値へ置き換え、上記の必要な token をすべて `--name: value;` 形式で書く。語彙の一覧だけを CSS block に置かない。

```css
:root {
  --background: oklch(98% 0.01 90);
  --foreground: oklch(20% 0.01 90);
  --radius: 0.5rem;
}
/* dark mode が必要なら .dark に同じ token の dark 値を宣言する */
```

## Components

```css
/* 基盤 component クラス。token だけでは伝わらない組み合わせ（.text-body / .btn /
   .card / .table / .stat-strip 等）。ページ側で同じ判断を重複させないための層 */
```

## Icons
- <library + grid + stroke + 例外条件>（例: lucide・24px・stroke 1.5・外部サービス公式 logo のみ例外）

## Logo
- Logomark: <単体マークの造形・grid・線幅・採用した幾何学と比率（黄金比等を使った箇所があればその箇所）。抽出で未確認なら「未制定」、参照範囲で不在・不使用を確認できれば「なし」と根拠・確認範囲>
- Wordmark: <製品名全体の造形・字幅比・ベースライン・mark との間隔。組版の場合は font / weight / case / 採用した OpenType feature（例: `palt` の有無） / tracking / ペア別 kerning / 改行可否。抽出で未確認なら「未制定」、参照範囲で不在・不使用を確認できれば「なし」と根拠・確認範囲>
- Usage: <存在する logomark / wordmark の使い分け・最小使用サイズを含む実表示サイズ。抽出で未確認なら「未制定」、参照範囲で不在・不使用を確認できれば「なし」と根拠・確認範囲>
- Assets: <パス・バリアント（mono / dark）・clearspace>

## Motion
- <stance（silent / 1〜2 primitives / motion-cut 等）と reduced-motion fallback>

## Exports
- `tokens.css` / Tailwind `@theme` / globals.css の :root 等の派生物は本ファイルから
  生成する。直接編集禁止。`## Tokens` を変えた編集は、同じ編集で Exports も再生成する
  （check は Exports 節を読まない — 古いまま残っても機械検知されない）。

## Notes（optional）
- 選定の理由・却下した案の「何が嫌か」。抽出で作った場合は出所（URL / ツール / 日付）
````
