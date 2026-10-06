# <project-name>

## Story

<一文: 誰の生活で、何をするか。人が主語、機能名は書かない>

Core actions:
- <ユーザーが実際にやること> — <cycle>

## ディレクトリ構造

<repo の構造と文書の配置規約>

```
<repo>/
└── {docs|.agent}/prd/<topic>/{prd|dd}.md
```

<docs/ は共有文書として Git で管理する。.agent/ は個人メモとして Git の管理対象から外す。選んだ方を描く>

<topic は機能ごとのディレクトリ名。prd.md は要件、dd.md は必要な場合の設計書を示す。同じ topic 配下にまとめる>

<置き場の規約は prd skill を参照する>

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
