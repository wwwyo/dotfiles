Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## ネットワーク（macOS 26+）

`container system start` で `default`（vmnet）ネットワークが作られる。任意の隔離ネットワークを追加できる。

```bash
container network create foo
container network create foo --subnet 192.168.100.0/24 --subnet-v6 fd00:1234::/64
container network ls
container network inspect foo
container network delete foo                  # 接続中コンテナがあると削除不可
container network prune                       # 未接続のものを一括削除

container run -d --name web --network foo web-test
container run -d --network default,mac=02:42:ac:11:00:02 ubuntu     # MAC 指定
```

MAC を指定するときは第 1 オクテットの最下位 2 bit を `10`（ローカル管理・ユニキャスト）に。

既定サブネットを変えるには：

```toml
# ~/.config/container/config.toml
[network]
subnet = "192.168.100.1/24"
subnetv6 = "fd00:abcd::/64"
```

### ローカル DNS ドメイン

`container` には組み込み DNS がある。`--name my-web-server` で起動したコンテナを `my-web-server.<domain>` で名前解決できるようにする。

```bash
sudo container system dns create test                       # ドメイン test を登録
sudo container system dns create host.container.internal --localhost 203.0.113.113   # ホストの IP を返す
container system dns list
sudo container system dns delete test
```

注意（macOS のパケットフィルタ制約）:

- `--localhost` を使うと Private Relay が無効化 される
- ローカルドメインのパケットフィルタ規則は macOS 再起動で消える

ホスト側のサービスへコンテナからアクセスしたいときの定番は `host.container.internal` パターン。

## ボリューム

名前付きボリュームと匿名ボリュームの 2 種類。匿名は `--rm` でも消えない点に注意。

```bash
container volume create myvol                                          # 名前付き作成
container volume create --opt journal=ordered myvol                    # ext4 ジャーナル指定
container volume create --opt journal=writeback:64m myvol              # ジャーナルサイズも指定
container volume create -s 10g myvol                                   # サイズ
container volume create --opt size=10g myvol                           # 同上（-s が優先）

container volume ls
container volume inspect myvol
container volume rm myvol                                              # 使用中は削除不可
container volume prune                                                 # 未参照のものを一括削除
```

ジャーナルモード：

- `ordered`（既定相当）: メタデータのみジャーナル、データはメタデータより先にディスクへ
- `writeback`: メタデータのみジャーナル、順序保証なし（最速・最も危険）
- `journal`: メタデータとデータ両方ジャーナル（最も安全）
