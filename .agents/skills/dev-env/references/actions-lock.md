# GitHub Actions workflow lockfile（`.github/workflows/actions.lock`）

`gh-actions-lock`（mise で pin、`gh` extension ではなく単体 binary として呼ぶ）が生成する。workflow の `uses:` が指す commit を記録し、GitHub の runner は onboard 済み workflow をその commit で実行する。public preview で、lockfile 形式・flag は版で変わりうる。

- **`.github/workflows/` の全 workflow を onboard する**。v0.2.0 の `--verify` は lockfile に entry の無い workflow もエラーにするため、一部だけ onboard する運用は成り立たない
- **生成・更新は `gh-actions-lock --no-narrow` で行う**。flag 無しだと新規 pin の `@v7` を `@v7.0.1` に絞り、SHA 参照も tag 参照に書き換える。gh-aw の `*.lock.yml`（compile で SHA に戻る）と pullfrog.yml（編集禁止の生成物）を書き換えないために narrowing を止める。lockfile が commit を固定するので、workflow 側の参照を絞らなくても実行される code は変わらない
- **`uses:` を追加・変更・削除したら同じ変更で再生成する**。gh-aw の `gh aw compile` 後も対象。CI（`test.yml` の `actions-lock` job）の `--verify` が不一致と lock 済み commit の正当性を検出する
- **major tag（`@v7`・`@v0`）の追従は自動では起きない**。upstream の更新を取り込むときは `gh-actions-lock --relock` を明示的に回し、差分の commit を review する
