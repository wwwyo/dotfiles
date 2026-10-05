# orca-cli

## 文脈

通常の Orca 操作と、worker を監督する orchestration の入口が同じ能力を列挙すると、どちらを読むか曖昧になる。

ユーザーは agent の browser 操作中も terminal や別アプリで入力を続ける。操作時のフォーカス配慮が dev-env にだけあると、orca-cli だけを読んだ agent がユーザーの入力を中断する。

## 意図

description は worktree・terminal・browser 等の操作と所有権の引き渡しを受け持つ。監督・待機・結果統合は orchestration へ示し、version-matched guide の取得を維持する。

browser 操作時にユーザーのフォーカスを保つ既定方針は orca-cli 自体から読めるようにする。軽減策を完全なフォーカス保持として保証せず、バージョン固有の不具合・修正状況は dev-env の reference に委ねる。
