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
追加したりしないという意味。ただし、`judge-result` の `merge_ready: true` に続く
同実行の `merge` と、merge 成功直後の `sweep` は、以下で定める固定手順であり
独自の action 追加ではない。**plan の `judge` は agent に内容判断を求める action であり、
`judge-input` の取得だけでは完了しない**。確認しても判断できない場合は、未確認事項を理由に
`ng` を登録する。

bot の依存更新のみの PR は、script が base/head の実 manifest 差分から全件の
更新種別を判定し、**全更新が minor/patch または devDependencies（major 含む）なら
LLM judge を介さず自動 ok** とする。runtime dependency の major、種別を確定
できない更新（range・タグ・downgrade・依存の追加削除・下記 mise を除く package.json 以外の
manifest、workflow 変更、rename を含むもの）、0.x 台の minor・0.0.x 台の patch 更新
（breaking の可能性があるため major 扱い）、peerDependencies の更新
（consumer の依存解決に影響）、依存以外の差分を含む PR は
従来どおり judge が判定する。判定の材料は PR タイトルの自己申告ではなく
manifest の実差分。

mise の `[tools]` は開発用依存（devDependencies 相当）として扱う。Renovate と Dependabot に同じ規則を適用し、`mise.toml`・`.mise.toml`・`.config/mise/config.toml`・`home/dot_config/mise/config.toml` の固定 semver pin 更新だけなら、major・0.x minor・prerelease の更新を含め script が自動 ok とする。同じ dir の `mise.lock` は対応 manifest の写像として除外する。tool の追加/削除・downgrade・range/alias・installer option・`[settings]`/`[env]` 等の変更が混ざるものは judge に残す。CI・review・always-hold・merge 直前の再検証は維持する。

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
   | `dispatch` | `pr_triage.py dispatch --repo <r> --number <n>` を呼ぶ。revive / spawn の解決・上限・dedup・delivery 検証は script がやる。結果が `needs_escalate: true` なら、返された `reason` を `--reason` に渡して続けて `escalate` を呼ぶ。`defer`/`none` なら何もしない。`dispatched: false` の `reason` が stale plan（plan 取得後に指摘が解消された）でも失敗ではない — 再送・独自回復せず次 tick に委ねる |
   | `escalate` | `pr_triage.py escalate --repo <r> --number <n>`（上限到達の旨を PR にコメントして打ち切り）。戻り値の `handle`（実査する terminal）を report の該当行に書く |
   | `judge` | `judge-input` で diff・PR 本文・CI を取得し、**executor 自身が references/judge.md の基準で判定して** `judge-result --sha <sha> --context-hash <context_hash> --verdict ok\|ng\|repair --reason <理由>` に登録する。材料取得だけで終えない。判断不能なら理由付きで ng。**ok の登録結果が `merge_ready: true` なら、次 tick を待たず同じ実行内で続けて `merge` を呼び、`merged: true` なら直後に `sweep` を呼ぶ**（`merge` が発行直前に hard gate を全件再検証する）。`merge_ready: false`（`blocked` の理由付き）なら merge せず、理由を report に残す。repair は次 tick の dispatch に渡す |
   | `merge` | `pr_triage.py merge --repo <r> --number <n>`。`merged: true` を確認したら直後に `pr_triage.py sweep` を呼ぶ（開始時の `plan.sweep` が空でも必須）。`merged: false` / `blocked`・失敗・成功未確認なら、merge 後の sweep は呼ばず理由を記録する。`ok: true` だけでは merge 成功ではない |
   | `hold` | 何もしない。理由は report に載せる |

3. script は毎 tick local Orca の全 worktree/session を確認する。`plan.local_sessions`
   に確認件数、`plan.sweep` に開始時点の片付け候補が入る。**各 merge 成功直後には、
   通常の merge action・judge ok からの同実行 merge のどちらも、同じ実行内で
   `pr_triage.py sweep` を必ず呼ぶ**。`sweep` 自身が最新状態から候補を再計算するため、
   開始時の `plan.sweep=[]` を理由に省略しない。開始時に候補があった場合は merge の
   成否とは独立して tick 末尾に sweep する。ただし、この tick で merge 後の sweep を
   1回でも実施済みなら tick 末尾の分だけ省略する。各 merge 成功直後の分は省略しない。
   永続的な skip の上限は呼び出し回数で進むため、複数 merge の tick では従来より
   早く上限に達し得る。追加 retry はせず、既存の上限を維持する。
   routine 外で merge された PR も対象。branch/head が merge 済み PR と一致・git clean・
   agent idle/done の worktree だけ、session を `orca terminal close --all` で閉じて削除する。
   live terminal がある場合は workspace completed・shell が prompt に戻っていることも必要。
   main・active workspace・子 worktree の親・作業中 agent は残す。削除直前に全条件を
   再検証し、close 後に live terminal が0になったことを確認する。条件を通すためだけに
   workspaceStatus を completed に変えたり、force 削除したりしない。
   sweep の実施と削除成功は区別する。`removed` / `skipped` は sweep の出力で確認する。
   jsonl には `worktree_rm` と `sweep_skipped` が残るが、同一 worktree・理由の連続 skip は
   重複記録されない。呼び出した事実・削除件数・エラーは `pr_triage.py log` の note に
   記録する。残存理由が出力にない場合は、`orca worktree ps --json` と必要に応じ
   `orca terminal list --worktree id:<worktreeId> --json` で merge した PR の worktree を
   再確認し、active・作業中・live terminal があり未 completed 等の理由を note に補う。
   確認できなければ未確認と書き、削除成功に数えない。sweep / log と状態確認の Orca コマンドは、Orca socket・
   GitHub・state dir（`~/.local/state/pr-watch`）・jsonl 保存先へアクセスできる環境で実行する。sandbox に阻まれる場合は
   `gh` と同じく sandbox 外で実行し、権限設定を一律に緩めない。
   sweep 失敗で merge 成功を取り消さず、代替実装もしない。log も失敗したら報告に残す。
4. report を書く（下記）
5. 最後に必ず `pr_triage.py lock release --run-id <plan.run_id>`。
   `gate` が保持したまま渡した run lock を executor session が引き継ぐ
   形なので、正常終了・中断・エラーのどれでも release する。run_id で
   所有者を照合するため、TTL 超で stale 回収された後に release しても
   別 run の lock は消えない。TTL は tick 間隔より短いので、release せずに
   死んだ lock は次の tick で stale 回収され、止まるのは死んだ tick の分だけになる

途中で script がエラーを返したら、その action を自分で代替実装せず
report に記録して次へ進む。

## dispatch の作業中ガード

`gate` と `dispatch` が同じ条件で延期を判定し、`dispatch` は実行時に PR・
Orca worktree/terminal 一覧・git status を取り直す。次のいずれかなら送信・復帰・新規起動をしない:

- PR の更新（`updatedAt`・作成時刻・head commit 時刻の最新）から1時間未満。
  古い commit の push も拾うため `updatedAt` を使うので、コメント・レビューでも待機が延びる。
  時刻を取得できない場合も延期する。
- 対象 worktree の agent が working、live/状態不明 terminal が存在する、または
  terminal 一覧に接続中/接続不明の terminal がある。agentIdentity・writable・idle 表示に
  依存せず、shell も占有扱いにする（別 cwd から動く Claude subagent は status だけでは見えない）。
- 対象 worktree の index・tracked/untracked に変更がある、または clean を確認できない。
  remote host の git status はこの script では確認できないので延期する。

この節は PRD の旧 routing（idle terminal への再送・即時 spawn）に優先する。
旧「指摘発生から45分未満」は、このガードの合否条件には使わない。

現行の jsonl の `dispatch` event は送信成功を記録するが、指摘ごとの識別子・
起点時刻・送信対象との対応を保存しない。`repo` / `pr` / `sha` と後続の送信時刻や、
種別の集合である `kinds` だけから、当時の対象を一意に復元することはできない。
GitHub の現在の resolved 状態や author の後続活動を当時の状態として代用せず、
指摘と dispatch を推定で対応付けて伝達時間を算出しない（待機込みの時間も含む）。
計測を再開するには、送信時に選別された起点の識別子・時刻と成功送信との対応を
監査可能に記録し、PRD と集計仕様を別途整える。この PR では計測機能を追加しない。

延期 event は jsonl に残らない。plan と日次 Hold 表には確認時点の理由と、
算出できる場合の PR 更新待機の期限を表示するが、更新される状態表示であり、
延期履歴や実際のガード解除時刻の記録としては扱わない。延期の状況は Hold 表で
定性的に追い、ガード解除後の伝達時間や待機時間だけを分離して算出しない。
往復上限は terminal 閉鎖後に新しく修復を起動する場合も含めて適用する。

延期は送信回数を消費しない。使い終えた terminal は利用者が閉じるまで占有として残る。
draft への修復 dispatch 自体は従来どおり対象だが、このガードを満たす必要がある。
draft の judge/merge は引き続き hold。repo 固有の heavy.lock は汎用ガードには使わない。
判定直後に別 session が起動する race を完全に防ぐ共有ロックではないため、修復側も
書き込み開始前に [repair](references/repair.md) の確認を行う。

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
理由を PR に書く。**draft PR は lane では merge しない** — plan が draft を
hold し、hard gate も `isDraft` を弾く（plan 後に author が draft 化した
場合や judge-result の同一実行 merge の race も含む）。author の ready 化後に
通常の判定へ回る。merge は squash 固定・branch 削除付き。

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
# 短い補足は flag で直接流す（JSON を組み立てる helper を書かない）
python3 ~/.agents/skills/pr-auto-merge/tools/pr_triage.py log \
  --message '再取得で head の変更を確認。次回は新しい head で再判定する。' \
  --repo wwwyo/example --pr 1 --sha '確認した head' \
  --source https://github.com/wwwyo/example/pull/1
# 長文・改行・URL を多く含む補足は JSON ファイル（message 必須）
python3 ~/.agents/skills/pr-auto-merge/tools/pr_triage.py log --input /tmp/pr-watch-note.json
# 必要な補足だけを読む。--event は複数指定可、--limit は絞り込み後の最新件数。
python3 ~/.agents/skills/pr-auto-merge/tools/pr_triage.py events --event note --limit 10
```

例: `{"message":"再取得で head の変更を確認。次回は新しい head で再判定する。",
"repo":"wwwyo/example","pr":1,"sha":"確認した head",
"sources":["https://github.com/wwwyo/example/pull/1"]}`。
`note` は補足ログであり action・verdict・送信成功・merge 実績を変更しない。
merge 後 sweep の実施結果は削除0件でも note に残す。それ以外の空振りや
tick ごとの件数を重複記録せず、次回に必要な情報だけ補足する。
既存 `pr-watch-log.md` の移行時は、原文と元ファイルの日付・path を `note` に
保持して読み戻しを確認してから旧ファイルを削除する。過去の実績 event として再生成しない。
**note の JSON を組む独自 helper を書かない** — キーを取り違えた helper は
executor 自身の例外になり、tick の作業を巻き戻す（実例: `KeyError` を直して再実行）。
`--message` 等の flag か `--input` のファイルのどちらかで渡す — 余剰キー・型不正は
script が構造化エラーで弾く。

- **executor の最終 assistant 出力の末尾に、tick の結果を1行に要約した固定行を必ず置く**。
  jsonl の代替ではない — Langfuse の transcript だけを見る評価・監視が md・jsonl を
  開かずに tick の判断を再構成するための要約。`plan` と当日の jsonl から作り、次の形を守る:

  ```text
  tick-summary: date=<YYYY-MM-DD> run_id=<plan.run_id> dispatch=<n> escalate=<n> judge=<n> merge=<n> hold=<n> sweep=<n> error=<n> judge_ok=<n> judge_ng=<n> judge_repair=<n> blocked=[<理由>:<n>,...]
  ```

  `sweep` はこの tick の sweep 出力の `removed` 件数の合計で、呼び出し回数ではない。
  jsonl で照合する場合は `ts >= plan.generated_at` の `worktree_rm` に絞り、
  この実行の sweep 出力と worktree を照合する（同時刻の手動 sweep を混ぜない）。
  sweep 実施済みでも `removed=[]` なら 0 とし、実施・残存理由は jsonl の note を参照する。
  `hold` は plan の hold action 件数。`judge_ok`・`judge_ng`・`judge_repair` は
  `event == "judge"` かつ `ts >= plan.generated_at` の event だけを数える — 当日の
  jsonl には前 tick の judge event も入るため、時刻で絞らないと件数が膨らむ。
  `blocked` は同じ絞り込んだ judge event の `blocked`（judge-result が ok でも hard
  gate が通らず `merge_ready: false` のときに残る理由の配列）を理由ごとに数える
  （`pullfrog-approval not success`・`judge ok stale`・`draft` など）。該当の無い
  field は 0・`[]` とし、行自体は省略しない。長い根拠は従来どおり jsonl の `note` に残す。
  `pr-watch.md` の件数見出しは**当日累計**（当日 jsonl 全体）、tick-summary は
  **per-tick** — 両者が一致しなくても不整合と読まない（後続 tick が同じ日次 file に追記する）。
  同じ理由で、md は後続 tick が Hold 行を書き換える（MERGED・他アクターの merge を外す）ため、
  ある時点の md に行が無いことを「未実施」の証拠にしない — 実施の有無は jsonl の
  action・note で確認する。

dispatch ガードの延期も Hold に載せ、恒久的な保留と区別して日本語で理由を書く。
以下の表は dispatch ガード延期の `reason` だけを対象とし、返された理由以上の原因を
推測しない。送信上限・既送・author 非対象など、他の Hold 理由をこの表の待機理由へ置き換えない。

| `reason` | Hold に書く理由 |
|----------|----------------|
| `PR activity timestamp unavailable` | PR 活動時刻を確認できないため待機 |
| `PR recently updated; defer until <UTC>` | PR 更新後の待機（更新待機の期限 YYYY-MM-DD HH:mm JST） |
| `agent working or terminal live/unverifiable` | 作業中または terminal 占有・状態不明のため待機 |
| `worktree cleanliness unavailable` | worktree が clean か確認できないため待機 |
| `dirty worktree` | 未確定の変更があるため待機 |

`reason` 内の部分文字列 `defer until <UTC>` を JST に変換する。これは PR 更新待機の
期限であり、他のガードも含めた実際の解除時刻ではない。時刻のない理由に期限を
推測して付けず、worktree の確認不能だけから一時的・恒久的とも断定しない。

dispatch は修正依頼を送った中間状態で、PR の決着ではない。dispatch の
見出し・件数・成果一覧は md と最終返信に載せず、送信履歴は jsonl に残す。
修正待ちの open PR は Hold にまとめ、待っている理由を書く。Hold 表の行数が plan の hold 件数より多いのは正常（dispatch 済みで author 対応待ちの PR も Hold に載る）— tick-summary の `hold=` と突き合わせて不整合と読まない。

```markdown
# PR Watch — YYYY-MM-DD

当日累計: merge N 件 / hold K 件 / error E 件

## Hold
（merge されなかった open PR を 時刻（JST）|repo|PR|理由 の表で。always-hold path・
judge ng・draft（author ready 待ち）・CI 待ち・dispatch 済みで author 対応待ちなど。judge ok 登録済みだが
残りの機械的条件（approval・CI・mergeable 等）を待っている PR は
「judge ok 登録済み・<条件>待ち」と書き、「script判定待ち」のような曖昧な
説明にしない。judge verdict は
head SHA ごとに記録されるため同じ PR は1行に集約し、当日の試行回数と
最新 verdict を理由に書く — jsonl は日ごとのファイルなので、
日をまたいだ履歴は `daily/<date>/` を遡る。judge ng が同じ head に
固定されて滞留する PR（人間の判断が必要な変更など）
は理由にそれを明記する）

## Error
（tick_error・script 失敗・dispatch の revive/spawn 失敗があった日だけ。
時刻（JST）|内容 の表で。plan の action を処理しきった=送信成功ではない — 
失敗した dispatch はここに明記し、Hold の理由にも残す）

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
- **PR は必ずリンクで書く**。repo 列がある表（Hold・修正・Merge）は PR 列を
  `[#<n>](https://github.com/<repo>/pull/<n>)`、repo 列が無い本文（Error の内容など）は
  `[<repo>#<n>](https://github.com/<repo>/pull/<n>)` にする。URL は repo と番号から
  常に組み立てられるので、裸の `#<n>`・リンクでない `<repo>#<n>` を残さない。PR 列は
  リンクだけにし、PR タイトルは理由・内容の列の先頭に置く。
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
- 失敗の断定と未取得・未検証を混ぜない。API ・check が取れなかった、
  確認できなかったは「未取得」「未確認」と書く。billing 障害・infra 障害・
  upstream の不具合のような原因断定は、API 応答・status page・upstream の
  issue 等の根拠を引いたときだけ書く — 「動かなかった」だけの観測を
  原因の断定として書かない
- 競合・依存 CI を実際に修正して push したものは `## 修正` に根拠付きで載せる。
  修正依頼の送信だけではこの節に載せない。[セキュリティ修正の例外](references/repair.md#cooldown)で修正したものも `## 修正` に載せ、それ以外の cooldown 待ちは Hold に解除日時を書く
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
- dispatch の delivery が未確認なら、入力が届いた可能性があるため pending を
  残し、自動再送せず reason 付き escalate とする。terminal を確認してから復旧する
- 依存 manifest・lockfile は置き場所ではなく file 種別で分類する。
  `apps/api/package.json` のように hold path 配下にあっても always-hold には
  ならず、bot の依存更新のみなら自動 ok 判定、それ以外は judge に進む。
  manifest と同じ PR で hold path の非依存 file を触る場合は従来どおり hold
- 送信上限（同一 head 3回・往復 3 ラウンド）に達した PR は escalate 済み
  として扱い、routine はそれ以上 dispatch しない

## pi の送信確認

修復 worker の新規・復帰起動は delegate の worker/personal からモデル・thinking を読み、mise 経由の pi 対話 session に指定する。Orca が `turn_started` を返さない local pi では、対象 cwd の session JSONL に今回の固有 delivery marker を持つ新しい user input と、その後のエラー・中断ではない、内容のある assistant generation があることを script が確認する。本文は報告に出さない。入力受付だけを成功とせず、直接 CLI の dispatch も lock で直列化し、送信前に pending を保存するため、中断・未確認時も同じ head へ自動再送しない。remote host・独自 session dir などで確認できない場合は reason 付き escalate とし、terminal を実査してから復旧する。`dispatch_failed`（名目 turn_started not observed）は未送信の確定ではない — `worktreePath` 欠落や観測窓より遅い generation でも起こる。escalate した PR の実査は、report の `handle` から terminal の `agentIdentity` / `worktreePath` と、対象 worktree の session JSONL に delivery marker 付き user input と後続 generation があるかを先に見る。
