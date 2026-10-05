# computer-use

## 文脈

この環境の共通設定は GUI 操作に bundled computer-use plugin を使うが、remote skill は `orca computer` へ誘導している。

## 意図

通常の GUI 操作は bundled plugin に揃える。skill 自体の入口からこの経路を選べるようにし、別の dev-env を偶然読むことに依存しない。`orca computer` はその経路を明示的に指定された場合の選択肢として残す。

description に CLI/API では届かない GUI の用途と、通常の Orca browser 操作との境界を示す。実行手順は本文の経路選択に持たせる。
