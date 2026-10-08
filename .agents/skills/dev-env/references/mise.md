# mise の設定と落とし穴

tool の pin・env・secrets 注入は global config で一元管理する。正本は dotfiles の
`home/dot_config/mise/config.toml`（→ `~/.config/mise/config.toml`、symlink なので
repo 編集が即反映）。supply chain 対策として `pin = true` + `minimum_release_age = "7d"`
を敷いている。`mise --help`・docs で分かることは書かない。

## 落とし穴

- `minimum_release_age` は version 解決（`@latest` 等の range 指定）にだけ効く。
  exact pin（`mise use tool@1.2.3`・config 直書き）は公開直後の版でもそのまま入る
  — pin する版の publish 日時は registry で確認してから書く。定期更新の自動化も
  cooldown は自分で確認しないと守られない
- `mise use` は cwd から見える config file を書き換える。repo の `mise.toml` がある
  dir で実行すると global tool の追加・pin 更新まで repo 側に書き込まれて汚染する。
  global の変更は `home/dot_config/mise/config.toml`（`mise use -g` と同じファイル）
  を直接編集する運用で統一する
- untrusted な repo config は読み込みを skip されて global 側の版に黙って
  fallback しうる（tool version が静かにずれる典型原因）。skip されるのは
  `[env]`・option/template 付き `[tools]` 等の trust 必須 config を、自動 trust
  しない discovery 系 command から読む場合 — plain な `[tools]` だけの config は
  trust 不要で、`install`/`exec`/`run` 系は active config を自動 trust する。
  `mise trust` は main checkout に掛ければ linked worktree に共有される。script
  から `MISE_TRUSTED_CONFIG_PATHS` に渡すのは内容確認済みの config に限る —
  trust した config は `[env]`・hook で任意 code を実行しうる
- tool と同名の wrapper script を PATH に置くと、wrapper 内から shim 経由で同じ名前を
  呼んで自己再帰する。wrapper 内では `mise exec <tool>@<ver> -- <bin>` で shim を
  介さず実体を呼ぶ
- shim が存在しても tool 本体が解決できなければ `mise ERROR <tool> is not a valid
  shim` で落ちる（shim あり・実体なし/未 install）。切り分けは `mise exec -- <tool>
  --version`（shim 経路が通るか）→ `mise ls`（install 済みか）の順
- HOME/XDG を差し替えて子プロセスを隔離する設計では mise shim が壊れる — shim は
  config・tool 解決に HOME を使うため。隔離側で tool を動かすなら、元の HOME で
  `mise bin-paths` を実行して得た実体 dir を子プロセスの PATH で shim より前に置く
- ユーザー自身の対話 shell に step-by-step でコマンドを実行させる案内では、環境確実化の
  prefix（`mise exec --` 等）を「省略可」と即答しない。agent の shell とユーザーの
  shell で mise の活性化状態が違いうる — 相手の環境を確認してから外す
- `go:<import path>` backend（例: `go:github.com/<owner>/<repo>`）は release/tag なしに
  exact commit で pin できる（pseudo-version は commit 由来で provenance を示す）。
  公開 release より新しい code が要るとき・cooldown が効く場面の選択肢。この backend の
  mise.lock entry は checksum を持たないため commit pin 自体が integrity anchor — CI で
  検査するなら 40-hex commit と lock entry の一致を見る。backend 切替時は旧 backend の
  install を残さない（別 format の install state を誤読しうる）
