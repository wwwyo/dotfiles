# langfuse

## 文脈

CLI と環境変数は dotfiles の mise と暗号化された秘密管理で復元する。unpinned な npx/bunx と平文 .env の案内はこの運用を迂回する。

## 意図

API 操作・計測・prompt 移行の起動条件を明確にする。CLI と SDK の導入、認証の案内は共通設定と secret-env を参照し、原本の API discovery と計測手順は保つ。

CLI の共通 pin も dotfiles に同梱し、設定済みであることを前提にする前に導入を案内する。公式が推奨する package 名を使い、executable 名とは区別する。
