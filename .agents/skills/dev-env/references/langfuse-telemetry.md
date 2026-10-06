# Langfuse telemetry

agent session の trace を Langfuse Cloud（JP: `https://jp.cloud.langfuse.com`）に送る。
プロンプトと tool 入出力（=コード内容）が外部 SaaS に行くため、**repo ごとの
opt-in**。仕組みは agent ごとに違う（Claude Code の native OTEL は metrics/logs で
Langfuse の OTLP endpoint は traces しか受けないため hook/plugin 経路を使う。
`OTEL_LOG_TOOL_DETAILS` は native OTEL 用の env で、exporter 未設定の現状は no-op）。

| agent | 仕組み | repo opt-in |
| --- | --- | --- |
| Claude Code | 公式 plugin `langfuse-observability@langfuse-observability` | repo の `.claude/settings.local.json` で `enabledPlugins` を `true`（user settings で default off。local > user の precedence で反転） |
| Codex | wwwyo fork の plugin `tracing@codex-observability-plugin`（`home/.chezmoitemplates/codex-base.toml.tmpl`） | repo の `.codex/langfuse.json` に `{"enabled": true}`（`process.cwd()` 解決。git root ではないので subdir 起動では拾わない — root から起動する） |
| pi | 公式 extension `@langfuse/pi-observability-plugin` | repo の `.pi/settings.json` に `packages` 宣言（install 先 `.pi/npm/` は gitignore） |
| Devin | plugin `devin-langfuse`（`wwwyo/devin-langfuse-plugin`）の Stop（turn ごと）+ SessionEnd（最終 flush）hook が sessions.db を正規化して送信 | repo-local `mise.local.toml` の `[env]` に `DEVIN_TRACE_TO_LANGFUSE="true"`（mise 公式の local override。tracked にしたい repo は `mise.toml` でも可） |

- **opt-in file は global gitignore 済み**（`**/.claude/settings.local.json`・
  `**/.codex/langfuse.json`・`**/.pi/settings.json`・`**/mise.local.toml` —
  `~/.gitignore`）。収集は個人の設定なので project repo には commit させない。
  dotfiles 自身は tracked で持つ（gitignore は tracked file に効かない）
- **worktree（Orca workspaces 含む）には gitignore 済み file が
  載らない**ので、opt-in は伝播しない。複製は
  `project-setup/tools/sync-local-worktree-files.sh` で行い、発火点は
  repo の `orca.yaml` `scripts.setup` と user-level Codex
  `~/.codex/hooks.json` の `SessionStart`。
  Codex は `--codex-session-start` で session の cwd を読み、Git root の親に
  `.codex-worktree-name` がある Codex 作成の worktree で不足 file のみ補う。
  既存の opt-in（無効化も含む）を上書きせず、Orca 作成の worktree・main checkout・
  Git 管理外では no-op。marker は installed desktop app の実装に依存するので、
  Codex の更新後に動かなくなったら作成処理の marker を再確認する
  共通 hook の正本は `home/dot_codex/hooks.json.tmpl` で、project repo に
  `environment.toml` は置かない。Codex が新規・変更 hook を実行するには
  `/hooks` の trust review が要る
- **opt-in は env 変数ではなく cwd 解決の file に寄せる**。env は子プロセスに
  伝播するため、opt-in 済み repo の shell から別 repo に agent を起動
  （`codex exec --cd` 等）すると env だけで未 opt-in repo が trace されてしまう。
  codex plugin は env `TRACE_TO_LANGFUSE` が config 解決の最優先なので、Devin の
  gate は意図的に別名 `DEVIN_TRACE_TO_LANGFUSE` にしてこの repo の env が
  codex plugin に見えないようにしてある
- **pi は global install しない**。`~/.pi/agent/settings.json` の `packages` に
  入れると key のある全 repo で有効になり、kill switch
  （`LANGFUSE_TRACING_ENABLED`）が要るが、それは Langfuse Python SDK 自体を
  no-op にする env でもあり Claude plugin・Devin emit・無関係な SDK 利用まで
  道連れにする。project `.pi/settings.json` 宣言なら trust 済み project でしか
  load されないので kill switch 自体が要らない。各 repo・各マシンで1回
  `pi install -l --approve "npm:@langfuse/pi-observability-plugin@0.1.2"` が要る

- **secrets は mise+age の global env**（`LANGFUSE_PUBLIC_KEY`/`SECRET_KEY`/`BASE_URL`）。
  Claude plugin は plain env を keychain の plugin config より優先して読むので
  `/plugin configure` 不要。GUI 起動の agent には env が届かない — Devin だけ
  hook wrapper 内で `mise x`（cwd は `DEVIN_PROJECT_DIR`）を評価して env を
  復元するので GUI でも trace される。それでも env が無ければ fail-open で素通り
- **machine-local の install が各マシンで 1 回要る**:
  - Claude: `claude plugin install langfuse-observability@langfuse-observability`
    （marketplace は `extraKnownMarketplaces` が自動登録。外部 source の plugin は
    project の enabledPlugins だけでは install されない）。install は user scope の
    `enabledPlugins` に `true` を書き込むので `claude plugin disable
    langfuse-observability@langfuse-observability --scope user` で commit 済みの
    `false` に戻す
  - Codex: `codex plugin marketplace add wwwyo/codex-observability-plugin` +
    `codex plugin add tracing@codex-observability-plugin`（初回に Stop hook の
    trust 承認あり）
  - Devin: `devin plugins install
    wwwyo/devin-langfuse-plugin#plugins/devin-langfuse`（user level。
    `--local` は machine 限定・更新は `devin plugins update`）
- **Devin exporter** は `wwwyo/devin-langfuse-plugin` repo の
  `plugins/devin-langfuse/hooks/` に置く（旧 `home/dot_config/devin/hooks/` から
  plugin 化して移設。以下この項の script 名はその dir の file）。vendored
  `langfuse_hook.py` を emit library として同 dir から
  import する（`emit_turn` に `source`/`label` param を足す divergence あり）。SDK は PEP723
  inline metadata で `langfuse==4.15.4`・`requests==2.34.2` pin、`uv run --script` が resolve する
  （upstream plugin と同じ方式）。トリガは `Stop`（turn 完了ごとの増分送信）
  + `SessionEnd`（最終 flush）— SessionEnd が発火しない・session を閉じない
  ケースでも pi/codex plugin と同様にほぼリアルタイムで trace が見える。
  `DEVIN_LANGFUSE_TIMING=session` にすると Stop は skip され SessionEnd の
  一括送信だけになる（session が正常終了しないと送られない trade-off）。
  この環境では global mise `[env]` に `DEVIN_LANGFUSE_TIMING="session"` を
  置き、まとめて送る方を既定にしている。repo ごとに戻したい場合は
  repo-local env で `turn` を上書きする。
  `langfuse-export.sh` が nohup detach するので hook 配列を待たせない。
  wrapper は `mise env` を `DEVIN_PROJECT_DIR` で評価してから gate 判定し
  （GUI 起動では mise env が乗らないため。`MISE_AGE_KEY` も keychain から補う）、
  opt-in でなければ uv/network を触らず終了する。stderr は machine 側 state dir
  `~/.local/state/langfuse-export/` の `hook.log`（1MB で rotate。repo 内 file ではなく
  plugin 化後も path は同じ）に残す。
  増分は `state.json` v2 の source user message ID ごとの payload fingerprint
  で管理する。turn 番号や timestamp は context 再作成で変わるため identity に
  使わない。trace/root は session + user message ID、generation/tool はさらに
  元 assistant message ID / tool ID から deterministic な OTel ID を生成する。
  末尾 turn の変化は同じ ID への更新、新しい node は新しい observation になる。
  同じ message_id の context copy は最初の位置を保ち、本文は最新 payload、
  tool_calls は source ID の和集合を読む。新版から消えた既存呼び出しも残す。
  body を checkpoint に保存せず hash のみを残す。
  DB read→emit→flush→atomic save を同じ `FileLock` 内で行い、古い snapshot による
  上書きと並走 hook の二重送信を防ぐ。emit 失敗は fingerprint を更新せず、HTTP /
  OTLP partial rejection / flush 失敗は checkpoint 全体を保存しない。次の hook で
  同じ ID のまま retry する。稼働中の retry は次回 Stop/SessionEnd が必要。
  **旧 checkpoint は送信成功の証拠ではない**。旧コードは emit / flush 失敗でも
  turn_count / buffer を保存し、source payload hash や cloud ID を持たない。
  `langfuse_reconcile.py --output /review/path/migrations.json` を既存の Langfuse env
  認証で実行すると、GET のみで session 全体を読み、source の旧 payload と
  input/output・model・時刻・型別 metadata・親子構造が一意かつ完全に一致する
  observation の既存 trace/span ID を対応付ける。raw IO やキーは保存せず、ID と
  hash のみを mode 0600 の review file に残す。曖昧・欠落・未対応 ID 形式は移行しない。
  reviewed file を `~/.local/state/langfuse-export/migrations.json` に置くと、hook が
  接続先・public key の hash・旧 checkpoint 全体の hash を確認して v2 に移行する。
  既存 ID を使うので unchanged な履歴の replay はゼロ、append は既存 root/children
  の ID を保持して固有 node を追加する。送信失敗時は移行 state も確定せず同じ ID で retry。
  未検証・stale な session は旧 reader/signature/random-ID exporter を継続する。
  既存 export を止めず、旧 resume 重複と送信試行 checkpoint の問題はその lane に残る。
  新規 session は最初から v2。破損 state は自動 reset / bulk replay せずログに修復待ちを
  残す。review file の導入と canonical hook の反映は承認後に行い、worktree から apply しない。
  cloud 側の既存記録や保持設定は変更しない。回帰テストは同じ hooks dir の
  `test_langfuse_export.py`（pinned SDK + localhost OTLP collector、cloud 送信なし）。
- **dotfiles repo 自身は罠がある**: `home/dot_claude/settings.json` は global の正本で、
  `home/dot_pi/agent/`・`home/dot_codex/` も `~` 配下の source。ここに global 側の
  opt-in を書くと全 repo で有効になる。dotfiles repo で trace したいときは
  `.claude/settings.local.json`・`.codex/langfuse.json`・`.pi/settings.json`
  （repo root、chezmoi 管理外。後2つはこの repo では tracked）・
  repo-local `mise.toml`（この repo では tracked。他 repo では `mise.local.toml`）を使う
- **Codex / Devin は turn 単位の compact 記録が既定**。Codex は
  `home/dot_codex/langfuse.json` の `detail=turn` を global default として読む
  （`enabled` は置かず repo opt-in を維持）。Devin は exporter の既定値。
  詳細記録へ戻すには Codex の repo `.codex/langfuse.json` で `detail=full`、
  Devin の repo-local env で `DEVIN_LANGFUSE_DETAIL=full` を指定する。
  turn の input/output はユーザー入力と最終応答。metadata の
  `telemetry_summary`（JSON、version=1）に generation/tool 件数・tool 名・
  bounded なエラー概要と時刻・model 別 token 使用量を保持し、session-eval が読む。
  tool 入出力全文と途中のモデル応答は送らず、個別 generation の cost/latency
  表示は full mode が必要。subagent の turn は残す。
  mode 切替だけでは過去 turn を replay しない。変更された tail に以前の詳細
  observation が残る場合、評価側は集約値を優先して二重計上を防ぐ。
  旧 Devin checkpoint の移行用 projector は、cloud に保存された summary が
  source と完全一致する turn だけ compact として照合し、full 履歴との混在を扱う。
- **Codex fork の配布**: marketplace は npm の公式 package ではなく Git 内の
  `plugins/tracing` を読む。生成 bundle を source と同じ commit に含め、
  plugin version も上げる。fork URL に変えるだけで npm source を残すと
  公式 package が引き続き動く。新しい hook の trust は `/hooks` で確認する。
- **Devin の送信成功確認**: HTTP transport の `Session.request` で JSON / protobuf
  partial rejection を検知する。`post` だけの override では現在の OTel transport
  を捕捉できない。検知した rejection は exporter 内部で再試行されても checkpoint
  の確定を止め、次の hook で同じ ID に再送する。
- **trace の確認は v2 API**: `GET /api/public/v2/observations?fields=core,basic,model,usage,metadata`
  （legacy `/api/public/traces` は 410。fields 指定しないと model/usage が返らない）
