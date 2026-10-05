Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## コンテナ管理

```bash
container ls                          # 実行中
container ls -a                       # 停止中も含む
container ls --format json --all | jq '.[] | .configuration.id'

container inspect my-web-server | jq
container logs my-web-server                # 標準出力ログ
container logs --boot my-web-server         # VM ブートログ
container logs -f -n 100 my-web-server      # 末尾 100 行を tail -f

container exec -it my-web-server sh          # 既存コンテナにシェルで入る
container exec my-web-server ls /content

container cp ./config.json my-web-server:/etc/app/   # ホスト→コンテナ
container cp my-web-server:/var/log/app.log ./       # コンテナ→ホスト

container stop my-web-server                  # SIGTERM、5 秒後 SIGKILL
container stop -s SIGINT -t 30 my-web-server
container kill my-web-server                   # 即時 SIGKILL
container rm my-web-server                     # 停止後に削除
container rm -f my-web-server                  # 実行中でも強制削除
container prune                                # 停止中のコンテナをまとめて削除
```

### ステータス監視

```bash
container stats                              # 全コンテナを top 風に表示
container stats --no-stream my-web-server    # 単発スナップショット
container stats --format json --no-stream my-web-server | jq
```

### ファイルシステムのエクスポート

```bash
container stop my-web-server
container export -o my-web-server.tar my-web-server
container export my-web-server > my-web-server.tar
```
