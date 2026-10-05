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

<docs/ は共有・tracked、.agent/ は個人メモ・gitignore。選んだ方を描き、topic は機能ごとのディレクトリ名を表す。prd.md が要件、dd.md が必要な場合の設計書。同じ topic 配下にまとめる。置き場の規約は prd skill を参照>

## セットアップ

ツールは mise で管理している。

```bash
mise install   # mise.toml に従ってツールをインストール
```

<起動・ビルド・テスト・lint のコマンド>

## 技術スタック

<言語・FW・主要ライブラリ>

## Skills

<repo 起動時に agent へ「いつ load するか」を伝える trigger を 1 行ずつ。詳細は書かず参照だけ置く>

- 学び・ハマりどころ・過去の失敗は `.agents/skills/<topic>/` を参照
