---
name: apple-container
description: Apple Silicon Mac で動く軽量 Linux コンテナランタイム `container` の利用者向けリファレンス。`container run`、`container build`、`container image pull/push`、`container machine`、ボリューム・ネットワーク・DNS・設定ファイルなど、日常的なコマンドの使い方を網羅する。`container` コマンドの使い方やトラブルシューティングに関する質問で使用する。
---

# apple-container（`container` CLI）

Apple 製の `container` ツールは、Linux コンテナを 軽量 VM 1 つ = コンテナ 1 個 の方式で Mac 上に起動するランタイム。OCI 互換イメージを使うため Docker / podman で作ったイメージがそのまま動く。リポジトリは [apple/container](https://github.com/apple/container)。

> このスキルは 利用者向け。ソースコードの修正やビルド方法ではなく、`container` コマンドを使う側の知識を扱う。

## 動作要件

- Apple Silicon Mac（Intel Mac 不可）
- macOS 26 推奨。macOS 15 でも動くが以下が制限される（issue は再現環境が macOS 26 でないと対応されない）。
  - コンテナ間ネットワーク通信不可（すべてのコンテナが default ネットワークに孤立して所属）
  - `container network` コマンド利用不可
  - `--network` 指定はエラー
  - サブネットは `192.168.64.1/24` 固定（vmnet との不整合でネットが完全に切れることがある）

### 対応アーキテクチャ

ゲストとして動かせるのは `linux/arm64`（ネイティブ）と `linux/amd64`（Rosetta 経由）の 2 つだけ。

- `container system kernel set --arch` は CLI ヘルプで `amd64` / `arm64` の 2 値しか受け付けないと明記。
- `container run --arch` / `container build --arch` は CLI 側で値を弾かないので `riscv64` / `ppc64le` / `s390x` などを書いてもイメージ pull や VM 起動まで進んでしまうが、ゲストプロセス起動時に `Exec format error` で失敗する。

## Routing

必要な操作の reference だけを読む。動作要件は上の共通条件、コマンドの flag は実行する版の `container <command> --help` で確認する。

| やること | 読む reference |
| --- | --- |
| インストール・起動・CLI の全体構造 | [references/setup-system.md](references/setup-system.md) |
| コンテナを動かす・ポート・mount・リソース | [references/run.md](references/run.md) |
| build・image・registry | [references/build-images.md](references/build-images.md) |
| コンテナ管理・logs・stats・export | [references/manage.md](references/manage.md) |
| network・DNS・volume | [references/network-storage.md](references/network-storage.md) |
| container machine | [references/machines.md](references/machines.md) |
| kernel・system・設定・補完 | [references/system-config.md](references/system-config.md) |
| 既知の制限を確認する | [references/limitations.md](references/limitations.md) |
| コマンドを素早く引く | [references/quick-reference.md](references/quick-reference.md) |
