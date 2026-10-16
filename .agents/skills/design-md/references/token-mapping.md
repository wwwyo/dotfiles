# 外部 design system の取り込み

第三者が配布する design system（配布された DESIGN.md / `theme.css` / token JSON / shadcn kit 等）を素材として使うときの規則。写像・欠損ロールの扱い・出所の記録をここで定める。

## 原則

- **値だけを取る。** 配布物の DESIGN.md を repo root の `design.md` として置かない。節構成（System / Tokens / …）も持ち込まず、[format.md](format.md) の形で新しく書く。語彙・format・check はこの skill が正本
- **1 システムにつき1回。** ページ単位で素材を差し替えない（`design.md` の前提は「pages must share the system」）。複数必要なときは `## Variants` に増やす
- **実数値を取る。** 値の出所は配布物の実装側（`theme.css` / shadcn kit / computed style）を優先し、一覧プレビュー用の JSON や screenshot の目測で色・余白を決めない。抽出モードと同じ規律
- **audit は Hallmark のまま。** step 5 の audit を素材が上書きしない。素材の署名が gate で落ちる場合（italic heading・re-drawn chrome・gradient 等）は「この build は gate 例外」と明示する。落ちたまま黙って通さない
- 素材名・URL・日付・取り込み判断を `## Notes` に記録する

## 写像

| 素材側 | design.md |
| --- | --- |
| `bg` / `fg` | `--background` / `--foreground` |
| **`accent`** / `accentFg` | **`--primary`** / `--primary-foreground`（下記参照） |
| `fgMuted` | `--muted-foreground`（`--muted` も要設計） |
| `bg2` | `--card` または `--secondary`（どちらかに決めて `## Notes` に理由） |
| `border` | `--border` |
| 用途名の付いた独自色（`announce` / `storyA` 等） | 用途名のまま role 名として追加し、`-foreground` ペアを付ける |
| `radius` | `--radius`（派生は `--radius-card` 等） |
| `fonts.body` / `display` / `mono` | `--font-body` / `--font-display` / `--font-mono` |
| `motion.duration` / `easing` | `--dur-*` / `--ease-*` |
| `motion.style`（散文） | `## Motion` の stance と reduced-motion fallback |
| `spacing.unit` | 名前付き 4pt scale の起点 |
| `spacing.section` / `maxWidth` | token ではなく layout 側の値 |
| `density` | space scale の刻み |
| `scheme`（light / dark） | dark は `.dark` block。format に field が無いので `## Notes` に明記 |

`googleFonts` の一覧はそのまま転記しない。ライセンス・loading 戦略・fallback stack を決め、`next/font` か self-host 前提へ置換する（デフォルトフローの font 手順と同じ）。

## `accent` は名前が同じで役割が違う

素材側の `accent` はブランド色であることが多い。design.md の `--accent` は hover / selected 用の控えめな面で、ブランド色は `--primary`。**名前を保ったまま写すとブランド色と hover 色が無言で入れ替わる。** 素材の `accent` は `--primary` に落とし、design.md 側の `--accent` は素材に対応物が無ければ別途設計する。

## 素材に無いロール

`format.md` が要求する `--popover` / `--secondary` / `--muted` / `--destructive` / `--input` / `--ring` と type / ease / dur の scale は、素材が持っているとは限らない。

**この抜けは check が守ってくれない。** `fgMuted` を `--muted-foreground` に写して `--muted` が無い状態は、コントラスト判定の対象から外れて静かに通り、`design-md-check.py` は error を出さない（error になるのは `var(--x)` として**参照**された未定義 token の `undefined-var` だけ）。ペアの片側しか無い `design.md` が error 0 で通る。

だから欠損ロールは**人間が決める**。agent が palette から導出してよいのは、導出根拠を `## Notes` に書ける場合だけ。どの token が素材由来でどれが設計かを区別して残す — 埋めた分を「素材に従った」ことにしない。

## 例

素材（方言）:

```json
{ "colors": { "accent": "#2f6f4e", "accentFg": "#ffffff", "bg": "#fbfaf7", "bg2": "#f1efe9",
  "border": "#e2ded4", "fg": "#1b1a17", "fgMuted": "#6b6a63" },
  "fonts": { "display": "\"Manrope\", system-ui, sans-serif", "body": "\"Inter\", system-ui, sans-serif" },
  "motion": { "duration": "200ms", "easing": "cubic-bezier(.22,1,.36,1)" },
  "radius": "8px", "scheme": "light", "spacing": { "unit": "4px", "maxWidth": "1128px" } }
```

`design.md` の `## Tokens` へ。抜粋ではなく**この節だけで形が成立する block** として書く — 素材に無いロールを抜いたままでも check は error 0 で通るので、抜粋を置くと読者がそれを完成形として写す。

```css
:root {
  /* 素材由来 */
  --background: #fbfaf7;  --foreground: #1b1a17;
  --card: #f1efe9;        --card-foreground: #1b1a17;
  --primary: #2f6f4e;     --primary-foreground: #ffffff;
  --muted: #efece5;       --muted-foreground: #6b6a63;
  --border: #e2ded4;      --input: #e2ded4;  --ring: #2f6f4e;
  --radius: 8px;
  --font-display: "Manrope", system-ui, sans-serif;
  --font-body: "Inter", system-ui, sans-serif;
  --dur-base: 200ms;  --ease-out: cubic-bezier(.22, 1, .36, 1);

  /* 素材に対応物が無いので設計した値 */
  --popover: #ffffff;      --popover-foreground: #1b1a17;
  --secondary: #f1efe9;    --secondary-foreground: #1b1a17;
  --accent: #efece5;       --accent-foreground: #1b1a17;
  --destructive: #a3342f;  --destructive-foreground: #ffffff;
  --font-mono: ui-monospace, monospace;
  --text-sm: 0.875rem;  --text-base: 1rem;  --text-lg: 1.25rem;
  --space-2: 0.5rem;    --space-4: 1rem;    --space-8: 2rem;
  --dur-fast: 180ms;    --dur-slow: 320ms;
}
```

`--muted-foreground` は素材の `fgMuted` 由来、`--card-foreground` は素材の `fg` を流用した導出値。`--muted` / `--input` / `--ring` と下段のロール・scale は素材に無いので設計した値（type・space scale は必要な段を名前付きで持つ最小構成で、段はプロジェクトごとに増やす）。素材名・URL・日付と、素材由来 / 導出 / 設計の別を `## Notes` に書く。

## 検証

```bash
python3 <この skill>/tools/design-md-check.py <repo root>/design.md
```

error 0 を確認する。ただし**check が通ることは token が揃っている証明にならない** — コントラストは `-foreground` ペア単位で判定されるので、ペアの片側が未定義だと判定ごと skip される（上記）。素材の palette が AA を満たさない場合は値の調整か `## Notes` への記録が必要になる。

`scheme` が dark の素材では `.dark` block に同じ token を宣言する。`.dark` が片側だけ上書きしても外側スコープ（`:root`）から継承して判定されるので、実際の表示色のペアで AA を満たすか確認する。
