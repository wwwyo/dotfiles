---
name: reporting
description: "ある作業（PR / diff / セッションでの変更）や調査・リサーチ結果を、読み手が短時間で理解できる単体 HTML にまとめる。UI 変更・設定変更・データ移行・障害調査・技術調査・コード構造の変更いずれも対象。「レポートにまとめて」「変更点をまとめたノート」「共有用の html」「before/after で説明」「作業レポート」「reporting」「調査結果を共有」「何を変えたか説明する資料」などのリクエスト時に使用。"
user-invocable: true
---

# Reporting

作業（PR / diff / セッション内の変更）や調査・リサーチ結果を、読み手が短時間で理解できる単体 HTML にまとめるスキル。本命は「変更や結果を理解しやすくする」こと。biz 向け共有はその用途の一つに過ぎず、読者に合わせて情報の粒度を変える。

## 入力の決め方

対象・読者・レポート型を先に決める。決め方次第で本文の書き方が変わる。

- 対象: PR 番号 / branch diff / セッション内の変更 / 調査結果、のいずれか。ユーザーの指示から特定できなければ現在の branch diff を既定にする
- 読者: エンジニア or 非エンジニア（biz）。不明なら聞く
- レポート型: 以下のいずれか。1 レポートに複数の型が混ざるときは section 単位で型を切り替える
  - UI 変更: 画面の変更。手順 c の撮影フローが本体
  - 変更（非 UI）: 設定・データ移行・コード構造の変更 → `references/change.md`
  - incident: 障害・不具合・不審挙動の調査 → `references/incident.md`
  - research: 技術調査・比較検討・事実確認の結果 → `references/research.md`

読者で変える粒度:

- 非エンジニア向け: PR 番号・commit・URL・作成者・作成日などの識別子を本文に書かない。文脈が共有済みなら経緯（why）も書かない。画面や結果そのものだけを見せる。ただし research 型の Sources（出典一覧）と本文の `[n]` 出典参照は識別子ではなく内容なので、読者に関わらず残す
- エンジニア向け: diff へのリンクや影響範囲を足してよい。ただし「Related: [PR](url)」1 行までに留める

## 構成の型（守るべき決定）

- 変更点・わかったことは箇条書きだけで書く。1 bullet = 1 つの事実、動詞で終える文にする。段落で説明しない
- 見出しは「何を変えたか・何がわかったか」の文にする（「パンくず」ではなく「パンくずを最適化」）
- まとまりは読者が辿る順に並べる（アプリならタブ順・画面順、非 UI なら処理の流れ順、incident なら症状→原因→対処、research なら読者が知りたい順）。レビュー回や日付・調査した順で分けない
- 目次を先頭に置く。`main` の max-width は 80vw
- 画像は「反映前」「反映後」のキャプションを画像の**上**に置く。すべての画像に注釈（赤枠 or 矢印）が入っていること。注釈のない画像は載せない
- 読者が認識できない粒度の変更（1px の罫線、色変更、説明文の追加程度）は書かない。位置の移動・要素の削除・導線の追加は書く
- 単体 HTML にする。画像は base64 埋め込み、外部依存は Google Fonts の link だけ。取得できなくても system font で読める fallback stack を持つ（`templates/report.html` の font-family 参照）。artifact ではなくファイルで渡す
- 自己完結にする（読者が非エンジニアのとき）: PR 番号・commit・URL・作成者・作成日を本文に書かない。ただし research 型の Sources と本文の `[n]` 出典参照は出典なので残す
- 文章は `japanese-tech-writing` skill に従う（空句・翻訳調の比喩・冗長を避ける）
- 本文は HTML なので markdown 記法は効かない — code 表現はバックティックではなく `<code>` で書く
- 事実だけを書く。diff・コマンド出力・調査で実際に確認したもの。憶測は書かない（推定は「（推定）」と明記）
- ファイル単位の変更一覧（`git diff --stat` の転記）は書かない。読者が知りたいのは「何がどう変わったか」であって「どのファイルが変わったか」ではない
- 状態の前後は `.state-table`（反映前/反映後）、主張の対立・選択肢の比較は `.state-table.compare`（色で優劣を付けない。decision matrix は `.matrix` を足し採用列を最終列に置く）で表にする（テンプレート参照）。変わっていない・差のない項目は書かない
- 図は装飾しない。要素が 3 つ以上あり要素間の関係（依存・データの流れ・状態遷移）が主張の本体で、箇条書きだと同じ関係を文章で繰り返すときだけ使う。外部 JS 依存ゼロなので Mermaid は使わない — 3〜5 ステップならインライン SVG、それ以上は「1. → 2. → 3.」の番号付き箇条書きで表す。1 主張につき 1 図まで

## 手順

`SKILL=<skill_dir>` とする（この SKILL.md のある dir。dotfiles では `~/.agents/skills/reporting` が正本で `~/.claude/skills/reporting` はその symlink）。以下のコマンド中の `tools/...` はすべて `$SKILL/tools/...` を指す。

### a. 材料を集める

```bash
gh pr diff <番号>
# もしくは
git diff main...HEAD --stat
```

incident・research 型は diff ではなく調査結果・調査ノートが材料になる。ページ/領域（incident なら事象、research なら sub-question / テーマ）ごとにグルーピングする。UI があるなら「どの画面が変わったか」を route 単位で列挙する。

### b. 読者を決めて粒度を決める

「入力の決め方」節のとおり決める。決められない場合はユーザーに一度だけ確認する。

### c. UI がある場合: before/after を撮る

before = main（またはデプロイ済み）、after = branch。同じ URL 群を両方に流す。

1. 撮る前に `$SKILL/tools/anno.js` で注釈を入れる。selector / テキスト指定なので座標推定しない。`opts.number: true` で画像の①②…と箇条書きを対応させられる。full-page で撮るときは `opts.full: true` を渡す（既定は viewport 固定）。画面外の要素は `scrollIntoView` するか `opts.full` を使う。使い方は `$SKILL/tools/anno-example.md` を参照
2. [orca-cli](../orca-cli/SKILL.md) の version-matched browser guide を読み、Orca 内蔵 browser で撮る。下の `orca` は同 skill で解決した executable に置き換える。`spec.js` は手順1で作ったローカルの注釈コードを使う:
   ```bash
   shots_dir="$(pwd)/shots"
   mkdir -p "$shots_dir"
   orca exec --command "set viewport 1440 900" --json
   orca goto --url <url> --json
   orca eval --expression "$(cat spec.js)" --json
   orca exec --command "screenshot \"$shots_dir/<name>-before.png\"" --json
   ```
   複数タブで作業する場合は `orca tab list --json` から対象の `browserPageId` を取り、各呼び出しに `--page <browserPageId>` を付ける。別 browser が必要なら `agent-browser` skill の fallback 条件を確認してから切り替える。
   full-page は `orca exec --command "screenshot --full \"$shots_dir/<name>-before.png\"" --json` を使う。`orca exec` の保存先は絶対パスで指定する。
3. 撮ったら圧縮する: `cwebp -q 80 shots/<name>-before.png -o shots/<name>-before.webp`
4. before/after 双方に同じ流れを繰り返す

### d. `$SKILL/templates/report.html` を埋める

`$SKILL/templates/report.html` をコピーして書き換える。Section 単位 = 画面/領域（incident なら事象、research なら sub-question / テーマ）。Section 内 = 箇条書き → （UI があれば）before/after 画像ペア。非 UI の section は箇条書きだけでよい（テンプレート内の sec-2 / sec-3 / sec-4 の例を参照）。型ごとの構成は `references/change.md` / `references/incident.md` / `references/research.md` を参照。

### e. 画像を埋め込む

```bash
$SKILL/tools/embed.sh report.html
# → report.embedded.html を生成
```

### f. セルフチェック

- 全画像に注釈（赤枠 or 矢印）が入っているか
- 見出しが「何を変えたか・何がわかったか」の文になっているか
- 読者に不要な識別子（PR番号・commit・URL・作成者・作成日）が混ざっていないか（research 型の Sources と `[n]` 出典参照は除く）
- section の順序が読者の辿る順になっているか（レビュー回・日付順・調査した順になっていないか）
- 読者が認識できない粒度の変更が混ざっていないか
- 対象の型の `references/*.md` の構成に沿っているか。research 型なら末尾に「わからなかったこと」と Sources があるか、確度の低い finding に表記が付いているか

### g. 出力先

ユーザーの指示に従う。指示がなければ作業 repo 外に置く（`wwwyo/me` なら `daily/<today>/`）。公開してよいかは必ず確認する。

## 関連 skill

- `pr`: PR 作成。画像添付は[スクリーンショットの取得・添付手順](../pr/references/screenshots.md)を参照
- `japanese-tech-writing`: 本文の文章規範
