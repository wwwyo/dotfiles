Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## コンテナマシン（`container machine`、alias `m`）

「アプリ 1 つを動かすコンテナ」ではなく「永続化された Linux 開発環境」が欲しいときに使う。

作成するイメージは信頼済みのものを選ぶ。machine はホストの HOME を既定で読み書き可能に共有し、SSH agent を転送する。通常の container の隔離を前提にしない（[公式の共有範囲](https://github.com/apple/container/blob/main/docs/container-machine.md)）。

特徴：

- OCI イメージから作る
- ホストのユーザーアカウントと同名のユーザーが作られる
- `$HOME` がそのまま `/Users/<username>` にマウントされる
- 停止しても FS が残る
- 通常の OCI コンテナと違い `/sbin/init` を起動する（`systemd` で長期サービス常駐が可能）

```bash
container machine create alpine:latest --name dev
container machine set-default dev
m run                                  # 対話シェル（既定マシン）
m run -n dev whoami                    # ホストのユーザー名が返る
m run -n dev pwd                       # HOME 配下ならホストの現在dir、それ以外なら Linux ユーザーの home
m run -n dev -- cat /proc/cpuinfo
m ls
m inspect dev
m stop dev
m rm dev                               # 永続ストレージごと削除
```

リソースは `set` で更新（次回起動から反映）：

```bash
m set -n dev cpus=4 memory=8G
m set -n dev home-mount=ro             # ro / rw / none
m set -n dev virtualization=true kernel=/path/to/vmlinux-kvm
m set -n dev kernel=                   # カスタムカーネル解除
m stop dev && m run -n dev -- nproc
```

### 独自イメージ

`/sbin/init` を含む Linux イメージなら何でも使える。最初の起動で自動でユーザー作成スクリプトが走るが、`/etc/machine/create-user.sh` をイメージ内に置けば独自プロビジョニングに差し替えられる（環境変数 `CONTAINER_USER` / `CONTAINER_UID` / `CONTAINER_GID` / `CONTAINER_HOME` / `CONTAINER_MACHINE_ID` が渡る）。

```dockerfile
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y dbus systemd openssh-server ...
RUN systemctl set-default multi-user.target
```
