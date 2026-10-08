# Skill quality evaluation

継続管理するのは、評価ケース・採点基準・runner・current skill の結果。
通常実行は指定commitのskillだけを評価する。比較が必要な変更では `--before` を指定し、
baselineは一時workspaceで実行する。oldのrunはこのtreeに保存しない。

## 保存している結果

2026-10-02、Pi 0.87.1、`opencode-go/space-bunny-free`、thinking `high` で実行。
対象snapshotは `db1fa8c3be8f29278ba6a9f1f35ad6f2d0e39abf`。
後続のmain取り込み・レビュー修正を含む最新headでは全モデル評価を再実行していない。
2026-10-03にagent-qaの4ケースを削除し、e2eの発火・非発火ケースを4件追加した。
現行は84依頼だが（2026-10-08 に image-generation → media-generation の rename に伴い動画2件を追加）、以下の保存結果は変更前のケース集合の実測であり、新しい集合では再評価していない。

| 評価 | Current |
| --- | ---: |
| 発火判定の正解 | 77/82 |
| 発火すべき41依頼の読み込み | 39/41 |
| 紛らわしい41依頼の誤発火 | 3/41 |
| 代表6タスクの基準達成 | 35/36 |

発火判定の失敗・反復を含む [全結果](results/triggers-1.json)、
[初回集計](results/initial-trigger-summary.json)、[再試行前の記録](results/trigger-retries.json) を残す。
未完了の実行だけを再試行し、採点可能だった失敗は置き換えていない。
`writing-positive`、`merge-near-miss`、`creator-boundary-positive`、未変更のsecret-env 2依頼を
追加で2回評価し、各回5/5だった。初回の差を調べる事後選定なので主集計には混ぜない。
[追加回2](results/triggers-2.json)、[追加回3](results/triggers-3.json)。

| 代表タスク | Current |
| --- | ---: |
| README の初回利用・翻訳・リンク | 6/6 |
| PRD のモデル・要件・用語・prototype | 6/6 |
| 日本語推敲の事実・確実性・責任主体 | 6/6 |
| CLI の機械可読契約・検証・dry-run | 5/6 |
| button の8状態・既存token・4幅 | 6/6 |
| skill の作成／検査分岐と保存契約 | 6/6 |

tool call数は公開result.jsonの配列長、tool error数はnative tool_execution_endのisErrorを事後集計したもの。
各行のis_errorも公開し、currentの6runは計118 call・2 errorで、grading.jsonの内訳と一致する。

CLIの `schema rename` は生成コードの文字列整形で例外終了する。成果物を修正して
採点し直していない。基準外の問題も各 `grading.json` に残す。
**この実測から全skill・全harnessでの精度維持は断言できない。**

## 過去の前後比較

同じ入力で旧版 `1ff5341` と上記snapshotを比較したとき、両側を採点できた81依頼の
正解は75→77、代表タスクは34→35/36だった。旧版の `structure-near-miss` は
再試行でもsnapshot外のskillを読んだため、81組の比較から除外した。
current単体の82依頼では、この依頼の誤発火も含めて上表を集計している。

比較の成果物・採点・再試行記録は
[記録済みcommit e07b6d5](https://github.com/wwwyo/dotfiles/tree/e07b6d5005387f54db01fa0cda5384d1a252a262/.agents/skillctrl/evals/skill-quality/results)
を参照する。現在のtreeにはcurrentのrunだけを残す。

## 方法と限界

- 現行の `triggers.json` はsecret-envを含む31 skillを扱う84依頼。
  タスク・scheduled automationの実運用は検証しない。
- 全40 skillをGit archiveで固定し、Pi自身のloaderで読み込みを確認する。
  user queryを加工せず、対象snapshotのSKILL.mdを実際に読めたことを発火の証拠にする。
  自己申告・失敗したtool要求は証拠にせず、別treeのskillを読んだ実行は無効にする。
- 新しいsessionでcontext files・自動extensions・prompt templates・default skill discoveryを
  無効にする。認証・user-levelモデル設定は既存環境を使う。保存した採点対象のnativeイベントは
  すべて `opencode-go/space-bunny-free` を示している。
- 発火後は操作開始前に終了する。未発火は正常なagent_endを待つ。
  APIエラー・timeout・不正参照は正解にせず、比較では両側が採点可能な組だけを使う。
  欠測が無作為とは限らないため、条件付き割合を全依頼や実利用へ外挿しない。
- 代表タスクはskill利用を明示し、同じfixtureとfile toolsだけを渡す。
  追加ヒアリング・外部レビュー・shell・browser・networkは実装agentから利用できない。
  発火精度と、読み込み後の成果物の評価は別に扱う。
- 親がCLIをコピーしたfixtureで14要求、helperを実行した。
  UIはOrcaのiframeで320/375/414/768pxを実測した。実端末の検証ではない。
  成功したfile callの参照・変更先がfixtureまたは対象snapshot内にあることも監査した。
- 保存した採点は版を伏せて6基準を判定したもの。正確なgraderのmodel IDは未記録。
  依頼・基準はagentが作り、人による妥当性確認は未実施。明示的な否定を含むnear missが多く、
  通常の曖昧な依頼を代表する統計標本ではない。
- 各タスク1完了回。時間/tokenは完了回だけで、総費用や速度の改善を示さない。
  標準偏差も異なる6タスク間の差で、同一タスクの反復分散ではない。

## 再実行

mise管理のPi・Node・Pythonと既存Pi認証を使う。commit済みのskillを評価する。
raw JSONLはlocal workspaceだけに保存し、公開結果にはtool証拠・artifact・hash・採点を残す。

```bash
mise exec -- python3 .agents/skillctrl/evals/skill-quality/run.py \
  --workspace /tmp/skill-quality-workspace/iteration-1 \
  --ref HEAD --model opencode-go/space-bunny-free --jobs 4 --timeout 180

mise exec -- python3 .agents/skillctrl/evals/skill-quality/tasks.py \
  --workspace /tmp/skill-quality-workspace/iteration-1 \
  --model opencode-go/space-bunny-free --jobs 2

bash .agents/skillctrl/eval.test.sh
```

現在のケースは、検索・作成の依頼を統合済みの `skillctrl` skill に向ける。`learn` のケースも Karpathy の方法で説明を作る新しい skill に合わせている。保存結果は旧 skill を評価した記録なので書き換えない。保存結果と同じケース・snapshotを再実行する場合は、[当時の評価ケースとrunner](https://github.com/wwwyo/dotfiles/tree/db1fa8c3be8f29278ba6a9f1f35ad6f2d0e39abf/.agents/skillctrl/evals/skill-quality) を使い、`--ref db1fa8c3be8f29278ba6a9f1f35ad6f2d0e39abf` を指定する。現在のケースを旧 snapshot に適用しない。
一時的な前後比較はfresh workspaceに `--ref <current-commit> --before <baseline-commit>` を指定する。
通常実行ではoldのsnapshot・runを作らず、tasksも同じmanifestの対象だけを実行する。

ref・model・Pi version・datasetが変わったworkspaceの再利用は拒否する。
未完了は `--retry-incomplete` と `--ids` で、過去dirをattemptsへ移して元入力から再開する。
result.jsonだけの削除は途中成果物が残るため拒否する。
発火検査のidsはcase ID、タスクのidsはeval name。

`probe.py <run-dir>` は確認済みfixtureコードをコピーして実行する。
UIはpreviewをOrcaで開き、viewport.js全文を `orca eval --expression` に渡す。
採点は [grader](vendor/skill-creator/grader.md) に沿い、grading.jsonを各runへ置く。
実行時の元データは [evaluated-tasks.json](results/evaluated-tasks.json) に固定している。
現在のtasks.jsonは未使用の発火案を削除したもので、prompt・fixture・assertionsは同じ。

## この harness への変更をレビューするとき

- 正規化の適用順: 比較・採点の前に正規化が効いているか。順序が変わると既存結果との比較が壊れる
- `python -O` で `assert` が消える — 入力検証・境界条件を assert に書かない
- subprocess・sandbox 実行への env リーク（評価対象に親の env・認証が漏れないか）
- run 間の fixture reset: 前回 run の残存 fixture・cache が結果を汚さないか
- 採点不能な cache・skip 結果を採点の分母・分子に混ぜない
- 欠測は MNAR になりうる — 条件付き割合を全体へ外挿しない（「方法と限界」の原則）

## 結果を見る

```bash
mise exec -- python3 .agents/skillctrl/evals/skill-quality/review.py \
  .agents/skillctrl/evals/skill-quality/results/tasks \
  --output /tmp/skill-quality-review.html
orca tab create --url file:///tmp/skill-quality-review.html
```

標準viewerのOutputsでcurrentの成果物・基準別判定を確認する。
集計は [benchmark.json](results/benchmark.json) と [benchmark.md](results/benchmark.md)。
比較workspaceの場合だけ `--benchmark <benchmark.json>` を渡してBenchmarkタブも表示する。
review.pyは [評価専用に保存したviewer](vendor/skill-creator/README.md) を使い、artifact中のHTMLがscriptを閉じる問題を
埋め込みJSONのescapeで回避する。with_skillは評価したcurrentのsnapshotを意味する。
