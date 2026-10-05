# anno.js の呼び出し例

`anno.js` はブラウザページ内で動く関数。selector とテキストで対象を指定し、座標は自分で計算させる（エージェントが目視で座標を推定しない）。

[orca-cli](../../orca-cli/SKILL.md) の version-matched browser guideを先に読む。以下の `orca` は同skillで解決したexecutable、`page` は対象の `browserPageId`。

## spec の例

```js
[
  // 削除された要素を示す: 枠だけ、ラベルは下に
  { type: "box", sel: "button.start-visit-prep", label: "削除", labelPos: "below" },

  // 表示内容が変わった要素: 枠 + 右にラベル
  { type: "box", sel: ".breadcrumb", txt: "顧客対応", label: "個社名を削除", labelPos: "right" },

  // 移動を示す: 移動元 → 移動先を矢印でつなぐ
  { type: "arrow", sel: "#chat-panel .chip", toSel: ".solution-card .reason-button", label: "ここへ移動" },
]
```

## Orca browser での実行

`SKILL=<skill_dir>` とする（SKILL.md 参照。dotfiles では `~/.agents/skills/reporting` が正本）。`tools/anno.js` は全体が 1 つの
アロー関数式なので、spec.js は `(<anno.js の中身>)(<specs 配列>)` の形にする。specs は JSON として
書けるので `specs.json` に保存し、次の一行で組み立てる:

```bash
shots_dir="$(pwd)/shots"
mkdir -p "$shots_dir"
page="<browserPageId>"
orca exec --command "set viewport 1440 900" --page "$page" --json
orca goto --url <url> --page "$page" --json

cat > specs.json <<'EOF'
[
  { "type": "box", "sel": ".breadcrumb", "txt": "顧客対応", "label": "個社名を削除", "labelPos": "right" }
]
EOF
{ printf '('; cat "$SKILL/tools/anno.js"; printf ')('; cat specs.json; printf ')'; } > spec.js
orca eval --expression "$(cat spec.js)" --page "$page" --json
# 戻り値（"box .breadcrumb" や "MISSING ..."）を確認し、MISSING があれば selector を直して撮り直す

orca exec --command "screenshot \"$shots_dir/crumb-after.png\"" --page "$page" --json
```

before/after で同じ URL 群を撮るときは、before 側（main / デプロイ済み）にも同じ spec で注釈を入れる。差分がない箇所に注釈が付いてしまう場合は selector が違う可能性が高い。

after でだけ新規追加された要素を狙う spec は、before の撮影では MISSING になるのが正しい挙動。エラーではないので該当行はそのまま無視してよい（before 用に spec を分けたり、注釈レイヤーを隠す必要はない）。

## 箇条書きと画像を番号で対応させる

`opts.number: true` を渡すと、spec の並び順に ①②… を label の先頭に自動で振る。report.html の箇条書きも同じ順で書けば、画像の番号とテキストが 1:1 で対応する。

specs.json:
```json
[
  { "type": "box", "sel": ".price", "label": "価格表示" },
  { "type": "box", "sel": ".add-to-cart", "label": "購入ボタン" }
]
```

opts は `anno.js` の第 2 引数なので、specs.json の後にカンマ区切りで足す:
```bash
{ printf '('; cat "$SKILL/tools/anno.js"; printf ')('; cat specs.json; printf ', {"number":true})'; } > spec.js
```

番号は見つかった spec だけを数える（MISSING はカウントしない）。MISSING が出たら selector を直してから番号付けをやり直す。

## 縦に長いページを撮る（full-page）

`orca exec --command "screenshot --full \"$shots_dir/crumb-after.png\"" --page "$page" --json` で撮るときは `opts.full: true` を渡す。既定（省略時）は viewport 固定の注釈なので、full-page 画像では位置がずれる。

specs.json: `[{ "type": "box", "sel": ".footer-cta", "label": "追加した CTA" }]`

```bash
{ printf '('; cat "$SKILL/tools/anno.js"; printf ')('; cat specs.json; printf ', {"full":true})'; } > spec.js
```

画面外（below-the-fold）の要素を狙うときは、`opts.full: true` を使うか、事前に `orca eval --expression "document.querySelector('.footer-cta').scrollIntoView()" --page "$page" --json` してから注釈を入れる。仮想スクロールのページでは scrollIntoView 自体が要素を DOM に出現させる副作用もある。
