Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## システム

```bash
container system start                  # サービス起動
container system stop                   # サービス停止
container system status
container system version
container system logs -f                # サービスログ
container system logs --last 1h
container system df                     # イメージ・コンテナ・ボリュームのディスク使用量
```

### カーネル管理

`--arch` で指定できるのは `arm64`（既定）と `amd64` のみ。`amd64` ゲストは Rosetta で動くため通常は `arm64` カーネルだけで足りる。

```bash
container system kernel set --recommended                   # 推奨カーネルを取得・適用
container system kernel set --tar https://.../kata.tar.zst --binary opt/kata/.../vmlinux
container system kernel set --binary ./vmlinux --arch arm64 --force
```

### システムプロパティ

`~/.config/container/config.toml` の現在値を一覧表示。

```bash
container system property list                    # TOML
container system property list --format json
```

## 設定ファイル `~/.config/container/config.toml`

|セクション|主な用途|
|:--|:--|
|`[build]`|ビルダー VM の CPU / メモリ / Rosetta / image|
|`[container]`|`run` / `create` の既定 CPU・メモリ|
|`[dns]`|`domain`（コンテナ名に補完されるドメイン）|
|`[kernel]`|`binaryPath` / `url`（カーネルアーカイブ）|
|`[network]`|新規ネットワークの既定 `subnet` / `subnetv6`|
|`[registry]`|イメージ参照でレジストリ省略時の既定 `domain`|
|`[vminit]`|`vminitd` イメージ|
|`[plugin.<id>]`|プラグイン固有設定|

例：

```toml
[build]
rosetta = false
cpus = 4
memory = "4gb"

[container]
cpus = 4
memory = "1gb"

[dns]
domain = "test"

[network]
subnet = "192.168.100.0/24"
subnetv6 = "fd00:abcd::/64"

[registry]
domain = "ghcr.io"
```

### メモリ表記

二進系（1024 基数）。`b` / `k|kb|kib` / `m|mb|mib` / `g|gb|gib` / `t|tb|tib` / `p|pb|pib`。
裸の整数はバイト扱い。

### CIDR

IPv4 例 `"192.168.100.0/24"` / IPv6 例 `"fd00:abcd::/64"`。読み込み時に検証され、不正なら起動失敗。

## シェル補完

```bash
container --generate-completion-script zsh > ~/.oh-my-zsh/completions/_container
container --generate-completion-script bash > /opt/homebrew/etc/bash_completion.d/container
container --generate-completion-script fish > ~/.config/fish/completions/container.fish
```

ファイル名は zsh のみ `_container` 固定。
