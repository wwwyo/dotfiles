# Project-local skill の導入

ステップ3で合意した技術スタックに紐づくskillを [skillctrl](../../skillctrl/SKILL.md) の手順で探索・追加する。プロジェクト固有のskillをローカルにインストールし、使う予定の agent 全部（claude / codex / pi）から使えるようにする。

#### 11.1. 候補探索（find）

合意済み tech stack の各キーワードについて `skillctrl` の探索・候補評価の手順に従い `skillctrl find <query>` で候補を取得する。インストール先は以下の 11.3 でセットアップ対象 repo を明示する。

```bash
skillctrl find shadcn
skillctrl find supabase
# ...合意したスタックぶん繰り返す
```

#### 11.2. ユーザー確認（HITL: 必須）

find の結果をそのまま install してはいけない。以下を1 skill ずつ表に整形してユーザーに提示し、明示的な承認を取る。


| 項目          | 内容                                                           |
| ----------- | ------------------------------------------------------------ |
| パッケージ名      | `<owner/repo@skill>`                                         |
| 説明          | find 結果の description（要約可）                                    |
| install 数   | 数値（例: 185K）                                                  |
| ソース         | owner（公式: `vercel-labs` / `anthropics` / `microsoft` 等は信頼度高） |
| install URL | `https://skills.sh/<owner/repo/skill>`                       |


提示フォーマット例:

```
以下を install しますか？

1. anthropics/skills@shadcn
   - shadcn/ui コンポーネント管理
   - 120K installs / source: anthropics（公式）
   - https://skills.sh/anthropics/skills/shadcn

2. vercel-labs/agent-skills@nextjs
   - Next.js best practices
   - 185K installs / source: vercel-labs（公式）
   - https://skills.sh/vercel-labs/agent-skills/nextjs

各 skill について y/n で回答してください。
```

ユーザーが y を返した skill のみ次のステップに進める。install 数 1K 未満 / 無名 owner はデフォルトで除外し、ユーザーが明示指定した場合のみ採用する。

#### 11.3. project-local skill インストール

承認された skill は、セットアップ対象 repo の `.agents/skills/<name>/` に実体を置く。tech stack に応じた skill の採用はそのプロジェクトの判断なので、dotfiles の共通 skill には追加しない。`skillctrl` は cwd の repo を対象にするので、対象 repo の clean worktree に `cd` して実行する。

対象 repo に `.agents/skills/` がなければ作成し、repo の承認済み commit 手順で clean にする。候補の `SKILL.md` と同梱ファイルを確認してから、名前を明示して取り込む。upstream の installer は実行しない。

CLI の JSON 結果に含まれる `repo` が実際の変更先なので、その worktree の差分・取得元・管理 lock（root の `skills-lock.json` と `.agents/skillctrl/upstreams.json`）を確認する。取得元と local skill の置き場を対象 repo の `AGENTS.md` の Skills 節に1行で記録する。Claude Code 用に `.claude/skills/<name>` → `../../.agents/skills/<name>` の相対 symlink を張る。codex・pi は `.agents/skills/` を直接読む。既存の skill や link がある場合は差分を確認する。

```bash
# cd into the approved target worktree, then import the named skill.
cd /absolute/path/to/project-worktree
skillctrl add owner/repo:chosen-name
```

#### 11.4. 導入確認

セットアップ対象 repo の `.agents/skills/<name>/SKILL.md`、必要な同梱ファイル、記録した取得元・commit SHA を確認する。`.claude/skills/<name>` の相対 symlink が、同じ repo の skill 実体へ解決されることも確認する。
