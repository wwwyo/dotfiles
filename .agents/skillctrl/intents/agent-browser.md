# agent-browser

## 文脈

この環境は Orca を使い、ブラウザ操作は Orca 内蔵 browser を優先する。汎用 skill の既定経路と共通設定が食い違うことがある。

## 意図

通常の Web 操作は Orca に揃える。agent-browser は、現在の環境で Orca では扱えない操作や、別 browser を明示的に指定された場合の選択肢として残す。

description は通常の Web 操作と fallback の境界を短く示す。長い能力列挙で Orca の既定経路と競合させない。
