両ファイルが揃いました。

## 変更したファイル

- `README.md`（英語・正本）
- `docs/README.ja.md`（日本語版、新規）

## 旧 README で実装と矛盾していた記述

fixture 内の事実（`project.json`、`sumcsv.py`、`examples/expenses.csv`、`LICENSE`）と突き合わせて削除した項目:

| 旧記述 | 実態 |
|---|---|
| CSV / Excel 対応 | `csv` モジュールのみ（Excel 非対応） |
| クラウドへ自動同期 | `project.json` の `network: false`。同期なし |
| 表計算より 10 倍高速 | 測定条件も実装も存在しない主張 |
| `npm install` / `npm start` | Python 3.11+ のスクリプト。`dependencies: []` |
| Roadmap: チャート・ホスト型ダッシュボード | 実装に存在しない将来計画 |

代わりに実装から確認できた事実だけを書きました: `python3 sumcsv.py FILE.csv` の使い方、`category` と `amount` 列が必要、分類ごとに合計して `カテゴリ,合計` を昇順出力、1 回の実行で 1 ファイル読み・書き込まない、引数なしなら usage 行を表示。

## 構成

ロゴ（既存の `assets/logo.svg`、`width="240"` で縮小表示）→ 概要 1 段落 → License バッジのみ（CI・公開パッケージは `ci: null` / `published_package: null` なのでバッジを省略）→ 主要導線は「Get started」と言語切替の 2 本だけ → 実行例（入力と出力を対にして提示）→ Get started → License。表格・特徴一覧・ロードマップは入れていません。

日本語版は `docs/` からの相対パスに直し、`[English](../README.md)` で相互リンクしています。

## 未実施・注意

指示どおり codex レビューと追加ヒアリングは省略しています。またシェルが使えないため `python3 sumcsv.py examples/expenses.csv` は実行していません。`sumcsv.py` の `DictReader` と `sorted(totals.items())`、`examples/expenses.csv` の内容（groceries 1200+300、books 800）を手Calculate したもので、出力は `books,800` / `groceries,1500` です。実行による確認が必要な場合は本地で試してください。