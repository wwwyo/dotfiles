# 学び skill をどう構造化するか

新しい学び skill を作る / 既存の学び skill の構造そのものを変える ときに読む。既存 skill にエントリを追記するだけなら読む必要はない（構造は既にあるため）。対象は repo に置いて session-consolidate が育てる学び skill で、dotfiles の汎用 skill（design-md / この skill 自体）は対象外。原型は [Vercel の product-design skill](https://vercel.com/blog/teaching-agents-product-design-at-vercel)。

## なぜ skill に置くのか

コードは *何が* ship されたかは示すが、*なぜ* そのパターンが標準になったか (rationale) は示さない。why は review・PR コメント・Slack・当時その場に居た人の中にあり、コードに無い文脈は agent にとって存在しない。だから accepted な決定を code と同じく repo に置き、変更をそれに照らしてレビューし、全 agent が読めるようにする。支えるのは3点セット＋任意の token 層:

- ① skill — 判断が要る文脈（rationale）
- ② lint — 決定論で自動強制できるルール
- ③ review loop — evidence を集め人間承認で反映
- ④ design.md — 視覚 token と基盤 component を書く視覚正本（product-design 型のみ・任意）。**repo root** に置き、agent はそれを読む。判断は skill の prose、再利用できる視覚値は design.md、機械判定は lint、と最も狭い場所に置く

構造の核は SKILL.md は知見を持たずルーターに徹し、知見の正本は `references/<topic>.md` に置くこと。必要な reference だけを読む — progressive disclosure の単位はやること (mode) であって行数ではない。

## skill の粒度と命名

学び skill は固定名ではない。扱うトピック・規模に応じたドメイン名を付ける（例: `coding` / `product` / `be-guideline` / `investigation`）。小さい repo なら1つ、育ってきたらドメインごとに分割してよい。

ただし、新規 skill は最後の手段。既存 skill の `references/` に自然に収まる運用ルールや、wiki / PROFILE / AGENTS で既にカバーされる判断基準は、新しい skill に分けない。1つの失敗例・1つの PR 由来の具体例だけで `product` / `wiki-ingest` のような広い名前の skill を作ると、発見性ではなく重複とレビュー負荷が増える。

新規に作るときは [templates/](../templates/) の型（product-design / guideline / investigation / qa-execution）から選ぶ。どれにも当てはまらなければ最も近い型を複製して mode（やること）を差し替える。型に無い領域を1件の学びで新設しない。

## レイアウト

```
<topic>/              # 例: coding, product, be-guideline
├── SKILL.md          # ルーター(runtime workflow): description(発火語) + Routing table(やること→reference) + 関連 skill
├── AGENTS.md         # skill 保守規約: load order / validation / governance(Review Loop)
├── CLAUDE.md         # `@AGENTS.md` の1行だけ（AGENTS.md を読まない agent への転送）
├── references/       # 知見の正本。1 reference = 1 やること(mode)
│   └── <topic>.md
└── tools/            # 決定論チェック (lint 等、任意)
```

- design.md（product-design 型・任意）— repo root に置く。[templates/product-design.md](../templates/product-design.md) の「値の層」を参照
- SKILL.md = ルーター — runtime workflow。本体は Routing table（`| やること | 読む reference |`）。知見を SKILL.md に溜めず参照先を指すだけにする。単独 reference にするまでも無い小トピックだけ短い inline section で持ってよい。frontmatter の `description` に「この repo で <トピック> を触るとき参照する」系の発火語を書き自動発火させる
- references/<topic>.md = 正本 — やること (mode) 単位で1ファイルに切り、そのファイルだけ読ませる。1 エントリ 1 行の bullet、事実・命令形。観測可能な決定として書く（「分かりやすく」等の形容詞ではなく「破壊的操作は Verb+Noun」のように検証可能に）。事実だけでなく rationale（なぜ。コードに残らないので特に重要）を残す。パス・コマンド付き、短命な PR/チケット番号は書かない（`#123` 裸書き禁止、必要なら `[owner/repo#123](url)`）
- 長い skill は読み落とされる — 追記・変更のたびに「もっとシンプルにできるか」を問う。新しい行を足す前に既存の行へ統合できないか、削れる記述が無いかを見る。SKILL.md や reference が伸びてきたら追記ではなく再整理を優先する
- skill 自身の AGENTS.md — この skill の load order・validation・governance を持つ（SKILL.md=runtime と分離）。`CLAUDE.md` は `@AGENTS.md` 1行だけで、読む index が違う agent に転送する。→「governance」
- tools/（任意）— 決定論で確実に判定でき、false positive が出ず、具体的 fix があるものだけ lint 化。判断が要る / 新しい標準の制定は reference + 人間へ。tool は reference の従属物で、矛盾したら reference 優先
- coverage gap — まだ標準の無い領域は「未確立」として明示しておく。推測で埋めない

## 配置と各ツール連携（初期構築時）

- symlink を張る — skill 本体は `.agents/skills/<topic>/` に置き、`.claude/skills/<topic>` から symlink する（codex・pi・devin は `.agents/skills/` を直接読むので symlink 不要。他ツールを使うならそこにも）。SKILL.md を直接各ツール配下に置かず、`.agents/skills/` を単一の正本にする
- team で管理している共有 repo の場合 — 個人の学び skill を team の repo に push しないよう、`_<topic>`（先頭 `_`）と命名し、共有 repo 側では gitignore する。正本は自分専用の dotagent repo に commit し、そこから共有 repo へ symlink（`_<topic>`）する — つまり「共有 repo では tracked にしない」だけで、個人 repo では version 管理される。自分専用 repo / ローカルなら通常名でよい。なお、チーム全体で共有すべき非自明な事実は、team 自身の guideline skill に PR で還元する（gitignored `_<topic>` は個人用の仮置き）

## governance（Review Loop）

skill 自身の AGENTS.md に還元の規約を書く。収集と判断を分ける: 作業中／週次で evidence（PR review・Figma・Slack・commit）をリンク付きで集める工程と、それを検証・グルーピングし open question を残す工程を分離する。自動化は review packet 止まり — reference / exemplar / lint rule / eval / design.md（視覚値の修正） / 変更なし のどれにするかは人間が決め、最も狭い該当ファイルに入れ、関連チェックを通してから merge する。推測で標準化しない。ルール化は evidence と承認を経てから、効かなくなったルールは外す。

## 起動時 index には 1行（いつ load するかの trigger）

repo の起動時 index は「いつこの skill を load するか」を agent に伝える trigger（skill 自身の AGENTS.md=保守規約 とは別物）。エージェントが起動時に無条件で読み込む index ファイルに、今回書き込んだ skill への参照が 1 行あることを保証する（無ければ追記）。どのファイルが起動時 index かは repo を見て判断する — `AGENTS.md` が基本、repo によっては `CLAUDE.md` / `CLAUDE.local.md` 等。学び skill を新設 or 追記したときはその skill への index を、既存のトピック skill に追記したときはその skill が自動発火するなら index 不要（発火語が description にある前提）:

```markdown
- 学び・ハマりどころ・過去の失敗は `.agents/skills/<topic>/`（session-consolidate が維持）を参照
```

旧運用の `## 学び・ハマりどころ` セクションが index ファイルに残っていたら、エントリを skill へ移設し、上の index 1 行に置き換える（移行）。

## リファインメント（自分が管理する学び skill のみ）

追記と同時に整理してよい。ただし触ってよいのは自分が管理する学び skill だけ:

- 重複・近接エントリの統合（情報と why を失わない）
- 陳腐化エントリの除去（根拠があるものだけ — このセッションで反証された / 現在のコードと矛盾。推測で消さない）
- reference が肥大したら やること 単位で分割し、SKILL.md の Routing table を更新

skill の分割・description 圧縮・reference の移動を行った後は、以下を監査する:

- 「上記」「このファイル」等の指示語と他 file への相互参照が、新しい配置でも意味を保つか
- 手順内で参照する節名・file 名・anchor が実在するか（dangling reference）
- frontmatter の description・本文の規範表現（必須・禁止）が圧縮で弱まっていないか
