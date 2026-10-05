Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## コンテナを動かす（`container run`）

### 基本

```bash
container run -it ubuntu:latest /bin/bash                # 対話シェル
container run -d --name web -p 8080:80 nginx:latest      # バックグラウンドで Web サーバー
container run --rm alpine echo hello                      # 終了後に削除
```

イメージ名にレジストリを省略すると `~/.config/container/config.toml` の `[registry] domain` が補完される（デフォルト `docker.io`）。

### よく使うオプション

| 用途 | フラグ |
|:--|:--|
| 名前付け | `--name <id>` |
| バックグラウンド | `-d` / `--detach` |
| 自動削除 | `--rm` |
| 対話 | `-i` / `-t`（合わせて `-it`） |
| 環境変数 | `-e KEY=VAL` / `-e KEY`（ホストから継承）/ `--env-file <path>` |
| 作業ディレクトリ | `-w /path` |
| ユーザー | `-u name\|uid[:gid]` / `--uid` / `--gid` |
| `ulimit` | `--ulimit <type>=<soft>[:<hard>]` |

### リソース

```bash
container run --cpus 8 --memory 32g big              # 既定は 4 CPU / 1 GiB
container run --shm-size 1G img                      # /dev/shm のサイズ
container run --tmpfs /tmp img                       # tmpfs マウント
```

### ファイル共有

`--volume` と `--mount` は同じ機能の別表記。

```bash
# ホストの ~/Desktop/assets をコンテナの /content/assets にマウント
container run -v ${HOME}/Desktop/assets:/content/assets python:alpine ls /content/assets

# 同じことを --mount で
container run --mount source=${HOME}/Desktop/assets,target=/content/assets,readonly python:alpine ls /content/assets
```

匿名ボリューム（`-v /path` 形式）は `--rm` を付けても 自動削除されない（Docker と違う）。`container volume rm <anon-id>` で明示的に消す。

### ポート公開

```bash
container run -d --rm -p 127.0.0.1:8080:8000 node:latest                  # IPv4
container run -d --rm -p '[::1]:8080:8000' node:latest                    # IPv6
container run -d --rm -p 8080:80/udp img                                  # プロトコル指定
```

書式: `[host-ip:]host-port:container-port[/protocol]`。複数ネットワーク接続時は最初に attach したインターフェイスへ転送される。

### マルチプラットフォーム

対応するのは `arm64`（ネイティブ）と `amd64`（Rosetta 経由）の 2 つのみ。

```bash
container build --arch arm64 --arch amd64 -t img .
container run --arch amd64 --rm img uname -a        # amd64 は Rosetta 経由で動く
```

### SSH エージェント転送

```bash
container run -it --rm --ssh alpine sh
# 内部: SSH_AUTH_SOCK=/run/host-services/ssh-auth.sock が設定される
```

### Linux capability

既定では制限された capability セット（`CAP_NET_BIND_SERVICE` などのみ）。

```bash
container run --cap-add NET_ADMIN alpine ip link set lo down
container run --cap-add ALL alpine sh
container run --cap-drop ALL --cap-add SETUID --cap-add SETGID alpine id
```

`CAP_` 接頭辞、大文字小文字は不問。`--cap-drop` が `--cap-add` より先に処理される（`--cap-drop ALL --cap-add ALL` は ALL を付与）。

### init プロセス

シグナル転送・ゾンビ刈り取りが必要なら `--init`。

```bash
container run --init ubuntu:latest my-app
```

カスタム init イメージ（`vminitd` をラップする独自バイナリ）は `--init-image <image>` で指定。VM ブート時に独自ロジックを差し込みたい場合に使う。

### ネスト仮想化

M3 以降の Apple Silicon と `CONFIG_KVM=y` 付きカーネルが必要。

```bash
container run --virtualization --kernel /path/to/vmlinux-kvm --rm ubuntu sh -c "dmesg | grep kvm"
```
