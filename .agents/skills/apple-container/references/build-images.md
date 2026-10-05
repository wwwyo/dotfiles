Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## イメージのビルド（`container build`）

```bash
container build -t my-app:latest .                                # Dockerfile を探してビルド
container build -f docker/Dockerfile.prod -t my-app:prod .        # Dockerfile を明示
container build --build-arg NODE_VERSION=18 -t my-app .           # build-arg
container build --target production --no-cache -t my-app:prod .   # ステージ指定
container build -t my-app:latest -t my-app:v1.0.0 .               # 複数タグ
```

ファイル探索順は `Dockerfile` → `Containerfile`。

### ビルダーのリソース

ビルダーは別の VM（既定 2 CPU / 2 GiB）。大きなビルドが詰まったら：

```bash
container builder stop && container builder delete
container builder start --cpus 8 --memory 32g
```

ビルド時に Rosetta を使わせない設定：

```toml
# ~/.config/container/config.toml
[build]
rosetta = false
```

## イメージ管理

```bash
container image list                                              # ローカルイメージ
container image inspect web-test | jq                             # 詳細 JSON
container image pull alpine:latest                                # 取得
container image push registry.example.com/me/img:latest           # 送出
container image tag web-test registry.example.com/me/web:latest   # 別名付与
container image save -o img.tar img1 img2                          # tar に保存
container image load -i img.tar                                    # tar から読み込み
container image delete web-test                                    # 削除
container image prune -a                                           # 未使用を一括削除
```

### レジストリ認証

```bash
container registry login some-registry.example.com                # 対話入力
echo $TOKEN | container registry login --password-stdin -u me reg # stdin
container registry list
container registry logout some-registry.example.com
```

レジストリ既定値は `[registry] domain` で変更。`--scheme auto`（既定）はループバック・RFC1918・既定 DNS ドメインの場合のみ HTTP、それ以外は HTTPS を選ぶ。
