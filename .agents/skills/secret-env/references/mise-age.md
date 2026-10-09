# mise + age

## 運用前提

- API key / token は設定ファイルやリポジトリに平文で置かず、`mise set --age-encrypt` で age 暗号化して `mise.toml` の `[env]` に格納する。暗号文なので commit / 同期してよい。
- 復号鍵（age secret key）は生ファイルとして持たず、macOS Keychain（service=`mise-age-key`）にのみ置く。
- Keychain の age key は shell 起動時に `MISE_AGE_KEY` env へ注入し、mise がそれを使って復号する。

## 学び

- `~/.config/mise/age.txt` を削除して Keychain の `MISE_AGE_KEY` だけで運用している環境では、`mise set --age-encrypt` の新規暗号化時に recipient を自動導出できないため、`security find-generic-password -a "$USER" -s mise-age-key -w | age-keygen -y` で導出した値を `--age-recipient` に明示する。
- `age-keygen -y` が環境によって通らない（stdin の扱い・引数解釈差）場合の代替: `MISE_AGE_KEY` を 600 の temp file に書いて `mise set --age-encrypt --age-key-file <path>` に identity file として渡すと recipient 導出をスキップできる（用後は file を消す）。検証: 暗号化→`mise env` で復号値一致を確認済み。
- global config の `[env]` に置いた age 暗号文は全ディレクトリで復号・注入される。repo 配下だけに閉じたい secret は、その repo の `mise.toml` に同じ recipient で暗号化して置き、global 側から削除して scope を検証する。
- scope の変更（repo-local ⇄ global）は同一 recipient なら**暗号文をそのままコピーすれば済む** — `mise set --age-encrypt` で再暗号化すると平文を手元に出す必要が生じる。移設の検証は復号値の sha256 先頭数桁を移設前後で突き合わせれば、平文を画面に出さずに一致を確認できる。
- repo-local `mise.toml` へ secret を移した後は、原本一致・repo 内で env が出ること・repo 外で env が出ないことを確認してから global 側を消す。復号鍵は Keychain の age key 単一なので、Keychain を失うと全 age 暗号文が復号不能になる（鍵自体は別途バックアップして単一障害点を避ける）。
- 非対話に spawn されたプロセス（agent セッション等）では shell 起動 hook が走らず `MISE_AGE_KEY` 未注入のことがあり、`mise exec` しても `[env]` の age 暗号文が復号されず secret が空に見える。macOS では Keychain から値を表示・ファイル保存せず、そのプロセスの env にだけ渡して復号させる:

```bash
MISE_AGE_KEY="$(security find-generic-password -a "$USER" -s mise-age-key -w)" \
  mise exec -- sh -c '[ -n "$FISH_API_KEY" ] && echo present || echo missing'
```

  判定は presence boolean に留め、`env` ・config 全量・鍵値をログに出さない。`set -x` も使わない。これで `present` ならキーは登録済みで、不足しているのは復号鍵の注入だけなので再登録は不要。
- Context7 MCP は `CONTEXT7_API_KEY` env を読むため、Claude/Codex の MCP config に `--api-key` 平文を置かず `args = []` / `args: []` にして親プロセスの mise+age env を継承させる。
- `mise.toml` の `[env]` は mise activate 済みの対話 shell が対象 dir に `cd` したときにだけ shell env へ注入される。agent の desktop app / GUI ランチャーは自前でプロセスを spawn しこの経路を通らないため、`[env]` に平文/暗号文どちらを置いても効かない。確実に効かせたい env は対象アプリの起動経路に直接乗る設定へ置く — Claude Code なら `~/.claude/settings.json` の `env`、Devin Desktop の MCP なら `mcp_config.json` の command を `mise x -- <tool>` にして global config の env を注入させる。terminal から `mise activate` 済み shell 経由で起動する場合は従来どおり `[env]` が効く。
