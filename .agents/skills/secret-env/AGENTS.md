`secret-env` skill の保守規約。

- `SKILL.md` はルーターに徹し、知見本体は `references/` に置く。
- reference は 1 エントリ 1 行 bullet とし、secret の値・断片・識別可能な token prefix は書かない。
- 新規知見を追記するときは、既存 bullet と dedup し、コマンド・scope・失敗条件が検証可能な形にする。
- secret 管理の実装変更は、復号確認・scope 確認・平文残存検索を通してから記録する。
