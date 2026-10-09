---
name: project-setup
description: "新しいプロジェクトやリポジトリの作成・初期化を依頼されたときに使う。「project setup」「プロジェクトを作って」「新しいリポジトリを作成」など。"
argument-hint: <project-name>
---
# Project Setup

新しいプロジェクトを初期化し、開発に必要な基盤ファイルを生成する。AI エージェントは Claude Code・Codex・pi・Devin を使う前提で構成する。

## 外部 OSS を fork する場合

外部 OSS の fork では、upstream へ contribute する差分に個人用の setup が混ざらないよう、**main を upstream の対応ブランチと同じ commit に保つ**。setup 用の commit は作らず、開発・contribution は main から別ブランチを切って行う。

upstream を維持するだけで自分では開発しない fork（mirror・参照用）は、このワークフロー自体を適用しない — ローカル設定さえ不要なら setup なしで終える判断も正しい。

この場合は、以下の通常ワークフローより本節を優先し、**setup は Git の差分に出ないローカル設定だけ**に限定する。

- upstream の構成・開発手順をそのまま使い、既存の tracked file を変更しない。`AGENTS.md`・`CLAUDE.md`・README・`mise.toml`・`.gitignore`・workflow の生成や上書き、依存関係・lockfile の変更は行わない。
- 個人用の設定が必要なら、既存の ignore 対象のローカル設定、`.git/info/exclude`、repo 外の設定を使う。tracked file の変更を `assume-unchanged` / `skip-worktree` で隠す方法は使わない。
- tracked file の追加・変更や commit が必要なステップはスキップし、理由を完了報告に記す。fork に新規 repo 向けの初期化・設定を一律に適用しない。
- 完了時に main と upstream の対応ブランチの commit が一致し、setup による tracked file の差分や未追跡ファイルが `git status --short` に出ていないことを確認する。作業開始前からあるユーザーの変更は保持する。

## ワークフロー

開始時に、以下の全ステップを含む todo list を作る。agent にタスク管理ツールがあればそれを使い、なければチェックリストで示す。進行に合わせて更新し、条件付きのステップは適用の有無が決まった時点で反映する。完了時に未完了項目がないか確認する。

引数 `$ARGUMENTS` をプロジェクト名として使用する。未指定ならユーザーに確認する。

### 1. リポジトリ作成

ghq 管理下にリポジトリを作成する。既にディレクトリがあればスキップ。
デフォルトのGitHubオーナーは `wwwyo`。引数が `owner/repo` 形式ならそちらを優先する。

```bash
# $ARGUMENTS が "owner/repo" 形式ならそのまま、"repo" のみなら "wwwyo/repo" として扱う
ghq create github.com/wwwyo/$ARGUMENTS   # repo名のみの場合
# ghq create github.com/<owner>/$ARGUMENTS  # owner/repo形式の場合はユーザー指定のownerを使う
cd "$(ghq root)/github.com/wwwyo/$ARGUMENTS"
```

### 2. git init

```bash
git init
```

### 3. 技術スタック確認

以降の `mise.toml` / `.gitignore` / `AGENTS.md` を整合させるため、最初にユーザーへ技術スタックを確認する。

- 言語・ランタイム（例: Node.js, Bun, Go, Python, Rust）
- パッケージマネージャ（例: pnpm, bun, uv）
- 主要FW・ライブラリ（任意）
- **対象オーディエンス・言語**（海外向け・英語圏も対象にするなら README・AGENTS.md などの公開向けドキュメントは英語で書く。日本国内向け・個人用途なら日本語でよい。ステップ 8・10 の生成言語をここで決める）
- **Langfuse に agent session の trace を収集するか**（yes ならステップ 5 で全 agent 分を opt-in。プロンプトと tool 入出力 = コード内容が外部 SaaS に送られるため、機密を扱う repo では no のままにする）
- **Pullfrog（PR review・agent 自動化）を導入するか**（yes ならステップ 13 で App install・workflow・repo-level config まで設定して動く状態にする）
- **プロジェクト固有のドキュメントを置く dir**（`docs/` = チーム共有で tracked、`.agent/` = gitignore される個人メモ。ステップ 8 のディレクトリ構造に最初から描く）

あわせて repo の種別を決める。依頼や repo 名から読み取れるなら聞かない。

- **product**: 1 つのプロダクトを育てる repo。以降は各ステップの既定どおり
- **playground**: API・model・ライブラリを試す PoC を複数置く repo。ステップ 8 で [playground の場合](#playground-の場合) の規約を入れる

### 4. mise.toml 生成

ツールはすべて mise で管理する（グローバル方針）。ヒアリングしたランタイム / パッケージマネージャを `[tools]` セクションに列挙する。
バージョンは exact ピン留め + 7日 cooldown で固定する（グローバルの supply-chain 方針に合わせ、`latest` の moving target と公開直後の版の両方を避ける）。

- `--pin`: 最新版を install しつつ解決された具体バージョンを mise.toml に記録する（付けないと `latest` の文字列が書かれる）
- `--before 7d`: 公開後 7 日以上経過したバージョンのみを対象にする

### 5. Langfuse telemetry opt-in（収集する場合のみ）

既存 repo の監査・修正では、`orca.yaml` の scripts・Langfuse 設定が新規 worktree へ伝播するかも完了条件に含める。既存の設定値を不具合と断定する前に意図的な設定でないか確認する（`--setup skip` の免除条件は [telemetry 手順](references/telemetry.md) が正本）。

ステップ 3 で収集を選んだ場合は、[導入手順](references/telemetry.md) を読み、4 agent の opt-in と Orca worktree への設定同期を行う。

### 6. パッケージマネージャーピン留め

グローバル方針（exact ピン留め + cooldown 7day）をパッケージマネージャ設定(ex. .npmrc, bunfig.toml)に反映する。

### 7. .gitignore 生成

プロジェクトの技術スタックに応じた内容を生成する。最低限以下を含む:

```
node_modules/
.DS_Store
.env
.env.local
*.log
```

ヒアリング済みスタックに応じてエントリを追加する（例: Go なら `vendor/`、Python なら `__pycache__/` `*.pyc` `.venv/` など）。

### 8. AGENTS.md 生成

プロジェクトの概要と構造を記述する。テンプレートは `document` skill の `assets/agents-md.md`、書き方の規約は `references/agents-md.md` に従う（Story の要否判定は `prd` skill の `references/story-format.md`）。ステップ 3 で確認したスタックと、選んだ `docs/` or `.agent/` をツリーに反映する。

#### playground の場合

Story 節は省き、冒頭に「何を試す場所か」と「何が分かれば採否を決められるか」を 1〜2 文で書く。ディレクトリ構造には、PoC ごとにコードと docs を同名の dir で切る規約を書く。

```
<repo>/
├── <poc>/           PoC ごとのコード
└── docs/<poc>/      その PoC で何を作り何を確かめるか
```

repo を public にするなら、手元のデータ（他 repo の中身・個人データ）は tracked なファイルに入れず、実行時に path を env で受けて読む。そのデータを含む生成物は gitignore する。

### 9. CLAUDE.md 生成（AGENTS.md を読まない agent への転送）

```markdown
read @AGENTS.md
```

この1行のみ。起動時 index は `AGENTS.md` が正本で、CLAUDE.md はそれを読まない agent（Claude Code 等）への転送役。Devin は AGENTS.md と CLAUDE.md を両方読むので内容の重複を避けるため転送1行に留める。

### 10. README.md 生成

`document` skill の `assets/readme.md` と `references/readme.md` を読み、その構成と規約に従って簡潔に書く。ステップ 3 で決めた基準言語を反映し、英語基準なら日本語版の `docs/README.ja.md` と冒頭の相互リンクも作る。AI agent への導入委譲を想定する製品なら、`references/readme.md` の「AI agent に導入を任せる製品」に従って `docs/start.md` と README の導入 prompt もここで作る。

ライセンスが未確定なら License 節とバッジは下書きに留め、ステップ 12 で採用条件が決まってから仕上げる。

product・公開 PJ では**ロゴ・ワードマークを独立した完了項目**として扱う — README 規約への間接参照だけでは抜けやすい。作る場合は [design-md](../design-md/SKILL.md) の Logo 作成フロー（symbol → 人間選択 → wordmark → 字間調整）に従う。

### 11. tech stack に合わせた skill 追加

[導入手順](references/project-skills.md) に従い、合意した技術スタックの skill を探す。ユーザーが承認したものだけを対象 repo に配置し、Claude 用の相対 symlink と取得元・commit SHA の記録を残す。

#### e2e 初期化（ブラウザ・モバイル UI がある場合）

[e2e skill](../e2e/SKILL.md) の導入手順（[OpenCode Go setup](../e2e/references/opencode-go.md)）に従う。`e2e init` は対話 terminal が必須で非対話 session では実行できず、`--yes` は Vercel 既定・共通 skill・MCP 登録を強制するため使わない。

[config template](../e2e/assets/e2e.config.ts) を repo root にコピーし、URL・起動コマンドを対象アプリに合わせる。依存関係は対象 repo の package manager で導入し、ステップ 6 の exact pin・cooldown に従う。`test:e2e` script と `.e2e/` の gitignore を加え、config・テストの雛形を初回 commit に含める。

### 12. GitHub リポジトリ作成

ユーザーに public / private を確認してから実行する。**public を選んだ場合は LICENSE を入れるかも確認する**（入れるなら license の種類も。迷ったら MIT。private なら不要）。入れる場合は `git add -A` 前にファイルとして生成して初回 commit に含める（`gh repo create --license` は `--source`/`--push` と併用できないため）。key 一覧は `gh api licenses --jq '.[].key'`:

```bash
body=$(gh api licenses/<key> --jq .body) && printf '%s\n' "$body" > LICENSE
# 生成物を開き、著作権 placeholder（[year]/[fullname]/<year>/<name of author> 等。形式は license ごとに違う）を埋める
# ※ GPL/AGPL 系の本文には <https://fsf.org/> のような角括弧付き URL が混ざっているのでそれは触らない
```

初回 commit 前に、確定したライセンスと生成した `LICENSE` に合わせて `README.md` と、あれば `docs/README.ja.md` の License 節・バッジを更新する。ライセンスを採用しない場合は節とバッジを省き、両版のリンクと未置換のプレースホルダーが残っていないことも確認する。

```bash
git add -A
git commit -m "init: project setup"
gh repo create wwwyo/$ARGUMENTS --source . --push
gh repo edit --delete-branch-on-merge
```

`--public` か `--private` はユーザーの回答に従う。

`--delete-branch-on-merge`（merge 時に head branch を自動削除する "Automatically delete head branches"）は repo 単位の設定。

#### 12.1. 公開範囲に応じたセキュリティ設定

初回 push 後、[設定手順](references/github-security.md) に従って GitHub 上の visibility に応じた項目を有効化する。

#### 12.2. Dependabot の定期更新（public の場合のみ）

`.github/dependabot.yml`（`version: 2`）を生成する。実際の manifest・lock file に合わせて `updates` の ecosystem・directory を選び、各対象に `schedule.interval: weekly` と `cooldown.default-days: 7` を設定する。ステップ 13 で導入する workflow も含め、GitHub Actions を使う場合は `github-actions`（`directory: "/"`）を加える。[対応する設定値](https://docs.github.com/en/code-security/reference/supply-chain-security/dependabot-options-reference#package-ecosystem) を参照する。

生成した設定をデフォルトブランチへ commit・push する。更新対象の manifest・workflow がまだなければ、初回追加時に `dependabot.yml` を作成・追記するようステップ 15 の handoff に含める。

lockfile を commit する JS/TS の package manager（bun / npm / pnpm / yarn）を使う場合は、Dependabot が lockfile 未追従の PR を作ったときに自動修復する workflow も生成する。背景・`pull_request_target` が必要な理由・雛形は [references/dependabot-lockfile.md](references/dependabot-lockfile.md) に従う。

### 13. Pullfrog 導入（yes の場合のみ）

ステップ 3 で導入を選んだ場合は、repo 作成・visibility 確定後に [導入手順](references/pullfrog.md) を読む。App・workflow・repo-level config を設定し、実際の PR で動作確認して commit・push する。 完了条件には Pullfrog 実効値の監査（`pullfrog config list --repo` と `--org` の両方で継承込みの値を確認）と直近レビュー言語の確認を含める。

### 14. wiki に PJ domain を作成（継続して育てる PJ の場合のみ）

立ち上げた PJ は `wwwyo/me` の wiki に記憶を持たせる。**setup の必須完了項目**として抜けずに実施し、失敗したまま終わらせない。規約の SSOT は `~/src/github.com/wwwyo/me/wiki/AGENTS.md`（「PJ ページのメンテナンス規約」「プロジェクト記憶も wiki で管理する」の項）。これは wiki skill の書き込み条件（議論で到達した理解のみ）に対する例外で、PJ の台帳としての状態同期にあたる。単発 task・playground 内の使い捨て PoC は PJ ではないので作らない — playground repo 自体を継続運用するなら repo 単位で 1 domain を作る。**対象は個人 PJ のみ** — ステップ 1 で確定した owner が `wwwyo` 以外（仕事の org repo 等）ならこの手順は対象外。

- `~/src/github.com/wwwyo/me/wiki/<pj>/` に dir + `index.md` + hub ページ `<pj>.md` を作る。OKF frontmatter は **hub ページだけ**に付ける（`tags` 先頭は PJ domain 名。`index.md` は予約 meta で frontmatter を持たず、付けても無視される）。`<pj>/index.md` には `* [title](<pj>.md) - description` 形式で hub のエントリを置き、hub ページには repo リンク・Phase・「何であるか」の1段落を書く
- `~/src/github.com/wwwyo/me/.agents/skills/wiki-lint/tools/okf_check.py` の `ALLOWED_DOMAINS` に PJ domain を追記
- `wiki/index.md` の Map に domain index への link を足し、`wiki/log.md` に Creation エントリを追記
- `wiki/life/project-focus.md` の PJ 一覧・フォーカスに反映する
- `wiki` skill に従って検証し、`wwwyo/me` の `AGENTS.md` の checkout 規約に従って、この PJ 登録で変更したファイルだけを stage・commit・push する。push の成功までをステップ 14 の完了条件とする

### 15. 最初の PRD へ handoff

setup 完了後、作成した repo を作業ディレクトリとする agent session へ handoff し、最初の `prd` skill を実行する。`delegate` skill の共通設定と `orca-cli` skill の Full Handoffs に従う。

- 引き継ぎ prompt に、対象 repo の絶対パス・GitHub URL・合意済みの目的と tech stack・選んだ `docs/` or `.agent/`・setup の完了状況を含める。wiki の PJ ページを作成した場合はその参照先も渡す
- 対象 repo の `AGENTS.md` と `prd` skill を読み、最初の機能のヒアリングから PRD 作成を進めるよう依頼する。最初に扱う機能が未定なら、その確認から始める。playground の場合は最初に取り組む PoC を対象にする
- handoff の送信と引き継ぎ先のターン開始を確認し、repo・session の参照先をユーザーへ報告する。todo list の最終項目は、この開始確認で完了にする

## 完了報告の表現

報告では成果物の状態を「merge 済み / PR 作成中 / ローカル（未 push）」で区別して書く。「できた」の一言に圧縮すると、未 merge の作業が完了済みに見えて引き継ぎ先が見落とす。
