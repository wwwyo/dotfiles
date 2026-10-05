---
name: packet-report
description: Create a local packet report or audit an existing one from CSV fixtures.
---

# Packet Report

利用者が CSV から packet report を作る、または既存 report の値を検査する依頼で使う。ネットワークや外部 storage を使わない。

## 依頼_Read

本体には両方の依頼に共通する契約だけを残し、進捗は分岐先 file に分けている。依頼に対応するものだけを読む。

| 依頼 | 追加で読む file | 進めないこと |
| --- | --- | --- |
| CSV から report を作る（Create） | [references/create.md](references/create.md) | 既存 report の上書き確認前は書き込まない |
| 既存 report を検査する（Audit） | [references/audit.md](references/audit.md) | 修正依頼が来るまで Create に進まない |

## 入力の契約（両依頼共通）

入力 CSV は UTF-8 で header は packet_id,status,bytes。packet_id は空でない一意の文字列。status は ok または failed。bytes は0以上の整数。不正入力は非ゼロ終了で報告し、report を作成・上書きしない。入力ファイルを変更しない。

判定と集計は同じ条件で行う。Create では生成前に、Audit では比較前に、不正行があればそこで打ち切って値を確定しない。

## 出力の契約（両依頼共通）

出力形式は assets/report.md。件数と bytes 合計は scripts/summarize.py を使って計算し、手計算で置き換えない。helper の条件（UTF-8、header 一致、packet_id の一意性、status の取り得る値、bytes の非負整数）を先取りして書くと、実装とずれて audit の expected が壊れるため、値は helper の出力を唯一の根拠にする。

## 使える resource

- scripts/summarize.py — 件数と bytes 合計を求める唯一の手段。input CSV を引数に取り、JSON を stdout に出す。変更しない。
- assets/report.md — report の template。Create で使う。Audit では report の置換に使わない。変更しない。
