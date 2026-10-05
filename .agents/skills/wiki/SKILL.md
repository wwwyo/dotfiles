---
name: wiki
description: "wwwyo/me の wiki/ から過去の学び・判断・PJ文脈を参照する。「以前まとめた話」「wikiから引いて」や /wiki で使う。議論でユーザーが到達した新しい理解は既存ページへ還元する。資料の転記・会話メモの保存は対象外。"
---

# Wiki

`wwwyo/me` の `wiki/` をどこの作業ディレクトリからでも参照するスキル。canonical は `~/src/github.com/wwwyo/me/wiki/`。

`wiki/` はユーザー自身が議論を通じて積み上げてきた知識ベース（OKF v0.1 準拠バンドル。frontmatter の `tags` 先頭＝domain と `type` で分類。dir は無意味な filing で分類には使わない）。別 repo で作業しているときも、過去の整理を引き当てて重複した議論や再発見を避けるために使う。

### 対象 checkout の解決

- **参照（読み）は canonical の `~/src/github.com/wwwyo/me` でよい**。ただし cwd が me の worktree 内なら uncommitted の変更を含むその checkout を読む（そちらが最新）
- **書き戻しは、merge に判断を要する変更なので作業中の worktree/branch に乗せる**。cwd が me の checkout 内ならその checkout に書き、そうでないときは canonical に書くか worktree を切る（規約の SSOT: `wwwyo/me/AGENTS.md`「このリポジトリを扱うときの注意」）

以下、このファイル内の `~/src/github.com/wwwyo/me` は上記解決の結果を指す。

## 守るべき制約

- 読みが基本、書きは条件付き。書けるのは「ユーザーが議論・学習セッションで自ら到達した理解・洞察」だけ。資料・教材・ドキュメントの転記は書かない（wiki はユーザーの合成知識であって scrapbook ではない）。書く前に必ず `~/src/github.com/wwwyo/me/wiki/AGENTS.md`（OKF バンドルの schema）を読み、その規約に従う
- 横断検索の入口は `tools/wiki_route.py route`。具体語での直接検索には `rg` も併用してよい。リンク関係には `tools/wiki_links.py` / `tools/wiki_route.py links`、orientation には root `index.md`（Map/Hubs）。個別ページを推測で開かない
- 答えは wiki の内容に根拠を置く。引用したページは必ず `~/src/github.com/wwwyo/me/wiki/<path>` 形式の絶対パス（または markdown リンク）で示し、ユーザーが現物を辿れるようにする
- 見つからないものを捏造しない。該当ページが無ければ「wiki に該当エントリなし」と伝え、必要なら `wwwyo/me` セッションで新規作成を提案する

## 探し方

分類は2軸: domain（`tags` 先頭）× `type`。dir は browse 用の filing に過ぎず分類の根拠にしない（domain は必ず `tags` で判定する）。

自然文の問いはまず router を叩く（`index.md` を読んで Map → domain index と辿るのは 1 回 2〜3 万 token・20 秒超かかる。router は数百 token・1 秒未満で当たりを絞れる）:

```bash
python3 <このスキルのbase directory>/tools/wiki_route.py route "エージェントに任せるかの判断は検証のしやすさで決まるって具体的にどういうこと？" --json
```

上位 5 件（`results`）の本文を実際に開いて確かめる。上位が外れていたら `~/src/github.com/wwwyo/me/wiki/index.md`（`## Map` = 各 domain index / `## Hubs` = 主要入口）から Map → domain index → ページの順に絞る fallback へ切り替える。TypeSafe（Jev）が使えないときは自動で bigram（文字 bigram TF-IDF）に落ちる（`router` フィールドで判別、exit code は変わらず 0）。具体的な語がすでに分かっているクエリは `rg` で直接検索してよい。

`route` の問いと `links` の対象ページ本文は TypeSafe（外部 API）へ送られうる。`.local` ページを対象にした `links` と `--local-only` を指定した実行は常に bigram のみ（外部 API に送らず、log にも残さない）。cwd による自動の送信抑止はない。問いに業務・顧客の固有名（案件名・顧客名・人名等）が入る場合は `--local-only` を付けるか、固有名を抜いた一般的な問いにする。

被リンク（backlinks）だけは `rg` で手動追跡すると取りこぼしやすい（`AGENTS.md` のような予約 meta ファイルからの参照を見落としがち）。knowledge graph として辿るときは専用ツールを使う:

```bash
python3 <このスキルのbase directory>/tools/wiki_links.py /tech/ontology.md --json
```

Outbound（バンドル外は `(external)`、リンク切れは `(broken)`）と Backlinks を両方出す。exit code は rg 互換。

## 書き戻す（新しい理解・洞察が生まれたときだけ）

議論や学習セッションでユーザーが新しい理解に到達したら、wiki に書き戻す。手順:

PJ も wiki で管理している。1 PJ = 1 domain（`wiki/<pj>/`）で、状態・意思決定 log がそこに載る。非公開の PJ ページは `*.local.md` に分ける。議論が進行中の PJ に関わるなら、一般知識のページだけでなく該当 PJ ページの意思決定 log と「位置づけ（自分の読み）」も更新する（決まったことを newest-first で1-2行 + link。経緯の物語は書かない）。規約は `wiki/AGENTS.md`「PJ ページのメンテナンス規約」、全体方針は `wiki/life/project-focus.md`。どの PJ が動いているかは `wiki/index.md` の Map から辿る。

1. `~/src/github.com/wwwyo/me/wiki/AGENTS.md` を読む（frontmatter 規約・書き込み後の必須作業がここにある）
2. 既存ページを確認（`rg` で重複を先に当てる）— 同じトピックのページがあれば新規作成ではなく更新。浅い・古い記述を見つけたら今回の理解で refine する
3. 書く内容はユーザーが自分の言葉で到達した理解（学習セッションならフリーリコールや転移課題の答えが素材）。教材・資料の要約転記はしない。frontmatter の `description` に YAML の `: ` を含むなら全体を double quote する
   - `daily/<date>/memo.md` の一節を切り出すとき、対象見出しから「ファイル末尾まで」を機械的に取らない。同じ日の memo.md には別セッションが後から無関係な節を追記していることがあり、末尾まで取ると混入する。対象見出しから**次の見出し直前まで**で区切る
4. AGENTS.md の書き込み後チェックを実行: domain の `index.md` 更新 → `log.md` 追記 → 関連ページと相互リンク（`wiki_links.py` で backlink 候補を確認。`python3 <このスキルのbase directory>/tools/wiki_route.py links <page> --json` でリンク候補を出してもよい。候補はあくまで提案で、貼るかどうかは本文を読んで判断する）
5. 検証: `cd ~/src/github.com/wwwyo/me && python3 .agents/skills/wiki-lint/tools/okf_check.py wiki`
6. 報告前に `git diff -- <更新ファイル>` と実ファイルの該当箇所を読み直し、意図した内容が保存されていること、重複・破損がないことを確認する。ツール応答が途切れた後は特に、保存済みとみなして報告しない
7. 書いた/更新したページのパスと要旨をユーザーに報告する。commit はユーザーの指示があるときだけ

`daily/<today>/memo.md` から特定の議論を wiki ページへ切り出すとき、「その見出しから末尾まで」を丸ごと移す抽出はしない。`memo.md` は複数セッションが同時に追記する共有ファイルで、自分が編集している間に別セッションが同じファイルの末尾へ別トピックを追記することがある。見出し〜EOF で切り出すと、後から着いた無関係なセクションを巻き込んで wiki ページに混入する。移す範囲は次の `---` 区切り（または次の `## HH:MM` 見出し）までに明示的に限定し、切り出し後は `git diff -- daily/<today>/memo.md` で自分の対象範囲だけが削られたことを確認する。

## エッジケース

- `~/src/github.com/wwwyo/me` が存在しない — `wwwyo/me リポジトリが見つかりません` と返して終了
- 該当ページが無い（言い換えても index を辿ってもゼロ）— 「wiki に該当エントリなし」と伝える。会話の中で新しい理解が生まれているなら上の手順で新規ページを作る。単なる参照要求なら `wwwyo/me` で `/memo` → 議論 → wiki 化の流れを提案する
- 複数の syntheses が重なる — どれを優先すべきかユーザーに 1 回だけ確認する（例: 「data-platform 系と FDE 系どちらの観点？」）
- bundle root が標準と違う — `wiki_links.py --root <path>` で差し替えられる（default: `~/src/github.com/wwwyo/me/wiki`）
