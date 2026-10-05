# CHECKS

packet-report skill の構造整理。整理のみが目的で、振る舞いの変更はしていない。

## 変更した file

| file | 変更 |
| --- | --- |
| `packet-report/SKILL.md` | 書き直し。共通契約（入力・出力・使える resource）だけを残し、Create / Audit の手順を分岐先 file へ移し、「依頼_Read」の表で読む file と進めないことを明示した。 |
| `packet-report/references/create.md` | 新規。SKILL.md の Create 節の手順と終了条件を移し、手順の番号順にした。 |
| `packet-report/references/audit.md` | 新規。SKILL.md の Audit 節の手順と終了条件を移し、read-only 条件を冒頭に置いた。 |
| `packet-report/references/legacy-notes.md` | 内容を create.md / audit.md へ移したため、参照のない空 file にした。削除できるが、この task では file tool に delete がなく、置換のみのため残置。SKILL.md からの参照は削除済み。 |

変更していない: `packet-report/scripts/summarize.py`、`packet-report/assets/report.md`、`samples/packets.csv`。

## 維持した契約

- 名前: frontmatter の `name: packet-report`。
- 入力: UTF-8、header `packet_id,status,bytes`、packet_id は空でない一意文字列、status は ok/failed、bytes は0以上の整数。不正入力は非ゼロ終了で報告し、report を作成・上書きしない。入力ファイルを変更しない。
- 出力: `assets/report.md` の形式。件数は `scripts/summarize.py` の出力、手計算で置き換えない。
- 検査時の変更禁止: Audit は input CSV・report・template・helper を変更しない。差があれば該当行と expected/actual、なければ no findings。修正依頼まで Create に進まない。
- 終了条件: Create は helper 出力と report 値の一致と placeholder 除去まで、Audit は verdict を返した時点。
- Create の上書き確認、Audit で template を置換に使わない、という点も維持。

## 確認したこと（静的読みのみ）

- 3 つの reference file を読み返し、原 SKILL.md の各条項が移動先に対応し、脱落・捏造がないことを確認した。
- fixture 全体を検索し、`legacy-notes.md` への参照が残っていないことを確認した。
- SKILL.md が参照する file（`references/create.md`、`references/audit.md`、`scripts/summarize.py`、`assets/report.md`）がすべて存在することを確認した。
- 日本語の文中に不自然な語が混入した箇所を直し、書き直した file を再読して文言を確認した。

## 確認していないこと

- shell が使えないため、`scripts/summarize.py` の実行、`samples/packets.csv` での end-to-end、YAML frontmatter の parser 検証は行っていない。
- 指示どおり eval agent と benchmark は起動していない。description の triggering 精度は未評価で、`description` は原文のまま変更していない。
- 外部 API・ネット検索・package install・commit/push は使用していない。fixture 外の file は変更していない。

## 次の依頼に残す判断

- `references/legacy-notes.md` は delete 可能な空 file。file を消せる手段で削除する。
