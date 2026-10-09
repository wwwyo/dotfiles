# Wiki への書き戻し

SKILL.md の保存先判定で wiki に該当するときだけ実行する。資料の要約や agent の推測をユーザーの理解として書かない。既存 wiki に repo の決定・プロセスがあっても、追記の前例にはしない。既存内容の移管・削除は今回の変更に必要な範囲か、明示された整理依頼の範囲で行う。

## Checkout と規約

- 書く前に対象 checkout の `AGENTS.md` と `wiki/AGENTS.md` を読み、schema・frontmatter・書き込み後チェックに従う。保存先の境界は SKILL.md に従う。
- cwd が me の checkout 内なら、その checkout を使う。別 repo からユーザー未見の変更を書き戻す場合は Orca CLI で me の worktree を切る。レビュー済みの変更の扱いは me/AGENTS.md に従う。canonical に自律変更を混ぜない。
- 非公開情報は `*.local.md` に分け、候補検索・リンク追加でも公開側へ固有名や本文を漏らさない。

## 更新と検証

1. 必要な domain だけ `rg` / router で重複を確認する。同じトピックがあれば既存ページを更新し、浅い・古い記述を今回の理解で refine する。新規ページのためだけに Map 全体や全 PJ を読まない。
2. ユーザーが自分の言葉で到達した理解を書く。学習ならフリーリコール・転移課題の答えを素材にする。repo の意思決定は ADR、プロセスは skill へ残し、wiki には必要な正本リンクだけを置く。PJ ページは個人の位置づけ・フォーカスに変化があるときだけ更新し、意思決定 log・作業進捗を積み上げない。
3. schema に従い frontmatter と節のメタデータ、domain index を更新する。`description` に YAML の `: ` があれば全体を double quote する。公開/非公開の index を分ける。log.md への追記等は現行 schema に要求がある場合だけ行う。
4. 関連ページがある場合だけ必要な相互リンクを加える。被リンクの確認は次のツールを使う。候補は本文の関係を確認してから貼り、全候補を読む・無理にリンクを作ることはしない。

```bash
python3 <このスキルのbase directory>/tools/wiki_links.py /tech/ontology.md --json
python3 <このスキルのbase directory>/tools/wiki_route.py links <page> --top 3 --json
```

`wiki_links.py` は Outbound（バンドル外は `(external)`、リンク切れは `(broken)`）と Backlinks を返す。標準外の bundle は `--root <path>` で指定する。`wiki_route.py` の `--root` は subcommand の前に置く。外部送信の制約は SKILL.md に従う。

5. 対象 checkout で検証する:

```bash
python3 .agents/skills/wiki-lint/tools/okf_check.py wiki
```

6. `git diff -- <更新ファイル>` と保存済みの該当箇所を読み直し、意図した内容・重複・破損・情報漏洩を確認する。ツール応答が途切れた場合も保存済みとみなさない。非公開の ignored ファイルは diff に出ないため、実ファイルで確認する。
7. 更新したページのパスと要旨を報告する。commit はユーザーの指示があるときだけ。

## Daily から切り出す場合

`daily/<date>/memo.md` は複数セッションが追記する共有ファイル。対象見出しから EOF まで機械的に取ると別の議論が混入する。対象見出しから次の同階層以上の見出し、`---` 区切り、または次の `## HH:MM` の直前までで範囲を明示し、切り出し後は daily の diff で対象範囲だけが削られたことを確認する。
