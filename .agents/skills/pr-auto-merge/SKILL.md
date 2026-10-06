---
name: pr-auto-merge
description: "wwwyo/* の open PR を triage し、QA・Blast Radius の根拠を確認して merge 可否と修正依頼を判断する routine。Orca automation または /pr-auto-merge で実行する。通常の単一 PR 作成・レビューには使わない。"
---

# pr-auto-merge (pr-merge-lane)

Orca automation `pr-auto-merge`（30分間隔・`workspace_path` = `wwwyo/me` 固定）
が駆動する routine。設計は `docs/prd/pr-merge-lane/prd.md`（dotfiles repo）、
実装は `tools/pr_triage.py`。

役割分担:

- **`tools/pr_triage.py`（script）** — 全 open PR の事実収集と、機械的に判定できる条件を担当する
  （path 3分類・unaddressed 判定・競合/依存 CI・移行修正検出・dispatch routing・hard gate・送信上限・
  worktree 削除条件）。`gate` が次の action を plan に出し、merge の発行直前にも条件を再検証する。
  action が無い tick では executor session を起こさない
- **executor session（これを読んでいる agent）** — plan の action を順に実行する。
  script の機械的な判定や dispatch 要否を覆さず、`merge` action は `pr_triage.py merge` で実行する。
  **`judge` action では、この agent 自身が LLM judge として内容を判定し、結果を登録する**
- **LLM judge（executor の役割）** — script が内容判断を委ねた PR について、
  [references/judge.md](references/judge.md) に従って QA・Blast Radius を評価し、
  `ok` / `ng` / `repair` を選ぶ。verdict は head SHA と判定時の本文・base・check 結果に紐付ける。
  merge の発行権は持たない

「script の判断に従う」は、script の条件を agent が独自に緩めたり、plan にない action を
追加したりしないという意味。**plan の `judge` は agent に内容判断を求める action であり、
`judge-input` の取得だけでは完了しない**。確認しても判断できない場合は、未確認事項を理由に
`ng` を登録する。

bot の依存更新のみの PR は、script が base/head の実 manifest 差分から全件の
更新種別を判定し、**全更新が minor/patch または devDependencies（major 含む）なら
LLM judge を介さず自動 ok** とする。runtime dependency の major、種別を確定
できない更新（range・タグ・downgrade・依存の追加削除・package.json 以外の
manifest、workflow 変更、rename を含むもの）、0.x 台の minor 更新
（breaking の可能性があるため major 扱い）、peerDependencies の更新
（consumer の依存解決に影響）、依存以外の差分を含む PR は
従来どおり judge が判定する。判定の材料は PR タイトルの自己申告ではなく
manifest の実差分。

## tick の手順（executor session）

1. plan を取得する:

   ```bash
   python3 ~/.agents/skills/pr-auto-merge/tools/pr_triage.py plan
   ```

2. `plan.prs[*].actions` を順に処理する。`dispatch` はレビュー指摘に加え、
   `CONFLICTING` と bot の依存 manifest・lockfile 更新に伴う CI 失敗、judge が必要とした major 更新への追従も対象。
   修正する author session は **references/repair.md** に従い、該当 PR・
   base・失敗ログだけを調べる。executor は dispatch 要否を再判断しない:

   | action | やること |
   |--------|---------|
   | `dispatch` | `pr_triage.py dispatch --repo <r> --number <n>` を呼ぶ。send / revive / spawn の解決・上限・dedup・delivery 検証は script がやる。結果が `needs_escalate: true` なら続けて `escalate` を呼ぶ。`defer`/`none` なら何もしない |
   | `escalate` | `pr_triage.py escalate --repo <r> --number <n>`（上限到達の旨を PR にコメントして打ち切り） |
   | `judge` | `judge-input` で diff・PR 本文・CI を取得し、**executor 自身が references/judge.md の基準で判定して** `judge-result --sha <sha> --context-hash <context_hash> --verdict ok\|ng\|repair --reason <理由>` に登録する。材料取得だけで終えない。判断不能なら理由付きで ng。**ok の登録結果が `merge_ready: true` なら、次 tick を待たず同じ実行内で続けて `merge` を呼ぶ**（`merge` が発行直前に hard gate を全件再検証する）。`merge_ready: false`（`blocked` の理由付き）なら merge せず、理由を report に残す。repair は次 tick の dispatch に渡す |
   | `merge` | `pr_triage.py merge --repo <r> --number <n>`。`blocked` が返ったら直前再検証で弾かれたので何もしない（状況が変わったサイン） |
   | `hold` | 何もしない。理由は report に載せる |

3. script は毎 tick local Orca の全 worktree/session を確認する。`plan.local_sessions`
   に確認件数、`plan.sweep` に片付け候補が入る。候補があれば `pr_triage.py sweep`。
   routine 外で merge された PR も対象。branch/head が merge 済み PR と一致・git clean・
   agent idle/done の worktree だけ、session を `orca terminal close --all` で閉じて削除する。
   live terminal がある場合は workspace completed・shell が prompt に戻っていることも必要。
   main・active workspace・子 worktree の親・作業中 agent は残す。削除直前に全条件を
   再検証し、close 後に live terminal が0になったことを確認する。force は使わない。
4. report を書く（下記）
5. 最後に必ず `pr_triage.py lock release --run-id <plan.run_id>`。
   `gate` が保持したまま渡した run lock を executor session が引き継ぐ
   形なので、正常終了・中断・エラーのどれでも release する。run_id で
   所有者を照合するため、TTL 超で stale 回収された後に release しても
   別 run の lock は消えない（残った lock は TTL 超で自動回収されるが、
   release しない間は次の tick が全部 skip される）

途中で script がエラーを返したら、その action を自分で代替実装せず
report に記録して次へ進む。

## judge の内容判断（executor が担当）

PR 本文の `Blast Radius` と `QA` を差分・検証結果と照合し、判定の根拠が確かかを確認する。
影響の深刻さ・検証状況・復旧可能性から、高なら hold、中なら影響に対応する検証が
済んでいれば merge 候補、低なら merge 候補とする。自己申告だけで低とせず、
根拠が不足して判断できなければ hold にする。詳細は [judge](references/judge.md)。
テストファイルの追加の有無ではなく、実施した QA で判断する。

`wiki/` は一律 hold にせず、通常の docs と同じ自動 merge 候補として扱う。
QA・Blast Radius の judge 判定と CI・レビューの hard gate を満たす必要がある。
`AGENTS.md` 等、wiki 以外の理由で常に hold となる path の規則は適用する。

## merge の発行経路（規約）

この routine の merge の発行経路は `pr_triage.py merge` のみ。script は
発行直前に hard gate（`state`・`mergeable`・unaddressed・required check・
pullfrog-approval・path 分類・judge verdict@head/判定材料 または script の
依存自動 ok・intent 永続化）を
全件引き直すので、`gh pr merge` 直叩きはこの再検証を迂回することになる。

`gh pr merge` の直接使用は禁止ではないが規約外として扱う — 緊急時だけ、
理由を PR に書く。draft PR は script が内部で `gh pr ready` してから merge
する（squash 固定・branch 削除付き）。

## report

`plan.report.md`（`wwwyo/me` の `daily/<date>/pr-watch.md`）は**人間が読む
日次レポート**で、PR の現在の決着と保留理由だけを書く。

Merge の掲載と merge 件数は、当日の jsonl に script の merge 成功実績が
ある PR だけを対象にする。本人による手動 merge は人間向けレポートに載せない。

`plan.report.jsonl`（同じ dir の `pr-watch.jsonl`）を**唯一のログ**とし、
script の action・judge・エラー実績と executor の長い判定根拠・参照URL・
状態再取得・次回への引き継ぎをここに集約する。`pr-watch-log.md` は生成・追記しない。
script の実績 event を手書き・編集せず、補足は `note` event で残す:

```bash
# JSON: message は必須。repo/pr/sha/sources/details は任意（schema 参照）。
# 長文・改行・URL を省略せず JSON ファイルに書く。
python3 ~/.agents/skills/pr-auto-merge/tools/pr_triage.py log --input /tmp/pr-watch-note.json
# 必要な補足だけを読む。--event は複数指定可、--limit は絞り込み後の最新件数。
python3 ~/.agents/skills/pr-auto-merge/tools/pr_triage.py events --event note --limit 10
```

例: `{"message":"再取得で head の変更を確認。次回は新しい head で再判定する。",
"repo":"wwwyo/example","pr":1,"sha":"確認した head",
"sources":["https://github.com/wwwyo/example/pull/1"]}`。
`note` は補足ログであり action・verdict・送信成功・merge 実績を変更しない。
空振りや tick ごとの件数を重複記録せず、次回に必要な情報だけ補足する。
既存 `pr-watch-log.md` の移行時は、原文と元ファイルの日付・path を `note` に
保持して読み戻しを確認してから旧ファイルを削除する。過去の実績 event として再生成しない。

dispatch は修正依頼を送った中間状態で、PR の決着ではない。dispatch の
見出し・件数・成果一覧は md と最終返信に載せず、送信履歴は jsonl に残す。
修正待ちの open PR は Hold にまとめ、待っている理由を書く。

```markdown
# PR Watch — YYYY-MM-DD

merge N 件 / hold K 件 / error E 件

## Hold
（merge されなかった open PR を 時刻（JST）|repo|PR|理由 の表で。always-hold path・
judge ng・CI 待ち・dispatch 済みで author 対応待ちなど。judge ok 登録済みだが
残りの機械的条件（approval・CI・mergeable 等）を待っている PR は
「judge ok 登録済み・<条件>待ち」と書き、「script判定待ち」のような曖昧な
説明にしない。judge verdict は
head SHA ごとに記録されるため同じ PR は1行に集約し、当日の試行回数と
最新 verdict を理由に書く — jsonl は日ごとのファイルなので、
日をまたいだ履歴は `daily/<date>/` を遡る。judge ng が同じ head に
固定されて滞留する PR（人間の判断が必要な変更など）
は理由にそれを明記する）

## Error
（tick_error・script 失敗があった日だけ。時刻（JST）|内容 の表で）

## 修正
（競合・依存 CI を実際に修正して push した PR を 時刻（JST）|repo|PR|内容・根拠 の表で）

## Merge
（その日 routine が merge した PR を 時刻（JST）|repo|PR|内容 の表で。Merge は常に
レポートの最下部に置く）
```

- 全ての表に独立した `時刻（JST）` 列を置き、時刻の降順（新しい順）で並べる。
  Hold は最後に状態・理由を確認した時刻、Merge は GitHub の `mergedAt`、
  Error はイベントの発生時刻、修正は修正を確認した時刻を使う。
  日付が当日と異なる時刻は日付も併記する。確認できない時刻は「未確認」として末尾に置く。
- head SHA は `pr-watch.md` に載せない。列・理由・内容への埋め込みも避け、
  判定と head の対応・長い根拠・引き継ぎは jsonl に残す。
- session・worktree の確認・片付け状況は日次レポートに載せず、`## Session` 節も作らない。
  監査は script が記録する jsonl を参照する — 片付け実績（`sessions_closed` /
  `worktree_rm`）・残した理由（`sweep_skipped`・上限到達で `sweep_giveup`）・
  確認件数（`local_sessions_checked`）が残る。次 tick への引き継ぎが必要な
  情報だけ jsonl の note に残す
- hold の理由が主役（1行で読めること）。該当の無い節は出さない
- report 更新直前に、plan の PR と既存 Hold の state・head・mergedAt を GitHub から
  取り直す。MERGED は Hold から外し、当日の routine の merge 実績がある場合だけ
  Merge に移す。CLOSED も Hold
  から外す。取り直しで plan 後に変わったと分かったものは TOCTOU として
  jsonl の note に記録し、md には書かない。action は追加しない。
  取り直し自体に失敗した PR は TOCTOU の一覧とは別に扱い、取得を試みた時刻つきで
  「未確認」を md の当該行に書く（時刻ごと md 側に残す）。現在 open と断定
  しない。過去の失敗は Error に残す。
- judge ng の理由は Hold の理由列に1行で書き、判定根拠・検証手順の長い
  記述は jsonl の note に置く（md の節の外に段落をぶら下げない）
- 競合・依存 CI を実際に修正して push したものは `## 修正` に根拠付きで載せる。
  修正依頼の送信だけではこの節に載せない。cooldown 待ちは Hold に解除日時を書く
- `orca file open` で開くのは merge があった日だけでよい（hold だけの日は開かない）

major は公式の変更内容と実際の利用箇所を照合して判断する。bot_dep 経路で
明らかに非該当なら追加の実行検証なしで ok とするが、check が fail している
場合は失敗と更新の無関係を確認してから ok にする（required 以外の fail も対象。
CI が無い・未実行・skip は妨げにしない）。影響がある・仕様と設定だけでは
判断できない場合に検証し、対応が必要なら repair とする。修正後の新 head の
全差分・CI を再判定する。breaking 記述だけで ng にしない。判定規則の変更時は
script の policy version も更新し、旧 verdict を次 tick の再判定へ戻す。

file の3分類は script が適用する。diff サイズは判定条件にせず、依存・tool の
lockfile は分類・内容判定から除外する（GitHub Actions の `*.lock.yml` は workflow）。
mise の `.config/mise/config.toml` と chezmoi の `home/dot_config/mise/config.toml`
は tool pin の manifest として judge に回す。`.github/workflows/` も
github-actions ecosystem の依存置き場として judge に回し（`*.lock.yml` は
生成物で常に hold）、bot の manifest・lock・workflow のみなら、
script の依存自動 ok または current head の judge ok の後は
pullfrog-approval を免除する。

## references

| ファイル | 読むタイミング |
|---------|---------------|
| `references/judge.md` | plan に `judge` action があるとき |
| `references/repair.md` | dispatch 先が競合・依存 CI・major 更新の追従を調査/修正するとき |
| `tools/pr_triage.py` の docstring / `schema` subcommand | script の挙動を確認したいとき |

## 運用上の前提

- `gh` はネットワーク/認証が要るので sandbox 外で実行する
- `pullfrog-approval` が absent・fail でも直ちに異常としない。bot の
  manifest・lock・workflow だけの PR は script の依存自動 ok または
  judge ok で免除済み（上記の規定）。
  それ以外で review が届かない head は人手介入が要る
- script の失敗（API エラー）は fail-closed: その tick では merge も
  worktree 削除もしない。再試行は次の tick に任せる
- dispatch の delivery 検証で `turn_started not observed` は turn 未起動の
  サイン。receipt に request ID があれば `--retry-request` で同 tick に一度
  冪等再送し、無ければ送信カウントを進めず失敗を記録して終了（次 tick の
  再送対象）。単発なら既知のノイズ、繰り返すなら dispatch 先側の問題として
  escalate の判断材料にする
- always-hold path の分類は bot の manifest bump にも効く。hold segment
  配下の manifest を更新する Dependabot PR は lane 上では必ず hold で、
  `pr_triage.py merge` の hard gate は解除しない — merge するなら明示指示に
  基づく `gh pr merge` で、規約どおり理由を PR に書く
- 送信上限（同一 head 3回・往復 3 ラウンド）に達した PR は escalate 済み
  として扱い、routine はそれ以上 dispatch しない
