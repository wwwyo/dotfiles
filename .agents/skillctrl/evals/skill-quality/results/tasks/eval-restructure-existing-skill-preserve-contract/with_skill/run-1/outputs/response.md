構造整理が完了しました。

## 変更した skill 一式（`fixture/packet-report/`）

| file | 内容 |
| --- | --- |
| `SKILL.md` | 共通契約（入力・出力・使える resource）だけに縮小。冒頭に「依頼_Read」表を置き、Create は `references/create.md`、Audit は `references/audit.md` だけを読む分岐を明示 |
| `references/create.md`（新規） | Create の手順を上書き確認 → helper 実行 → template 置換の順にし、終了条件（3値の含有・helper 出力と一致・placeholder なし・入力未変更）を列挙 |
| `references/audit.md`（新規） | 冒頭に read-only 契約（input CSV・report・template・helper を変更しない）を置き、expected/actual の比較手順と verdict 形式、および「修正依頼まで Create に進まない」終了条件を記載 |
| `references/legacy-notes.md` | 中身が create.md / audit.md と重複していたため、SKILL.md からの参照を削除し、空の転送 file に。**削除は未実施**（この task の file tool に delete が無いため置換のみ） |

未変更: `scripts/summarize.py`、`assets/report.md`（既存 helper と template をそのまま使用）、`samples/packets.csv`。`samples/packets.csv` は skill 外 sample のため参照せず。

## 保存したルール

`fixture/CHECKS.md` に記録しました。
- 維持した契約（名前・入力・出力・Audit の変更禁止・Create/Audit の終了条件・上書き確認・template は Audit で置換不可）
- 実際に確認したこと（静的読みのみ、原条項の移動先対応、fixture 全体検索で `legacy-notes` 参照ゼロ、参照先 file の存在、文言の不自然な混入の修正と再読）
- 確認していないこと（shell 不在により helper 実行・end-to-end・frontmatter parser 検証なし。指示どおり eval agent / benchmark は未起動、description は原文据え置きで triggering 精度は未評価）
- 次に残す判断（`legacy-notes.md` の削除）

外部 API・ネット検索・package install・commit/push は使わず、fixture 外は変更していません。