# Langfuse telemetry

agent session の trace を Langfuse Cloud（JP: `https://jp.cloud.langfuse.com`）に送る。
プロンプトと tool 入出力（=コード内容）が外部 SaaS に行くため、**repo ごとの
opt-in**。仕組みは agent ごとに違う（Claude Code の native OTEL は metrics/logs で
Langfuse の OTLP endpoint は traces しか受けないため hook/plugin 経路を使う。
`OTEL_LOG_TOOL_DETAILS` は native OTEL 用の env で、exporter 未設定の現状は no-op）。

| agent | 仕組み | repo opt-in |
| --- | --- | --- |
| Claude Code | 公式 plugin `langfuse-observability@langfuse-observability` | repo の `.claude/settings.local.json` で `enabledPlugins` を `true`（user settings で default off。local > user の precedence で反転） |
| pi | wwwyo fork の extension `@wwwyo/pi-observability-plugin`（`git:github.com/wwwyo/pi-observability-plugin`。`detail: turn` を持つ） | repo の `.pi/settings.json` に `packages` 宣言（install 先 `.pi/git/` は gitignore） |

- **opt-in file は global gitignore 済み**（`**/.claude/settings.local.json`・
  `**/.pi/settings.json`・`**/.pi/langfuse.json`・
  `**/mise.local.toml` —
  `~/.gitignore`）。収集は個人の設定なので project repo には commit させない。
  dotfiles 自身は tracked で持つ（gitignore は tracked file に効かない）
- **worktree（Orca workspaces 含む）には gitignore 済み file が
  載らない**ので、opt-in は伝播しない。複製は
  `project-setup/tools/sync-local-worktree-files.sh` で行い、発火点は
  repo の `orca.yaml` `scripts.setup`。main checkout・Git 管理外では no-op
- **opt-in は env 変数ではなく cwd 解決の file に寄せる**。env は子プロセスに
  伝播するため、opt-in 済み repo の shell から別 repo に agent を起動
  （`pi` を別 repo の cwd で起動する等）すると env だけで未 opt-in repo が trace されてしまう。
- **pi は global install しない**。`~/.pi/agent/settings.json` の `packages` に
  入れると key のある全 repo で有効になり、kill switch
  （`LANGFUSE_TRACING_ENABLED`）が要るが、それは Langfuse Python SDK 自体を
  no-op にする env でもあり Claude plugin・無関係な SDK 利用まで
  道連れにする。project `.pi/settings.json` 宣言なら trust 済み project でしか
  load されないので kill switch 自体が要らない。各 repo・各マシンで1回
  `pi install -l --approve "git:github.com/wwwyo/pi-observability-plugin@v0.2.0"` が要る（git source は tag/commit で pin される）

- **secrets は mise+age の global env**（`LANGFUSE_PUBLIC_KEY`/`SECRET_KEY`/`BASE_URL`）。
  Claude plugin は plain env を keychain の plugin config より優先して読むので
  `/plugin configure` 不要。pi を GUI ランチャーから起動する場合は `mise x -- pi ...` で global env を子に注入する。認証 key の解決は [pi の設定・認証](pi.md) に従う。
- **machine-local の install が各マシンで 1 回要る**:
  - Claude: `claude plugin install langfuse-observability@langfuse-observability`
    （marketplace は `extraKnownMarketplaces` が自動登録。外部 source の plugin は
    project の enabledPlugins だけでは install されない）。install は user scope の
    `enabledPlugins` に `true` を書き込むので `claude plugin disable
    langfuse-observability@langfuse-observability --scope user` で commit 済みの
    `false` に戻す
- **dotfiles repo 自身は罠がある**: `home/dot_claude/settings.json` は global の正本で、
  `home/dot_pi/agent/` も `~` 配下の source。ここに global 側の
  opt-in を書くと全 repo で有効になる。dotfiles repo で trace したいときは
  `.claude/settings.local.json`・`.pi/settings.json`
  （repo root、chezmoi 管理外。後者はこの repo では tracked）を使う
- **pi は turn 単位の compact 記録が既定**。`home/dot_pi/agent/langfuse.json` の
  `detail=turn` を global default として読む（keys は mise の env から取るので
  この file に secret は置かない）。詳細記録へ戻すには repo の `.pi/langfuse.json`
  に `detail=full`、run 単位なら `LANGFUSE_PI_DETAIL=full`。metadata の
  `telemetry_summary`（JSON、version=1）に generation/tool 件数・tool 名・
  bounded なエラー概要と時刻・model 別 token 使用量を保持し、session-eval が読む。
  turn の input/output はユーザー入力と最終応答で、tool 入出力全文と途中の
  モデル応答は送らず、個別 generation の cost/latency 表示は full mode が必要。
  observation 量の削減が目的（pi は 6h 窓で観測の~6 割を占めていた）。
  mode 切替だけでは過去 turn を replay しない。変更された tail に以前の詳細
  observation が残る場合、評価側は集約値を優先して二重計上を防ぐ。
- **trace の確認は v2 API**: `GET /api/public/v2/observations?fields=core,basic,model,usage,metadata,trace_context`
  （legacy `/api/public/traces` は 410。fields 指定しないと model/usage が返らない。
  `sessionId`/`traceName` は `trace_context` に入るため照合時は指定が要る）
- **telemetry 配線の疎通確認は最小 probe**: 検証対象の worktree で agent を
  起動し、session 名を `langfuse-live-check-<source>-<YYYYMMDD>` にして
  「ツールを使わず『ok』とだけ返答して」の 1 turn を投げる。tool を使わせない
  ので observation の形（turn 集約 vs full）に依存せず、日付 suffix で同種
  probe や batch の他 session と区別できる。到達確認は probe 開始時刻を記録し、
  上の v2 observations API をその時間帯で引いて返った observation の
  `sessionId` / `traceName` を照合する（session 名は識別の目印であって
  lookup key にはしない。probe しただけでは配線の成否は分からない）
- **units 課金は取り込み件数ベースで保存量ではない** — cloud 上の trace を消しても
  units は戻らないので export→削除は節約にならない。削る手段は送信する observation
  数を減らすことだけ（turn/full 集約の動機）。SDK の sampling は trace 単位なので
  1 session=1 trace の構成では session の途中が欠けて使えない。Blob Export に
  session comments は含まれない — 記録が要るなら comments API で別途取得する
