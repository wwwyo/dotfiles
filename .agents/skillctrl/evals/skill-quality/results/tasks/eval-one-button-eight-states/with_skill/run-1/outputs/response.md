**Hallmark · component-scope run** (audience 研究者 / use 保存操作 / tone 控えめな modern-minimal、design.md の locked system に従う。macrostructure・nav・footer・enrichment は component-scope としてスキップ)

### 変更・作成ファイル（fixture 内のみ）
| ファイル | 操作 |
| --- | --- |
| `button.css` | 全面改訂 — 8 状態 + component token（spacing/radius/motion のみ） |
| `button.html` | マークアップを canonical snippet に更新（state は class/属性で差分） |
| `button.preview.html` | **新規** — 8 状態を縦並びで同時表示する preview |
| `index.html` | `#save` のマークアップのみ差し替え。`<h1>`・counter・`<script>`（保存処理）は無変更 |
| `tokens.css` / `design.md` | 無変更 |

### 見た目の要点（8 状態）
- default: accent 塗り + `--color-accent-ink`、44px タッチ底线、`white-space: nowrap`
- hover: `--color-accent-hover` のみ（`opacity: .8` を廃止、hover 作用は 1 つだけ）
- focus: `:focus-visible` 2px ring（`--color-focus`）+ **paper ハロ**。focus と accent の素の組合せは 2.6:1 で 3:1 未満のため、`--color-paper` の 2px リングで塗りから分離
- active: 1px 沈む + 塗り深化
- disabled: `opacity .55` + `not-allowed` + `disabled` 属性の 3 経路
- loading: spinner 追加 + copy を design.md の『保存中…』へ（幅固定で layout shift なし）
- error / success: 塗りではなく paper + error/success 枠 + アイコン + 文言（『再試行』/『保存済み』）。accent 塗りを唯一の重い面に保つ
- motion: 色フェード 160ms + 押下 100ms のみ。reduced motion で spinner は減速（停止はしない）、押下変形は取消

### 推定（判断が必要だった点）
1. `min-inline-size: 7.5rem` — 『保存』→『保存中…』→『保存済み』で幅が変わらないための**推定値**。更长い文言なら要調整。
2. error/success を outlined に決めた（filled 赤/緑は控えめ cadence と衝突）。破壊的でないので赤塗りは不適と判断。
3. focusハロは既存 token だけで解決する手段故选（新しい色値は追加していません、gate 48）。
4. success の自動解除・`aria-live` 読み上げ・`data-state` 遷移は**保存処理側の責務**なので未実装（scope 外）。

### 検証について（正直な申告）
ブラウザ/シェルのない環境のため、**レンダリング確認・4 ビューポート（320/375/414/768px）の目視は未実施**です。コントラスト比は手計算（WCAG 2.1 式）で preview末尾に記載（6.8:1 / 9.6:1 / 15.9:1 / 8.0:1 / 6.6:1、disabled は opacity 適用前 12.8:1 で WCAG 1.4.3 の除外対象）。`button.preview.html` をローカルで開くと 8 状態を比較できます。