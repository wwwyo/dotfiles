Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## インストール・起動

### 初回インストール

```bash
brew install container
container system start
```

初回はカーネルのダウンロードを促すプロンプトが出る。`Y` で承認。`brew services start container` でログイン時に自動起動するサービスとして登録することもできる。

### アップグレード

```bash
container system stop
brew upgrade container
container system start
```

### アンインストール

```bash
container system stop
brew uninstall container
```

ユーザーデータ（`~/.config/container` など）は `brew uninstall` では消えないので、不要なら手動で削除する。

### 起動確認

```bash
container system status
container system version
container list --all      # 空でも応答すれば OK
```

## CLI の全体構造

サブコマンドツリーは大きく分けて以下のグループ。

| グループ | 主なコマンド |
|:--|:--|
| コンテナ | `run` / `create` / `start` / `stop` / `kill` / `delete` (`rm`) / `list` (`ls`) / `exec` / `logs` / `inspect` / `stats` / `copy` (`cp`) / `export` / `prune` |
| イメージ | `build` / `image pull` / `image push` / `image list` / `image inspect` / `image tag` / `image save` / `image load` / `image delete` / `image prune` |
| ビルダー | `builder start` / `builder status` / `builder stop` / `builder delete` |
| ネットワーク（macOS 26+） | `network create` / `network list` / `network inspect` / `network delete` / `network prune` |
| ボリューム | `volume create` / `volume list` / `volume inspect` / `volume delete` / `volume prune` |
| レジストリ | `registry login` / `registry logout` / `registry list` |
| コンテナマシン | `machine create` / `machine run` / `machine list` / `machine inspect` / `machine set` / `machine set-default` / `machine logs` / `machine stop` / `machine delete`（alias: `m`） |
| システム | `system start` / `system stop` / `system status` / `system version` / `system logs` / `system df` / `system dns ...` / `system kernel set` / `system property list` |

ヘルプ全般は `container --help` / `container <subcommand> --help`。
