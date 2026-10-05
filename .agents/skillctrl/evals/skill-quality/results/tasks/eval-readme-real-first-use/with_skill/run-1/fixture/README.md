<p align="center">
  <img src="assets/logo.svg" alt="Sumcsv" width="240">
</p>

# Sumcsv

If you keep your spending or sales in a CSV and just want to know the totals per category, Sumcsv gives them to you from the terminal instead of a spreadsheet. It is one Python script: standard library only, nothing to install, and your CSV never leaves your machine.

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[Get started](#get-started) · [日本語](docs/README.ja.md)

Given `examples/expenses.csv`:

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

## Get started

Requires Python 3.11 or later. Sumcsv ships as source, so download or clone the repository, `cd` into it, and run the script — there is no install step.

```console
$ python3 sumcsv.py examples/expenses.csv
```

The command prints one `category,total` line per category, sorted by category, so you can pipe it into another tool or redirect it to a file. Run it with no argument to see the usage line.

Before you point it at your own file:

- The header needs `category` and `amount` columns; other columns are ignored.
- `amount` must be a whole number. Values with decimals, thousands separators, or a currency symbol stop the run — convert them first.
- It reads one file per run and never writes to it.

## License

Licensed under the [MIT license](LICENSE).
