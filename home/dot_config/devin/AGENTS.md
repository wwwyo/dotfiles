- ユーザーの意見に迎合しない。問題があれば率直に指摘する
- 判断する際はカウンターファクトとトレードオフを考える（「もしこの選択をしなかったら？」「別のアプローチだったら何が変わる？」）
- ツールはmiseで管理
- Cloudflare の操作は `cf` CLI を優先する。
- API key / token などの秘密は設定ファイルやリポジトリに平文で置かず、mise + age で管理する。詳細は secret-env skillを参照
- PoC の dev 環境のプロダクトから AI を呼ぶときは opencode を使う（key は mise の `OPENCODE_API_KEY`）。基本は安さ重視の open model を選び、扱うデータの責任範囲でモデルを分ける
- package install は supply chain リスクを避けるため、最新版を exact ピン留め（範囲指定 `^`/`~` は使わない）し、cooldown 7day を指定する。これは依存を「どう入れるか」の規則であって「入れない」ではない。定番ライブラリが解く問題を自前実装しない
- 汎用skillは `~/src/github.com/wwwyo/dotfiles/.agents/skills` で管理する。codex・pi・devin は `.agents/skills` を直接読み、Claude Code だけ `.claude/skills` から symlink で参照する
- skill や AGENTS.md に記述を足す・変えるときは常に「もっとシンプルにできるか」を考える。長いと読み落とされる — 新しい行を足す前に既存の行へ統合・削れないかを見る
- 対話的入力が要る作業でも、できる限り自分で回してから、人間の入力・承認が本当に必要な箇所だけを最小単位で handoff する。手順を丸ごとユーザーに渡さない。ユーザーにブラウザで開いてほしい URL は自分で `open` までやる

- 動画（demo・product launch・motion graphic）は `~/src/github.com/wwwyo/hyperframes`（HyperFrames の fork）を cwd にして `/hyperframes` skill から入る

- session 記録は Langfuse、長期記憶（semantic memory）は `~/src/github.com/wwwyo/me/wiki/` を SSOT とする。repo を問わず、タスクに関連する知識・PJ の文脈が要りそうなときは wiki skill を使って参照し、議論で新しい理解に到達したら同 skill で書き戻す
- 常に Orca を前提として動かす。worktree・terminal・file open・ブラウザ操作（Orca 内蔵ブラウザを `orca tab`/`goto`/`eval` 等で操作）など、Orca state が絡む・Orca で代替できる操作は `orca` CLI 経由にし、`git worktree` 直叩き・独自 PTY/tmux・agent-browser 等の別ブラウザを先に選ばない（詳細は orca-cli skill）
  - 通常の分担方法は agent の判断に任せる。別 repo での作業や独立したセッションが必要な場合は delegate skill を使う
- Orca の scheduled automation は `.agents/scheduled-tasks/*/automation.toml` が desired state（SSOT）
