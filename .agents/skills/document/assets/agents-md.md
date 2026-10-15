# <project-name>

## Story

<一文: 誰の生活で、何をするか。人が主語、機能名は書かない>

Core actions:
- <ユーザーが実際にやること> — <cycle>

## ディレクトリ構造

<repo の構造と文書の配置規約>

```
<repo>/
└── {docs|.agent}/
    ├── prd/    機能ごとの要件・設計書（構造は prd/README.md）
    └── adr/    戻すのが難しい判断（構造は adr/README.md）
```

<docs/ は共有文書として Git で管理する。.agent/ は個人メモとして Git の管理対象から外す。選んだ方を描く>

<各 dir 内の構造は README.md に書き、ここには重複させない>

## セットアップ

ツールは mise で管理している。

```bash
mise install   # mise.toml に従ってツールをインストール
```

<起動・ビルド・テスト・lint のコマンド>

## 技術スタック

<言語・フレームワーク・主要ライブラリ>

## Skills

<agent がいつ文書や skill を読むか、条件と参照先を1行ずつ書く。詳細は参照先に置く>

- 学び・ハマりどころ・過去の失敗は `.agents/skills/<topic>/` を参照
