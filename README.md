# dotfiles

個人用の dotfiles リポジトリ。[chezmoi](https://www.chezmoi.io/) で管理する。macOS と Linux（Omarchy 等）の両対応。

## セットアップ手順

1. dotfiles を canonical path へ clone

   ```bash
   git clone <repository-url> ~/src/github.com/wwwyo/dotfiles
   ```

2. chezmoi をインストール。macOS は brew（未導入なら先に [Homebrew](https://brew.sh) を入れる。以降は `brew bundle` が面倒を見る）、Linux/Omarchy は pacman

   ```bash
   # macOS
   brew install chezmoi
   # Omarchy（Arch）
   sudo pacman -S chezmoi
   ```

3. init + apply

   ```bash
   chezmoi init --source ~/src/github.com/wwwyo/dotfiles
   chezmoi apply -v
   ```

   `chezmoi init` が `~/.config/chezmoi/chezmoi.toml` を生成する（`home/.chezmoi.toml.tmpl` から。`sourceDir` と `mode = "symlink"` が書き込まれる）。apply は次の処理を行う。

   - `home/` 配下のファイルを `~/` へ配置（基本は source への symlink。template / executable は実ファイル）
   - `run_once_10-install` で環境構築（darwin: brew bundle + duti + defaults + mise install / linux: mise install）
   - `run_once_after_15-migrate-legacy-links` で旧 link.sh 時代の whole-dir link 先に残った repo 管理外ファイル（`~/.config/mise/conf.d/local.toml` 等）を新しい dir へ移行
   - `run_after_20-link-repodirs` で repo 内 dir の symlink（`.agents`, `.claude/*`, `.codex/*` 等）を張る

   **apply は main checkout（canonical path）から実行すること**。worktree から apply すると link 先が worktree 内を指し、worktree 削除で壊れる。

   age 復号鍵、SSH 秘密鍵、ユーザーデータは自動移行しない。Mac を移行する場合は [MIGRATION.md](MIGRATION.md) の手順に従う。

   macshot は起動後、**Settings → General → Settings Backup → Import Settings…** で [scripts/macshot-settings.json](scripts/macshot-settings.json) を選び、確認して再起動する。

### GitHub CLI 拡張

`gh-secure` はプロジェクトごとではなく、ユーザー単位で一度インストールする。`gh` は mise 管理のものを使い、拡張は 7 日以上経過した commit（2026-09-14 の版）に固定する。

```bash
mise exec -- gh extension install GitHubSecurityLab/gh-secure --pin 42c928f94b61caae03774d2436b897a1d04fff20
mise exec -- gh secure --version
```

## 構造

```
.chezmoiroot        # "home" — chezmoi の source root を home/ に指定
home/               # chezmoi source state（~/ へ deploy されるもの）
  dot_gitconfig     # → ~/.gitconfig
  dot_config/       # → ~/.config/
  dot_claude/       # → ~/.claude/（file entry のみ。dir は link script 側）
  Library/          # → ~/Library/（macOS only）
  run_once_*        # apply 時に1度だけ走る install script
  run_after_*       # apply 後に走る dir link script
.agents/ .claude/ .codex/ .pi/   # chezmoi 管理外。run_after script が dir 丸ごと symlink
scripts/ docs/ tests/            # repo 内部ファイル（deploy されない）
```

### 命名規則（chezmoi）

- `dot_foo` → `~/.foo`、`private_` → 権限 0600、`executable_` → +x、`symlink_` → symlink、`*.tmpl` → template 評価
- `home/dot_local/bin/` → `~/.local/bin/`（PATH 上）。vendored な CLI は `executable_` 付きでここに置く。単一 skill からしか呼ばれない script はここではなく `<skill_dir>/scripts/` に置く
- OS 分岐は `{{ if eq .chezmoi.os "darwin" }}`（`.tmpl` ファイル or `.chezmoiignore`）で行う
- `.chezmoiignore` で deploy 対象外を指定（macOS 専用 entry の linux 無効化、dir link 対象の除外）

### dir 単位リンク（chezmoi 管理外）

以下は `run_after_20-link-repodirs.sh.tmpl` が repo 内 dir へ symlink を張る（理由は `.chezmoiignore` 冒頭）:

- `.agents` — skillctrl が skill を取り込み、merge 後の実体を各 agent が共有する
- `.claude/{skills,agents}` / `home/dot_claude/hooks` — 同上 + repo 内相対 symlink（`skills/*` → `../../.agents/`）+ executable script
- `.agents/scheduled-tasks` → `~/.claude/scheduled-tasks` — Orca automation の手順書置き場。repo 内の `.claude/scheduled-tasks` は旧パスの互換 symlink
- `.codex/{rules,scripts,hooks,automations,skills}` / `.pi/agent/extensions` — 同上
- `home/dot_config/{git/hooks,mise/tasks}` — executable を含むため per-file symlink 不可

## 新しいファイルを追加する方法

- **`~/` に置きたい file**: `home/` 配下に `dot_` 命名で追加 → `chezmoi apply`
- **実行ファイル / runtime が書き込む dir**: 該当 dir が dir link 対象なら repo 内に置くだけ（`chezmoi apply` 不要）。新しい dir link 対象を足す場合は `run_after_20-link-repodirs.sh.tmpl` に `link_dir` 行を追加
- **OS 依存の中身**: shell script は `[[ "$OSTYPE" == darwin* ]]` で分岐。JSON/TOML は `.tmpl` 化して `{{ if eq .chezmoi.os }}` で分岐

## 注意事項

- 既存のファイルは chezmoi が検出する（`chezmoi apply` で上書きされる前に `chezmoi diff` で確認推奨）
- `.ssh/config` のみ管理対象。SSH 鍵や `~/.ssh/config.local`（マシン固有の Host）などの機密ファイルは対象外
- Codex の共通設定は `home/.chezmoitemplates/codex-base.toml.tmpl`。`~/.codex/config.toml` は実ファイルで、apply は共通設定だけを更新する。repo trust・hook 承認履歴・PC 固有の plugin 配置先などはローカルに保持され、repo には同期されない。`~/.codex/hooks.json` は引き続き template から配置する。
- Pi の共通 sandbox 設定は `home/.chezmoitemplates/pi-sandbox-base.json`。`~/.pi/agent/sandbox.json` は実ファイルで、個別ファイルの読み取り許可はローカルだけに保存する。sandbox は恒久無効のまま。
- **旧 Pi sandbox symlink からの移行**: この変更を pull する前に、`~/.pi/agent/sandbox.json` を内容を保った実ファイルへ置き換える。旧リンク先の source を移動するため、pull 後では古い個別許可を読めなくなる。`chezmoi apply ~/.pi/agent/sandbox.json` で共通設定を反映する。新規セットアップでは不要。
- `~/.claude/settings.json` は repo への symlink なので書き戻しが `git status` に出る。Devin の `~/.config/devin/config.json` は template から作る実ファイルで、承認や個人設定はローカルに保持する。Devin の Orca hook は PC ごとの home directory から描画する。
- mise の age 復号鍵は macOS では Keychain（`service=mise-age-key`）、それ以外では gitignore 済みの `~/.config/mise/age.txt` から読む（`home/dot_zsh/01-exports.zsh`）。鍵ファイル自体は repo に置かず、password manager 等の別経路で持ってくる

設定の分離・新規セットアップ・再 apply・hook の可搬性は、chezmoi と Python がある環境で `python3 tests/agent-config-local-state.py` により確認できる。
