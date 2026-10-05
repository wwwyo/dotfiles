# macOS アプリ install の code 管理

dotfiles でアプリを宣言管理する場所: `scripts/Brewfile`（cask・brew）、自前 tap `wwwyo/tap`、`run_once` script。「公式 cask が無い = 管理不可」ではない — 以下の順序で判断する。

## 判断順序

1. まず `brew info --cask <name>` と homebrew-cask の cask file を見る。**token 名だけでは判断しない** — `muse-code` は Meta のターミナル agent で desktop の Muse app ではない、といった名前衝突がある一方、`muse` cask は homepage が muse.ai でも `uninstall quit` の bundle id が `com.meta.endo` で実は目的の Meta 製アプリ、という逆向きのケースもある。homepage・bundle id で同一性を裏取りする
2. cask が無くても stable な非認証 download URL があるなら、自前 tap（`scripts/Brewfile` の `tap "wwwyo/tap"`）に数行の cask を足せば宣言的に管理できる。version 検出は `livecheck { strategy :sparkle }` で appcast を見ればよい
3. download URL が署名付きで expire する場合だけ最終手段: install 済み app の `Info.plist` の `SUFeedURL` から Sparkle appcast（無認証・常に最新 DMG を指す）を parse し、`run_once` script で install する

## 管理範囲の切り分け

Sparkle 同梱のアプリは自身が auto-update するので、管理範囲は初回 install だけに切るのが筋（update までコード化しない）。
