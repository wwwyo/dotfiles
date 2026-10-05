<p align="center">
  <img src="../assets/logo.svg" alt="Sumcsv" width="240">
</p>

# Sumcsv

支出や売上を CSV で管理していて、カテゴリごとの合計だけ知りたい、というときに表計算ソフトを開かずにターミナルで集計できます。Python の標準ライブラリだけで動く 1 つのスクリプトで、インストールは不要、CSV がローカル環境の外に出ることもありません。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](../LICENSE)

[English](../README.md) · [すぐに試す](#すぐに試す)

`examples/expenses.csv` を集計すると:

```csv
category,amount
groceries,1200
books,800
groceries,300
```

```console
$ python3 sumcsv.py examples/expenses.csv
books,800
groceries,1500
```

## すぐに試す

Python 3.11 以降が必要です。Sumcsv はソースだけで配布しているので、リポジトリをダウンロードまたは clone してそのディレクトリで実行してください。インストール手順はありません。

```console
$ python3 sumcsv.py examples/expenses.csv
```

1 行ずつ `カテゴリ,合計` の形式で、カテゴリ名の昇順に出力するので、他のコマンドに繋いだりファイルに書き出したりできます。引数なしで実行すると usage の行が表示されます。

自分のファイルに使う前に、次の点を確認してください。

- ヘッダーに `category` と `amount` の列が必要です。それ以外の列は無視されます。
- `amount` は整数である必要があります。小数点、カンマ区切り、通貨記号があると処理が中断するので、先に変換してください。
- 一度の実行で読むファイルは 1 つで、書き換えることはありません。

## License

Licensed under the [MIT license](../LICENSE).
