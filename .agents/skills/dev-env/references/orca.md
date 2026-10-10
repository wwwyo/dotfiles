# Orca

Orca 操作の正本は `orca-cli` skill — `ORCA skills get orca-cli` が version-matched guide を返す。ここには guide / `--help` から直接読めない周辺知見と、dotfiles が管理する設定ファイルの仕様を置く。操作時の既定方針は `orca-cli`、バージョン固有の調査結果はこの reference に持たせる。

## keybindings.json

- dotfiles 側の source: `home/private_dot_orca/keybindings.json` → `~/.orca/keybindings.json`（`private_` prefix で `~/.orca` の mode を 0700 に宣言。credential 類が入る state dir なので 0755 にしない）
- entry は**置き換え型**。key ごとの配列が binding 集合全体になる — 既存のデフォルト binding を残したいときは配列に併記する。書かないと消える。`[]` は unbind
- file watcher は無い。反映は Orca 再起動か Settings → Shortcuts の reload — 実行中の terminal session を殺したくないときは再起動せず reload を案内する
- bindable な command ID の正本は `/Applications/Orca.app` 内の command registry（`terminal.splitDown`・`terminal.splitRight`・`worktree.palette` 等をここから掘る）

## ショートカット化できないもの（2026-09 時点）

存在しない機能を掘り直すコストを省くための negative list:

- browser tab の split — split 機構（`createUnifiedTabInSplit` / `placement: 'rightSplit'`）は simulator/emulator tab にのみ配線。`terminal.splitRight` は terminal tab 内 pane 分割で別物、`orca tab create` に placement 引数なし。[stablyai/orca#10076](https://github.com/stablyai/orca/pull/10076) の `tab.moveToSplitRight`（default `Mod+\`）が open のまま — merge されれば palette → `Mod+\` の 2 ストロークで近似できる

## CLI の補足

引数仕様は version-matched guide と `--help` が正本なのでここには列挙しない。guide・`--help` の両方に使い分け基準が載らないものだけ置く:

- `orca file open <path> --worktree <selector>` — 非対話 session でも動き、`--worktree` で別 worktree の file を直接 Orca editor で開ける。「ファイルをユーザーに見せる」用途では browser panel 経由の中継よりこちらを優先する

## embedded browser がユーザーのフォーカスを奪うとき

操作時の既定方針は [orca-cli のフォーカス保持ルール](../../orca-cli/SKILL.md#preserve-the-users-focus-during-browser-automation) を参照。

2026-10-03、macOS の Orca 1.4.218 の CLI help・同梱実装を確認。`tab switch` の明示的な pane focus は opt-in だが、フォーカス移動を完全に止める設定や `tab create --no-focus` は確認できなかった。操作時のフォーカス保持は、この調査では実測していない。[issue #20595](https://github.com/stablyai/orca/issues/20595) は macOS 1.4.201 で `click` / mouse 操作のフォーカス移動と、`type` / `keypress` がユーザーの terminal に届く挙動を報告している。

根本対応の候補は、offscreen rendering による「Focus-safe browser pages」を追加する [PR #24047](https://github.com/stablyai/orca/pull/24047)。確認日時点では draft・未マージなので、現在使える設定として案内しない。Orca 更新後に可否を案内するときは、installed version の guide / help と PR の merge・release 状態を再確認する。

## worktree・session が消えたとき

Orca 管理の worktree を消す経路は2つある — scheduled task `cleanup`（`.agents/scheduled-tasks/cleanup/`、3日おき。`liveTerminalCount==0` かつ git 側の条件を満たすものを `orca worktree rm`）と、`pr-auto-merge` の sweep（merged PR の worktree を同日中に消す）。PTY は Orca 再起動や shell 終了で落ちるので「勝手に閉じられた」ように見える。確認先は `orca automations runs --id <automation> --json` の `outputSnapshot.content`（run ごとの agent 最終報告。snapshot が null / `truncated` のときはその run からは辿れない。削除した path が残るのは cleanup の30日ルール経由のみで、抜け殻削除は本数のみ）。pr-auto-merge 側の削除は `wwwyo/me` の `daily/<date>/pr-watch.jsonl` に `worktree_rm` event として残り、人間向けの報告は同 dir の `pr-watch.md`。git 側の復元は cleanup SKILL.md、terminal scrollback は戻らないが pi session の本文は `~/.pi/agent/sessions/` の JSONL に残る。

## stablyai/orca への issue

GitHub issue forms 管理 — `[Feature]:` 接頭辞と enhancement label は form が自動付与、英語必須。形式の強制は Web UI 層のみで、`gh` / API 経由ならチェックは素通りする。

## automation の非自明な挙動

- **reuse の成立条件は前回 run の pane + PTY が live なこと**。`run.workspaceId` が一致し、pane に agent status `done` が乗り、PTY が生きているときだけ既存 PTY へ prompt が貼られる。`workspaceMode: new_per_run`・pane の `done` 不在・PTY 終了では新規 session が立つ。
- **入力受付と turn/model の証明を区別する**。`provider: "unsupported"` や `turn_started not observed` だけで未送信と断定して再送しない。対象 terminal の描画と pi session の新しい user/assistant message を確認し、二重送信を避ける。
- **automation CLI は model/thinking の per-run flag を持たない**。`provider = "pi"` の task は delegate の task/データ区分でモデルを決め、Orca Settings → Agents の pi コマンド・起動引数に設定する。異なるデータ区分の task を同じ launcher に混ぜず、標準 pi launcher は MiMo を使い、Operator は delegate の優先順に従い、pi を使う場合は Haiku・high を `terminal create --command` に明示する。worker も選んだモデル・thinking を明示する。GUI 起動では `mise x -- pi` を使い telemetry の global env も注入する。
- **新規 Mac・automation 同期前の launcher 確認**。`sync_automations.py` は provider だけを同期し、GUI の起動引数は検査・配備しない。同期前に全 pi task のデータ区分を確認する。現在の6件は personal。delegate の worker/personal の第一候補が `pi --list-models` にあることを確認し、Settings → Agents の command を `mise`、args を `x -- pi --no-sandbox --model <provider/model> --thinking <effort>` に保存する。試験用 worktree を標準 pi launcher で起動して footer の model/thinking と Langfuse の有効表示を照合する。異なる区分の task を追加した場合は共通 launcher のまま有効化せず、task ごとの起動モデルを指定できる経路を整える。稼働済みの再利用 session は設定変更で切り替わらないため、対象 task の terminal を個別に確認する。
- `orca.yaml` の `scripts.setup` は各 worktree の working tree を `readFileSync` で読む — その worktree 内の未 commit 変更も即反映される。新規 worktree に入らないのは push 不足ではなく、start-from の ref に commit されていないため。`commandSourcePolicy`（`shared-only` / `local-only` / `run-both`。旧 `shared-first` は `shared-only` に正規化）は `orca.yaml` の key ではなく Settings の repo ごとローカル設定。`local-only` で local script が空なら shared に fallback せず何も走らない。UI の local script 欄を消しても policy が変わらないのは明示保存済みのときだけ — 未設定（`undefined`）だと local script の有無から effective policy が決まり、消すと `local-only` → `shared-only` に反転する

- 溜まった automation session record を掃除する専用コマンドは無い。`terminal close --worktree <selector> --all`（destructive）は指定した worktree の全 terminal を live session 込みで閉じるので、掃除用途には使わない

## orchestration: worker が自分の mailbox を読むとき

version-matched guide は coordinator 視点の記述が中心。worker 側の契約は `orca skills get orchestration --reference worker-contract` に独立してある — preamble を持つ worker はまずそれを読む。ここには読み違えやすい差分と guide に載らない挙動だけ置く:

- `orca orchestration check --terminal <自分の handle> --json` で読む。`--run <run_id>` は Run scope を明示する flag で、worker が自分の mailbox を読むときは省略する（既定は自分の bound Run）
- `worker_done` を送る直前に1回 check する — 直前の redirect・追加指示を取りこぼさないため。check には live な preamble の自分の terminal handle を使う（古い handle には新しい Run の message は届かない）
- 消費せず中身だけ見るときは `--peek`（unread を read にしない）。応答の `ok: false` は「0件」ではなく失敗 — 空と区別して扱う
- `check` が `consumer_fenced` を返したら、その process は自分の Dispatch の owner ではなくなっている（Attempt が別 worker に付け替えられたか、自分抜きで settle した）。止まり、`worker_done` も check の再試行もしない。空の check は「置き換えられた」意味ではない — 置き換えは `consumer_fenced` でしか分からない
- `send` 成功は durable enqueue、nudge は best-effort であり worker の受領/理解を証明しない。worker は `check` の全 message を処理し、変更に影響する指示は受領と現在の到達点を status で返す。delivery が replay される版では処理済み `deliveryId` を version-matched guide に従って `check --ack` する。ack の返り値にも次の FIFO batch が含まれるため、本文の処理・status 応答・ack を deliveryId が null になるまで繰り返す。`replayed: true` は未 ack の旧 delivery であり新規0件ではない。本文を時刻で絞り込んで古い未処理指示を捨てない
- 待機は `check --wait`（stderr に keepalive が流れる）。呼び出し側の tool 実行には blocking 上限（1分程度）があるので、長い待機は繰り返し呼ぶ
- sibling worker との連絡は group address で届く。`@all` 等の Run group は sender の属する Run の live Dispatch 群を指す（worker からは sibling、coordinator は含まれない）。worker が coordinator へ blocker を上げる宛先は group ではなく `run:<id>`。`worker_done` 等の lifecycle message は group 宛にしない

## 自分のいる worktree を消すとき

`orca worktree rm` は対象を cwd にしている process の足元も消す — cwd が消えた後は相対 path・`getcwd` 依存のコマンドが元の意味をなさないエラーで落ちる。自分が中にいる worktree（pr-auto-merge sweep 等で自分の worktree が対象に含まれうるケース含む）を消す操作の前に、実行側 shell の `pwd` が対象外であることを確認する。確認せず消して後続コマンドが不可解な `ENOENT` / deleted-path エラーで落ちたときの原因はこれ。

## `orca computer` が focused window を取れないとき

`focused topmost` 系エラーで全コマンドが拒否されるときは、accessibility 権限の欠落と対象 window が前面に無いこと（または画面ロック）を切り分ける — 権限は `orca computer permissions` で設定画面を開いて確認する。権限が通っていても解消しないなら、対象 window をユーザーに手動で前面へ出してもらう。`open -a` は agent の実行環境では app 名の解決・前面化に失敗することがあるので復帰手段に頼らない。click が効かない入力要素には `set-value` が fallback になる。

- `native pipe startup failed` が出たら `js_reset` は効かない。Playwright/CDP へのフォールバックはユーザーが明示指定している場合に限るので、障害時は独断で切り替えず、その旨を報告・要求して止まる
- `chrome:control-chrome` 系の権限確認（"saved browser permissions could not be
  verified"）で embedded browser の操作が止まると、検証用 browser の別 profile では
  サービス login が壁になる。ログイン済み実環境が要る診断は、ユーザーの普段の
  Chrome で `chrome://inspect/#remote-debugging` を有効化して接続する経路が実効
  した（2026-10、minaosi の note 実機検証で確認）

## embedded browser の Design Feedback

browser toolbar の annotate ボタン（MessageSquarePlus アイコン、aria-label `Annotate page element`）でユーザーが要素を選んで送るフィードバックは、`## Design Feedback: <pathname+search>` 形式のメッセージとして agent に届く（見出しは page タイトルではなく URL の pathname + search）。既定の keyboard 経路もある — `browser.annotateElement` に mac は `Mod+Shift+C`、linux/win は `Alt+Shift+N`（workspace doc preview には配線されない）。要素ごとに Intent・Selector・Bounds と自由文の Feedback が必ず載り、Source・React・Location・Full DOM path・HTML・Computed styles は取れたときだけ出る（Computed styles は非 default 値があるときのみ — selector から file へ辿る手がかりは Source / React）。UI 反復で「この枠」「ここ」のような散文の指摘が来たら、要素を選んで送り直してもらう方が往復なしで箇所を特定できる。
