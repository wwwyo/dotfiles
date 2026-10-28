---
name: cleanup
description: 3日ごと、閾値を超えたキャッシュ・使っていない mise install・不要になった git worktree / branch / agent workspace の残骸を掃除する
---

ローカル環境の掃除。sandbox 外（`dangerouslyDisableSandbox: true`）で実行する。

全ステップが閾値ゲート付きで、**何も消さず freed 0MB で終わるのが正常な結果**。異常は exit code 1 と `failed:` 行で表現される。閾値を下げたり強制クリーンを実行したりせず、結果をそのまま報告する。

## 1. キャッシュ

`mise clean-cache` を実行する。各キャッシュが閾値（go modcache / buildcache / uv 5GB、bun / npm 2GB、container image 3GB）を超えたときだけ削除し、未満なら skip する。**使っていない mise install**（どの tracked config からも選ばれず、tracked stub も使っていない tool version。実行中 process の起動元 version は残る）は `mise prune` で毎回消す。閾値は無く、消しても再取得で戻せるので常時実行する。残っていないかは `mise ls --prunable` で確認できる（stub や実行中 process が参照している分は残るので、空にならないこともある）。uv cache は他の uv process が lock を持っていれば skip する（`--force` で奪わない）。`simctl unavailable`（未参照 simulator の削除）は full Xcode＋simulator runtime が無い環境では `skip (simctl なし…)` 表示になり、`failed:` や exit 1 にはならない — Xcode 不在は閾値判定と無関係な恒常的な環境要因なので異常に数えない。

cleanup の対象外だが、手動で「storage を空けて」と頼まれて消すときは次を消さない。`~/.rustup` は mise 管理 rust の本体を兼ねる — 丸ごと削除すると cargo/rustc が動かなくなる。古い版は、削除前に各プロジェクトで `rustup show` を確認し、`rust-toolchain` / `rust-toolchain.toml` や directory override が対象版を選んでいないことを確かめてから `rustup toolchain uninstall <版>` で版単位に消す（`cargo --version` だけではプロジェクト固有の指定を検出できない）。`~/.codex` は `auth.json`・`config.toml` を含み、消すとログイン・設定が飛ぶ — 容量の大半は `sessions/` なのでそこだけを消す。

## 2. git worktree / branch

対象は `~/src/github.com/wwwyo/`・`~/src/github.com/fudoki-hensansitu/` 配下の個人 repo と、agent の workspace 置き場（`~/orca/workspaces/`・`~/.codex/worktrees/`）。移管後も旧ディレクトリにある checkout を含む。workspace 置き場は repo を消しても dir が残るので、repo 走査とは別に単独でも見る（下の「workspace 置き場の残骸」）。**GitHub で archived 済みの repo は対象外** — 新しい merge も fetch 成功も起きないので、走査すると毎回 fetch 失敗のノイズになる。`gh repo view <name> --json isArchived -q .isArchived` で確認する。

各 repo で順に:

```bash
git fetch -q origin && git remote prune origin
git worktree prune                      # 実体が消えた登録を落とす
git worktree list                       # 残ったものを点検
```

`git fetch` が失敗したら「remote が無い」と即断しない。https remote + credential helper の破損では fetch/ls-remote が恒常的に使えないが、`gh api repos/{owner}/{repo}`（`/branches/<branch>` で head 照合）や `gh pr list` で remote 実状態は取れる。検証コマンドがその dir でエラーになるときは、別の cwd か `gh api` で再確認してから判定する（dir 内の `gh` 失敗で MERGED PR を見落とした実例あり）。認証不通が恒常化している repo は上の archived 疑いで対象外を検討する。

fetch が失敗した repo では、API 照合は `origin/main` / `origin/<branch>` の local remote-tracking ref を更新しない — 下の削除判定は古い ref を見る。判定に使う remote ref の SHA が `gh api` で取れる現在の head と一致することを確認できるまで branch は消さず、一致を確認できなければ branch を残して `git gc --prune=now` も skip し、fetch 失敗と照合不可を報告に載せる。

macOS 標準には `timeout` コマンドが無い（GNU coreutils 由来）。`git fetch` 等を timeout 付きにしたくても素の `timeout 60 git fetch` は command not found で空振りする。timeout なしでそのまま実行するか、`gtimeout`（coreutils）が入っている前提を確認してから使う。また `git worktree list` 等の出力を `| head` で切ると、行数がパイプのバッファ待ちで固まることがある。件数を絞りたいときはパイプせず、そのままの出力を読むかファイルへ書き出す。

**worktree の削除**: `git worktree list` の各 worktree について、中身と最終更新の2つを見る。

```bash
git -C <path> status --short --untracked-files=all
cutoff=$(date -v-30d +%Y-%m-%d)   # find は bfs 実装なので相対表現は通らない。ISO 8601 を渡す
find <path> -type f -not -path '*/.git/*' -newermt "$cutoff" -print -quit
```

- 変更が0件、または全て削除マーク（` D`）だけ → 中身の無い抜け殻なので `git worktree remove --force <path>`
- 30日以内に更新されたファイルが1件も無い → 中身があっても `git worktree remove --force <path>`。放置された worktree は戻ってこない
- 上のどちらでもない（変更があり、かつ30日以内に触られている） → **消さない**。path と件数を報告に載せる

worktree を消すと未 commit の変更は失われる。30日ルールはそれを承知で入れてある。ただし HEAD が detached でどの local branch からも到達できない場合は、gc で commit ごと消えるので残す。

**Orca 管理の worktree**: `~/orca/workspaces/` 配下など `orca worktree list` に出るものは、上の git 判定の前に `orca worktree ps --json` で `liveTerminalCount` を見る。live terminal（spawn 済みで生きている PTY。idle な shell も含む）が1つでもあるものは消さない — Orca workspace は質問・相談のように git に変更が残らないセッションの容器でもあり、git status が clean でも消すとセッションの入れ物ごと失う。live terminal が無いものだけ上の判定に進み、消すときは `git worktree remove` ではなく `orca worktree rm --worktree 'path:<path>'` を使う（git 側だけ消すと Orca の登録が dead path を指したまま残る）。なお `pr-auto-merge` は毎 tick local session を確認し、routine 外も含む merge 済み PR の完了済み session を close して、clean・branch/head 一致の worktree を片付ける。main・active workspace・作業中 session は残す。この cleanup 自体は live terminal の保護を維持する。

- `orca worktree rm` は checkout 中の local branch の削除も試みる。merge 未証明でも remote に同 commit があれば消える（OPEN PR の branch が消えた実例あり）。rm 後に `git branch --list` で確認し、下の branch 判定で残すべきものが消えていたら `git branch <b> origin/<b>` で復元する
- 誤って消した workspace の復元: local branch が消えていれば `git branch <b> <sha>`（sha は `git worktree list` の記録か reflog から）で戻し、`orca worktree create --repo name:<repo> --name <name> --base-branch <ref> --no-parent` で同 path に workspace を再作成できる。ただし live terminal の中身（scrollback・対話の表示状態）は戻らない
- `orca worktree ps --json` の `isPinned` フラグは削除判定に入っていない — pin しても PTY が落ちれば削除判定に進む。その後もこの cleanup の git 判定が適用されるので、dirty や30日以内の更新があれば残る

**workspace 置き場の残骸**（`~/orca/workspaces/`・`~/.codex/worktrees/`）: ここは repo を消しても dir だけが残る。`orca worktree list` に出ないものは Orca の管理から切り離されているので live terminal の判定は無く、次の順で見る。どの削除も**退避 → 削除**の順で行い、退避に失敗したら消さない。

- 退避先は `~/.local/state/cleanup/wip/`。先に `mkdir -p ~/.local/state/cleanup/wip` を実行する。file 名は `<name>-<worktree id か path の hash>-<date>` で一意にし、既に同名 file があれば上書きせず `-2`, `-3` … を付ける（前回の退避を潰さない）
- 空 dir: `.DS_Store` だけのものは `rm -f <dir>/.DS_Store` を先に実行してから `rmdir <dir>`（`rmdir` は中身があると失敗するので、予期しない中身が残っている場合の歯止めとして使う）。repo の置き場として空 dir を残す意味は無い（Orca は必要になれば作り直す）
- 親 repo が生きている → 通常の worktree と同じ判定（dirty かつ30日以内に触られていれば残す）。Orca 未登録なので `orca worktree rm` は使えず、`git -C <親 repo> worktree remove --force <path>` で消す。消す前に: (a) `git -C <path> log --oneline @{u}..` 等で未 push の commit を確認し、あれば**消さずに** branch 名と commit を報告、(b) 未 commit は `git -C <path> diff HEAD`（staged + unstaged）と `git -C <path> ls-files --others --exclude-standard` の file を tar で退避 → 空でなければ両方を wip に保存
- `.git` の `gitdir:` が指す親 repo が存在しない → clone ごと消えた残骸。`git worktree prune` では落ちないので `rm -rf` するが、**親 repo が無いので差分も commit 判定も取れない** — 未 push commit の確認は不可能で、branch 名も HEAD が読める場合しか分からない。そのため削除前に非 `.git` ツリー全体を `tar czf` で退避し、tar が失敗したら消さない。報告には「復旧不可（親 repo 不在）」と、読めた場合だけ branch/HEAD を書く
- repo を持たない dir（agent の成果物だけがある）→ 成果物を wip に退避してから `rm -rf`
- 個人 repo 以外（fork した外部 repo 等）の checkout も、上の条件を満たせば対象にする。Orca 未登録のまま残っているのは、作業が終わって置き去りにされた残骸とみなす

**branch の削除**: `main` と、worktree が checkout 中の branch は対象外。判定軸は PR の state ではなく **その commit を local branch 以外から辿れるか**。上から順に見て、当たった時点で確定する。

1. `git merge-base --is-ancestor <branch> origin/main` が真 → 削除（main に入っている）
2. `gh pr list --head <branch> --state all --json state` を見る:
   - `OPEN` → **削除しない**（作業中の可能性。merge されれば次回 1・2 で消える）
   - `MERGED` → 削除（squash merge は祖先判定に出ないのでこちらで拾う）
   - `CLOSED` / PR 無し → 3 へ
3. remote branch が生きていて `git merge-base --is-ancestor <branch> origin/<branch>` が真 → 削除（remote から辿れる。ここに来るのは PR が CLOSED か無いものだけ）
4. `git diff --stat origin/main...<branch>` が空 → 削除（固有の中身が無い）
5. それ以外 → まず**差分の中身が main に実質包含されていないか**を確認する。squash merge で sha が変わったもの・同じ変更が別経路で入ったもの・main 側に上位互換があるものは ancestor 判定に落ちないまま抜け殻として溜まる。`git diff origin/main...<branch>` の残差分を読み、`git show origin/main:<file>` で該当ファイルの現状と突き合わせ、同等・上位互換が既に main にあると確認できたら削除してよい（抜け殻。根拠を報告に添える）
6. 包含も確認できないもの → **削除しない**。local にしか無い実体差分を持つので、branch 名と差分の規模（`N files changed, +X/-Y`）に**中身の要約（何を変える branch か）と main との包含確認の結果**を添えて報告し、ユーザーの判断を待つ。差分規模だけだと中身を1本ずつ聞き返される往復が起きる

`gh` は sandbox 解除で実行する。

PR の state だけで残すと、remote に push 済みで消しても失われない branch が溜まり続ける。逆に PR が MERGED でも remote と分岐した local commit を持つことがあるので、1・2 に当たらなかったものは必ず 3・4 まで見る。

## 3. gc

fetch が成功した、または fetch 失敗後に判定で使う remote ref の SHA を GitHub API と照合できた repo で、上で worktree か branch を削除した場合に `git gc --prune=now` を実行する。照合できない repo と何も削除しなかった repo は skip する。

`gc --prune=now` は参照の無い commit の実体を消すので reflog 経由の復旧も効かなくなる。branch 判定の 5 は変更内容が main に実質包含されることだけを確認し、元の commit が main や remote から到達可能とは限らない — 消した時点で同等のコードは残っても元の commit 履歴は gc で失われる。その履歴を残す必要があるなら gc 前に別 ref を作る。detached HEAD の worktree を消した場合は、削除前に `git branch --contains <sha>` でその HEAD が local branch から到達可能かを確認しておく。

## 報告

1行サマリ（freed 合計 / 削除した worktree・branch・workspace 残骸の本数）と、判断を残した項目（30日以内に触られている dirty な worktree、branch 判定の 6 に落ちた branch のみ）を列挙する。6 の branch は差分規模に加えて中身の要約と main との包含確認の結果を添える。5 で消した抜け殻 branch は何が main のどこに入っているかの根拠を添える。30日ルールで消した worktree は未 commit の変更ごと消えるので、path と件数を報告に残す。workspace 残骸を消したときは、退避した patch / 成果物の path を載せる。skip だけで終わったならそう書く。なお `OPEN` PR がある branch を残すのは定常動作なので判断待ちには数えない — open PR の棚卸しは pr-auto-merge task（`.agents/scheduled-tasks/pr-auto-merge/`）が日次で担う。
