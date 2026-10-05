# PR のスクリーンショット

ローカルのスクリーンショット/画像を GitHub PR にアップロードし、body またはコメントに埋め込む手順。

## CLI からの添付

GitHub.com で repo の write 権限があり、GitHub CLI が v2.99.0 以降なら `gh pr edit --attach` を使う。添付のためのブラウザ操作は不要。画像を複数渡す場合は `--attach` を繰り返す。

```bash
gh pr edit <PR_URL> --attach /tmp/before.png --attach /tmp/after.png
```

所定位置に埋め込む場合は、既存 body を保存し、必要なら任意の`## Screenshots / Videos`節を追加して、`![before](/tmp/before.png)`のようなローカルパスの参照を挿入してから添付する。本文中の参照はアップロード先の URL に書き換わり、参照しなかった添付は末尾に追加される。

```bash
gh pr view <PR_URL> --json body -q .body > /tmp/pr-body.md
# /tmp/pr-body.md の Screenshots / Videos に画像のローカルパスを挿入
gh pr edit <PR_URL> --body-file /tmp/pr-body.md --attach /tmp/before.png --attach /tmp/after.png
```

実行後は body にアップロード先の参照が入り、PR ページで画像が表示されることを確認する。添付が一部だけ成功して非ゼロで終了する場合もあるため、再実行前に body を確認する。

旧 CLI、GitHub Enterprise Server、その他 CLI 添付を利用できない環境では、以下のブラウザ手順を使う。

## ブラウザからの添付（fallback）

### 仕組みと制約

ブラウザ手順は PR のコメント textarea を staging に使い、そこに画像をアップロードして `user-attachments/assets/<UUID>` 形式の永続 URL を発行させ、コメントは送信せずにその参照だけを取り出して `gh pr edit` で body に埋め込む。現行 GitHub は textarea に `<img width=.. height=.. src="https://github.com/user-attachments/assets/<UUID>" />`（環境により `![](...)` markdown）の形で注入する。

- 対象 PR が既に存在している必要がある（textarea を staging に使うため）。未作成なら先に `gh pr create` する。
- URL はコメントを送信しなくても永続する。
- private repo でも動く（user-attachments は repo アクセス権ベースで配信される）。
- browser 自動化が必要なため CI 環境では動かない（ローカルで人が回す前提）。

### 前提

- この手順では `agent-browser` が既定（他の skill は agent の内蔵ブラウザ — Claude Code のブラウザパネルや Orca 内蔵ブラウザ — を優先する）。理由は 2 つ: 内蔵ブラウザにファイルアップロード手段が無いこと、Claude の `computer {action: "screenshot"}` が任意のパスに書き出せないこと。agent-browser は `upload <sel> <files>` を持ち、`screenshot [path]` が任意のパスに書き出せるので、どちらも解決する。
- GitHub のログイン状態は `--profile <name>` で継承する（`--session` は独立セッションでログインを継承しない）。プロファイル名は `agent-browser profiles` で確認する。auth state の保存・読込は不要。`meta[name=user-login]` が自分の login を返せばログイン済み（private repo は未ログインだと 404 "Page not found"）。
- 継承されるのは個人アカウントのみ。仕事アカウントの private repo には入れない。
- アップロードする画像はローカルに絶対パスで用意する。特殊文字（CleanShot の Unicode narrow space 等）を含むパスは単純名でコピーしてから渡す。
- GitHub の UI は変わりうるので selector は複数試す。
- 複数コマンドにまたがる複雑な JS は `agent-browser eval --stdin` にヒアドキュメントで渡す。

### 手順

### 0. 対象 PR を特定する

PR 番号/URL が指定されていなければ現在のブランチから取得する。

```bash
gh pr view --json number,url -q '"\(.number) \(.url)"'
```

### 1. (任意) スクリーンショットを撮る

フロントエンド画面のスクショが必要なら agent-browser で撮る。`screenshot [path]` は任意のパスに書き出せる。dev server が起動していなければユーザーに手動取得を依頼し、ローカルの絶対パスを受け取る。

```bash
export AGENT_BROWSER_SESSION="$(agent-browser session id --scope worktree --prefix pr-screenshot)"
agent-browser --profile <name> open '<dev-server-url>'
agent-browser wait --load networkidle
agent-browser screenshot /tmp/pr-screenshot-1.png
```

画面幅を厳密に合わせる場合は、ページを開く前に viewport を直接指定する。

```bash
agent-browser set viewport 1280 800
```

### 2〜6. PR ページを開いてアップロードし、参照を取り出す

```bash
agent-browser --profile <name> open '<PR_URL>'

# ログイン確認。private repo は未ログインだと 404 になる
LOGIN=$(agent-browser eval "document.querySelector('meta[name=\"user-login\"]')?.content || null")
[ "$LOGIN" = "null" ] && { echo NOT_LOGGED_IN; exit 1; }

# file input を特定する。GitHub は display:none で隠しているので unhide しないと掴めない
cat <<'EOF' | agent-browser eval --stdin
(() => {
  const sel = ['input[type=file][id*=comment]', 'input[type=file]']
    .find((s) => document.querySelector(s))
  if (!sel) return 'NO_FILE_INPUT'
  const el = document.querySelector(sel)
  el.style.setProperty('display', 'block', 'important')
  el.style.setProperty('visibility', 'visible', 'important')
  el.style.setProperty('opacity', '1', 'important')
  return sel
})()
EOF

agent-browser upload "input[type=file]" /tmp/pr-screenshot-1.png

# GitHub が textarea に参照を注入するまで待つ
agent-browser wait --fn "!(document.getElementById('new_comment_field') || document.querySelector('textarea[id*=comment]'))?.value?.includes('Uploading')"
VALUE=$(agent-browser eval "(document.getElementById('new_comment_field') || document.querySelector('textarea[id*=comment]'))?.value")
echo "$VALUE"

# staging に使っただけなので textarea は空に戻す（コメントは送信しない）
agent-browser eval "(() => { const t = document.getElementById('new_comment_field') || document.querySelector('textarea[id*=comment]'); if (t) t.value = '' })()"
```

複数枚あるときは `upload` と待機のブロックを画像の数だけ繰り返す。

selector が見つからない場合は unhide が別要素に当たっているか、input が再生成されている。実際の DOM を見て selector を取り直す。

```bash
agent-browser eval "document.querySelector('form[id*=comment]')?.outerHTML.slice(0, 2000)"
```

### 7. body またはコメントに埋め込む

body に埋め込む場合（既存 body を取得 → 所定位置に挿入 → `--body-file` で更新）:

```bash
gh pr view <PR_NUMBER> --json body -q .body > /tmp/pr-body.md
# /tmp/pr-body.md の所定位置（例: `## Screenshots / Videos` 直下）に画像 markdown を挿入
gh pr edit <PR_NUMBER> --body-file /tmp/pr-body.md
```

コメントとして投稿する場合:

```bash
gh pr comment <PR_NUMBER> --body "## Screenshots

![screenshot](https://github.com/user-attachments/assets/...)"
```

表示幅を抑えたい場合は、注入された `<img>` の `width`（Retina スクショだと実寸の 2 倍になることがある）を `800` 程度に書き換える。markdown 形式で注入された場合は `<img width="800" alt="..." src="..." />` に置き換える。

### 8. 確認

PR ページをリロードして画像が表示されることを確認する。使い回した `agent-browser` session がそのまま使える。

```bash
agent-browser open '<PR_URL>'
agent-browser wait --load networkidle
agent-browser eval "[...document.querySelectorAll('.markdown-body img')].map(i => i.naturalWidth).join(',')"
# → "800" 等、naturalWidth > 0 の並びが返れば表示されている（0 だけなら画像が壊れている）
```

### 注意点

- `gh` コマンドは sandbox 外で実行する（TLS 証明書検証の制約回避）。
- コメントは送信しない（textarea を staging に使うだけ）。誤って送信した場合はそのコメントを削除する。
- 作業が終わったら `agent-browser close` でセッションを閉じる。
- selector が見つからない / textarea に URL が出ない場合は、待機を延ばして再試行する。GitHub の UI 変更時は selector を更新する。
- body 表示時、GitHub は `user-attachments` URL を署名付き URL（`private-user-images.githubusercontent.com/...`）にリライトして表示するが、body のソースは元 URL のまま・永続する。表示確認は画像要素の `naturalWidth > 0` で判定するとよい。

## 参考

- [GitHub CLI のメディア添付](https://github.blog/changelog/2026-09-01-github-cli-media-in-issues-pull-requests-and-comments/) — 対応バージョン・権限・GitHub Enterprise Server の制約
- [gh pr edit](https://cli.github.com/manual/gh_pr_edit) — `--attach` と本文中のローカルパスの扱い
- [tonkotsuboy/github-upload-image-to-pr](https://github.com/tonkotsuboy/github-upload-image-to-pr) — 同じ staging 方式の AI エージェント skill
