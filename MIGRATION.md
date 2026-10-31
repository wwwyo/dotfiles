# 新しい個人 Mac への移行

この手順では、dotfiles で再現できる設定と、手動で移す秘密情報やユーザーデータを分けて扱う。dotfiles の canonical clone 先は `~/src/github.com/wwwyo/dotfiles` とする。

## 旧 Mac で退避する

1. 各リポジトリで `git status --short --branch` を実行し、未コミット変更と未 push commit を確認する。残す変更は commit して push するか、リポジトリごと安全な保管先へコピーする。
2. ユーザーデータのバックアップは原則不要。Eagle library は Google Drive で管理しているので `google-drive` cask を入れれば sync で復元される。ブラウザと password manager のデータも account sync で移る。

age 復号鍵は password manager（Bitwarden の secure note）に退避済み。新 Mac での Keychain 再登録手順は後述。

それ以外のデータ（Obsidian vault、個人文書、Codex・Claude・Devin の会話履歴と cache、PostgreSQL のデータ、ブラウザ profile）は移行せず捨てる。

## 新しい Mac をセットアップする

1. dotfiles を canonical path へ clone する。

   ```bash
   mkdir -p ~/src/github.com/wwwyo
   git clone https://github.com/wwwyo/dotfiles.git ~/src/github.com/wwwyo/dotfiles
   cd ~/src/github.com/wwwyo/dotfiles
   ```

2. Homebrew と chezmoi を導入してセットアップを実行する。

   ```bash
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   brew install chezmoi
   chezmoi init --source ~/src/github.com/wwwyo/dotfiles
   chezmoi apply -v
   ```

   `chezmoi apply` が `home/` 配下を `~/` へ配置し、`run_once` script で `brew bundle`・duti・`mise install` まで走る（brew は手順2で入れたので installer は skip される）。

   Homebrew 外のアプリは一律に自動導入しない。会社用アプリの混入を避けるため、必要なアプリだけを公式サイトまたは App Store から導入する。

   この時点ではまだ age 復号鍵が無いが、`[settings.age] strict = false` なので `mise install` は失敗せず、暗号化した環境変数が無いだけで進む（実機検証済み）。次の step で鍵を登録する。

   Brewfile の `mas` 行は App Store へのサインインが前提。未サインインだと `brew bundle install` が非ゼロ終了し、`set -e` により run_once script がそこで止まる（mise install まで進まない）。先に App Store アプリでサインインしてから実行するか、失敗したらサインイン後に `chezmoi apply` を再実行する（`run_once` は成功した実行だけ記録されるので、失敗時は次の apply で最初からやり直される）。

3. password manager に退避した age 復号鍵を Keychain に登録する。次のコマンドは入力を表示せず、shell history に秘密値を残さない。鍵そのものをコマンド行へ書かない。

   ```bash
   printf 'age secret key: ' >&2
   IFS= read -rs AGE_SECRET_KEY
   printf '\n' >&2
   security add-generic-password -U -s mise-age-key -a "$USER" -w "$AGE_SECRET_KEY"
   unset AGE_SECRET_KEY
   ```

4. 新しい Mac 専用の passphrase 付き ed25519 SSH 鍵を作る。SSH 秘密鍵は dotfiles に入れない。

   ```bash
   mkdir -p ~/.ssh
   chmod 700 ~/.ssh
   ssh-keygen -t ed25519 -a 100 -f ~/.ssh/id_ed25519 -C "$(git config user.email)"
   ssh-add --apple-use-keychain ~/.ssh/id_ed25519
   # hosts.yml は移行対象外なので gh の再認証が必須。git の credential.helper も gh を経由する
   gh auth login
   gh ssh-key add ~/.ssh/id_ed25519.pub --type authentication --title "$(scutil --get ComputerName) authentication"
   gh ssh-key add ~/.ssh/id_ed25519.pub --type signing --title "$(scutil --get ComputerName) signing"
   ```

   `~/.ssh/config` の `Host github.com` は既に `id_ed25519` を指しているので変更不要。署名側は次の 2 箇所を dotfiles に反映する。両方とも symlink 経由で repo が書き換わるので、commit までが手順。

   ```bash
   cd ~/src/github.com/wwwyo/dotfiles
   git config --global user.signingkey ~/.ssh/id_ed25519.pub
   # 新鍵の署名をローカルの git log --show-signature が検証できるよう allowed_signers に追加
   printf '%s %s\n' "$(git config user.email)" "$(cat ~/.ssh/id_ed25519.pub)" >> home/dot_config/git/allowed_signers
   git add home/dot_gitconfig home/dot_config/git/allowed_signers && git commit -m "chore: 新しい Mac の SSH 署名鍵を登録"
   ```

   旧 SSH 秘密鍵のコピーは、既存システムとの互換性が必要な場合だけ行う。その場合も password manager や暗号化ストレージなどの安全な経路を使う。

5. 日本語入力の入力ソースを調整する。**システム設定 → キーボード → テキスト入力「編集」**を開き、「ABC」を選択して左下の「−」で削除し、「日本語－ローマ字入力」は残す。ABC が登録されていると、英数キー1回目でABCへ切り替わって未確定のかなが確定される。ABCを外すと、日本語入力中に誤ってかなになった文字列を英数キー2回でローマ字へ戻せる。英数キー1回は英字入力への切替に使う。[Appleの日本語入力ガイド](https://support.apple.com/ja-jp/guide/japanese-input-method/jpim10231/mac)
6. デスクトップ、Dock、キーボードなどの個人設定を必要に応じて戻す。現在の Mac で確認した値は次の通り。macOS の既定値との差分を網羅したものではないため、新しい Mac では好みに合わせて選ぶ。

   - **システム設定 → デスクトップとDock**：Dock は画面下、サイズ 46、自動的に表示/非表示をオン、拡大をオフ。ウインドウを Dock にしまうときは Genie エフェクト。アプリケーションアイコンへのウインドウ最小化はオフ、起動時のアニメーション・起動中インジケータ・最近使ったアプリの表示はオン。
   - デスクトップの壁紙クリックでウインドウをよける設定は「常に」。ステージマネージャはオフ。Mission Control は操作スペースを最近の使用状況に基づいて自動整列、ディスプレイごとに個別の操作スペースを使用。アプリごとのウインドウグループ化はオフ。
   - ウインドウのタイトルバーをダブルクリックしたときの動作は「拡大」。書類を開くときはフルスクリーン時のみタブで開く。アプリ終了時にウインドウを閉じる設定はオン。
   - **システム設定 → キーボード**：キーリピートは速め、リピート入力認識までの時間は短め。Globe キーは入力ソースの切り替え。英数キーで日本語入力中の未確定文字をローマ字に戻す操作を使う場合は、手順 5 の入力ソース構成も合わせる。
   - **システム設定 → キーボード → キーボードショートカット → Dock**：「Dockを自動的に表示/非表示」のショートカット（⌥⌘D）はオフ。ほかのショートカットカテゴリは今回確認していないため、必要なものを新旧 Mac で見比べる。
   - **Finder のデスクトップ表示**：外部ディスクをデスクトップに表示、内蔵ハードディスクは非表示。デスクトップアイコンは自動整列せず、アイコンサイズ 64。

   「システム設定 → デスクトップとDock」「キーボード」「キーボードショートカット」は GUI で設定する。`defaults` で読み取れる設定もあるが、macOS のバージョンでキーや挙動が変わるため、移行時は画面上の値を優先する。

7. macOS の権限を手動で再許可する。画面収録、アクセシビリティ、入力監視、フルディスクアクセス、マイク、カメラなど、各アプリが必要とする権限をシステム設定で確認する。

### dotfiles 管理外で手動対応するもの

- `~/.claude.json` の MCP server（context7 等）は Claude が自分で書き換えるファイルなので dotfiles では管理しない。`claude mcp add` で再登録する
- `~/.ssh/config.local` はマシン固有の Host（AWS SSM の ProxyCommand 等）を置く git 管理外のファイル。無くても `Include` は警告のみで動く
- `~/.npmrc` は dotfiles 管理しない。`npm login` が token をこのファイルに書き込むため、symlink 化すると平文 token が repo の diff に混ざる。npmjs の認証は必要なときに `npm login` する運用。
- 定期実行の automation は Orca で管理している。移行時は Orca 側で作り直す。`.config/devin/automations/` は使っていない
- Anarlog.app の同梱 CLI はアプリの起動時に `~/.local/bin/anarlog` へ自動 install される（`~/.local/bin` は PATH 通し済み）。失敗時はログのみで静かにスキップされるので、`anarlog` が見つからないときは Settings → Developers → Install で再 install する。どちらも無い場合は `/Applications/Anarlog.app/Contents/MacOS/anarlog-cli` を直接呼べる
- `home/Library/LaunchAgents/` の worker plist は `$HOME` 化済みで dotfiles 管理対象。chezmoi が `~/Library/LaunchAgents/` に deploy する。outpost は `<outpost>` の placeholder にしてあるため、使うときに outpost の ID または名前を設定する。未設定、Devin.app 未導入、worker ディレクトリ未作成の場合は exit 0 で待機し、再起動ループにはならない。
  Devin CLI を導入して outpost を設定した後は、LaunchAgent を読み直す。正常終了したジョブは設定変更だけでは再起動しない。

  ```sh
  launchctl bootout "gui/$(id -u)" "$HOME/Library/LaunchAgents/ai.devin.worker.plist" 2>/dev/null || true
  launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/ai.devin.worker.plist"
  ```

- VSCode / Cursor の設定は dotfiles にあるが両アプリとも現在未導入。入れるときは settings 内の `${env:HOME}` がそのまま使える

## セットアップを検証する

検証前にターミナルを開き直し、新しい login shell を開始する。新しい shell が Keychain から `MISE_AGE_KEY` を読み込んだ後、次を確認する。

```bash
# age 暗号化した環境変数を、値を表示せずに復号できる
mise exec -- sh -c 'test -n "$OPENCODE_API_KEY"'

# 宣言した tool に不足がない
mise ls --missing
mise ls

# SSH 接続と署名鍵の設定
ssh -T git@github.com
git config --global --get user.signingkey
ssh-keygen -lf ~/.ssh/id_ed25519.pub

# 主要コマンド
command -v git mise node python gh rg

# Anarlog 同梱 CLI(アプリ初回起動で auto install される。未起動なら一度開いてから)
command -v anarlog
```

署名付き commit を作って GitHub へ push し、GitHub 上で署名が Verified になることも確認する。

## 旧 Mac を消去する前に確認する

- dotfiles と残すリポジトリに dirty な変更や未 push commit がない。
- 新しい Mac で age 復号、mise tool、主要コマンドが動く。
- GitHub への SSH 接続と commit 署名を確認した。
- Google Drive（Eagle library）とブラウザ、password manager の sync が完了した。
- macOS の必要な権限を再許可した。
