Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## クイックリファレンス

| やりたいこと | コマンド |
|:--|:--|
| サービス起動 / 停止 | `container system start` / `container system stop` |
| イメージ取得 | `container image pull <ref>` |
| イメージビルド | `container build -t <name> .` |
| 対話実行 | `container run -it <image> /bin/sh` |
| バックグラウンド実行 | `container run -d --name <name> --rm <image>` |
| ポート公開 | `container run -p 127.0.0.1:8080:80 <image>` |
| ボリュームマウント | `container run -v $HOME/x:/x <image>` |
| SSH 転送 | `container run --ssh <image>` |
| シェルに入る | `container exec -it <id> sh` |
| ログ追従 | `container logs -f <id>` |
| 起動ログ | `container logs --boot <id>` |
| 統計表示 | `container stats <id>` |
| コピー | `container cp <src> <dst>` |
| 停止・削除 | `container stop <id>` / `container rm <id>` |
| イメージ push | `container image push <ref>` |
| レジストリ認証 | `container registry login <host>` |
| ネットワーク作成 | `container network create <name>` |
| DNS ドメイン作成 | `sudo container system dns create <name>` |
| ボリューム作成 | `container volume create <name>` |
| マシン作成 | `container machine create <image> --name <id>` |
| マシンでシェル | `m run -n <id>` |
| ディスク使用量 | `container system df` |
| サービスログ | `container system logs -f` |
| バージョン確認 | `container system version` |
