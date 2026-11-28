# 個人の MCP を MCP Server Portal に集約する

ChatGPT・claude.ai（web・スマホ）とローカル agent から、公開 remote MCP（context7・fudoki・queria・Cloudflare API・Buffer）、Composio 経由の外部サービス（Google Search Console・Google Analytics）を portal の入口から使う構成。2026-10-13 に自前 proxy（wwwyo/access-mcp-proxy、archive 済み）から置き換えた。判断の経緯は同 repo の ADR 0002 と PRD `docs/prd/mcp-portal/` に残っている。この Mac の loopback で動く OpenScreen も portal（Gateway・Tunnel 経由）に載せていたが、2026-11-17 に外し、Claude Code の local plugin から直接つなぐ形にした（[skill-plugins](skill-plugins.md)）。2026-11-27 からは、同じ Gateway・Tunnel の経路で wwwyo/personal-mcp のカメラ（server `camera`、`camera/`）を載せている（portal `media`）。

portal は 3 つある。

- `mcphub`（`mcp.wwwyo.dev`、portal ID `wwwyo`）: 開発で常用する MCP。Code Mode `default_on` で、text を返す server を置く
- `mcp-media`（`https://mcp-media.wwwyo.dev/mcp`、portal ID `media`）: Code Mode `off`。画像など text 以外を返す tool の server（いまは personal-mcp のカメラ `camera`）を置く。Code Mode の execute を通すと image content が base64 の文字列になり、出力上限で切れて client で画像として見られないため、2026-11-27 に分けた。置き場所は「tool が text 以外を返すか」で決め、text だけなら `wwwyo` に置く
- `mcp-marketing`（`mcp-marketing.wwwyo.dev`、portal ID `marketing`）: マーケティング用。マーケ系の外部サービス（Composio 経由の GSC・GA、Buffer 等）をここに載せ、マーケ作業の agent にはこの portal だけを渡す

```text
ChatGPT / claude.ai / ローカル agent ──OAuth──▶ portal mcp.wwwyo.dev ─┬─▶ https://mcp.context7.com/mcp（key は Cloudflare 保管）
                                                                       ├─▶ https://api.fudoki.dev/mcp（認証なし）
                                                                       └─▶ https://mcp.queria.io（利用者ごとの OAuth。token は portal が保持）

マーケ作業の agent ──OAuth──▶ portal mcp-marketing.wwwyo.dev ─┬─▶ Composio tool router session（portal に 1 つ。GSC・GA。key は Cloudflare 保管）
                                                              ├─▶ https://mcp.buffer.com/mcp（key は Cloudflare 保管）
                                                              └─▶ https://mcp.cloudflare.com/mcp（server `cloudflare-small`。利用者ごとの OAuth）
```

## 外部サービスは portal に集約し、既存の MCP が無いものだけ Composio を使う

agent から使う MCP は、外部サービスも含めて Cloudflare の portal に集約する。client（Claude Code・Codex・ChatGPT 等）にサービスごとの MCP を直接登録しない（2026-11-10 に決定。11-09 の「外部サービスは Composio に統一」から改めた）。

- **まず既存の MCP server を探す**: 公式（または提供元が保守する）remote MCP があれば、それを portal の upstream として入れる（Cloudflare API・context7 が先例。手順は下の「MCP を追加するとき」）。OAuth で scope を絞れるか、tool 単位で読み取りだけを公開できるかを確認してから入れる
- **既存の MCP が無い・使えないものだけ Composio**: 公式 MCP が無い、remote で提供されていない、権限を絞れない、といったサービスは Composio の tool router session を経由して portal に入れる（GSC が先例）。自作はどちらも無いときの最後の手段
- どちらの経路でも入口は portal 1 つに保つ（マーケ用途は `mcp-marketing`、開発用途は `mcphub`）。

### Composio を使うときの構成

- **役割の分担**: Composio は連携を持ち、OAuth token を保管・更新する。portal は agent の認証・tool 単位の公開・ログ・Code Mode を受け持つ。Composio 自体も複数 toolkit を 1 endpoint に束ねられるが、Composio の外の MCP（公式 remote MCP・context7・自作）は束ねられないので、入口は portal に寄せる
- **汎用 endpoint（`connect.composio.dev/mcp`）は使わない**: `COMPOSIO_SEARCH_TOOLS`・`COMPOSIO_MULTI_EXECUTE_TOOL`・`COMPOSIO_PROXY_EXECUTE`・`COMPOSIO_REMOTE_BASH_TOOL` などのメタツール経由で、全 toolkit の全操作（削除系も）を呼べる。portal の tool 単位の公開設定が効かない
- **portal ごとに tool router session を 1 つ作り、その session の MCP URL を server `composio` として portal に入れる**（2026-11-10 に toolkit ごとの session・server から切り替えた）: Composio Platform の API（`POST /api/v3.1/tool_router/session`）で、`toolkits.enable` と `tools.<toolkit>.enable` に許可する tool だけを並べ、`search`・`execute.enable_multi_execute`・`workbench`・`manage_connections` を無効にする。session の `mcp.url` は許可した tool だけを個別の tool として出し、メタツールは出さない。portal 側は Code Mode なので、toolkit・tool が増えても agent の context は増えない
  - toolkit を足すときは `PATCH /api/v3.1/tool_router/session/<id>` で `toolkits.enable` と `tools.<toolkit>.enable` に追加する。URL は変わらないので、portal 側は `cf mcp servers sync composio` で再同期するだけでよい。PATCH が渡した配列で置き換わるかは未検証なので、既存の toolkit・tool も含めて送り、後で `GET` で確認する
  - session は `preload.tools: "all"` にしておく（いまの session の値）。許可リストは実行できる tool を絞るだけで、MCP の tool 一覧に出すのは preload。明示リストにした場合は toolkit・tool を足すたびに preload も更新する
  - 認証が要る toolkit は、PATCH の前に Platform で auth config（scope を絞る）を作り、session と同じ user_id `wwwyo` の接続を `POST /api/v3/connected_accounts/link` で張って ACTIVE を確認し、session の `auth_configs.<toolkit>` に auth config を指定する。`manage_connections` は無効なので agent からは接続を始められない
  - portal 側では Composio を toolkit 単位で on/off できない（server が 1 つなので）。tool 単位なら portal の `servers[].updated_tools` で無効にできる。toolkit ごとに渡す agent を分けたいときは portal を分ける
- **読み取り専用にするときは 3 段で絞る**: auth config の OAuth scope（GSC なら `webmasters.readonly` だけ）、auth config の `tool_access_config.tools_available_for_execution`、session の tool 許可リスト。scope の変更は新しい接続にしか効かないので、scope を変えたら接続し直す
- **portal へは共有 key で入れる**: server は `auth_type: bearer` にし、`auth_credentials` に `{"headers":{"x-api-key":"<ak_ key>"}}` を JSON 文字列で渡す（Composio は `Authorization: Bearer` ではなく `x-api-key` を読む）。portal 側の `on_behalf` は `false`
- **書き込み系の tool を agent に渡すときは別に判断する**: Composio の `require_approval` は experimental で、portal（Code Mode）経由で elicitation が中継されるかは未検証。いま出している書き込みは GSC の `SUBMIT_SITEMAP` だけ（2026-11-13 にユーザーが選んだ）。これには scope `webmasters` が要るので、Google から見るとトークンは読み書きの権限を持ち、他の書き込みを止めているのは Composio の許可リストだけ
- **tool 一覧は最新版で取る**: `GET /api/v3/tools?toolkit_slug=<slug>` は `toolkit_versions=latest` を付けないと古い版が返る（2026-11-13 時点で GA 4 件・GSC 6 件。latest では 84 件・14 件）。読み書きの別は tool の tag（`readOnlyHint`・`createHint`・`updateHint`・`destructiveHint`）で判断する
- **managed auth は scope を足すことがある**: GA の auth config は `analytics.readonly` だけを指定しても `userinfo.profile` が付き、PATCH しても外れなかった（GSC には付かなかった）。scope を厳密にしたいときは、自前の OAuth client を使う auth config にする

#### Composio の key・project の区別

- **Composio Connect（consumer、`connect.composio.dev`）と Composio Platform（`platform.composio.dev`）は project が別。** Connect で繋いだ接続は Platform の key から見えない。session 方式は Platform 側で作り、接続も Platform 側の auth config で作り直す
- key は 2 種類ある。Connect の設定画面で出るのは `ck_`（consumer key、header は `x-consumer-api-key`）で、session 作成には使えない（`Invalid API key` の 401 になる）。session 作成と portal 用には、Platform の Project Settings → API Keys で `ak_`（header は `x-api-key`）を発行する
- `ak_` は権限を選んで発行する。setup では Auth configs・Connected accounts・Session management（Read and write）、Session tool execution（Write only）、Toolkits・Tools（Read only）を使った。権限が足りないと `This API key does not have the permissions required for ...` が route と必要な権限つきで返る。portal に置く常用 key は Session tool execution（Write only）だけでよい。Legacy の single toolkit MCP は、実行と作成が同じ「MCP (Legacy) Write」権限で分けられないので使わない
- global mise の `COMPOSIO_API_KEY`（age）は setup 用の権限の強い key。portal に置く常用 key（Session tool execution だけ）は mise に置かず、Cloudflare の server の credential にだけ入れている。接続（OAuth）は `POST /api/v3/connected_accounts/link` で発行したリンクを人が開いて同意する。リンクは約 10 分で失効する
- session の有効期限は doc に記載が無い（2026-11-09 時点）。portal の server が `error` になったら、同じ設定で session を作り直し、server の `hostname` を差し替える

## portal に載せる MCP の基準

portal は個人の MCP の入口を 1 つにまとめる経路。ChatGPT・claude.ai に加え、ローカル agent（Codex・pi・Devin・Claude Code）も `https://mcp.wwwyo.dev/mcp` の 1 entry だけを持つ（Claude Code は core plugin 経由、他は各 client の設定で下記。マーケ作業の agent は `mcp-marketing` を別 entry として持つ）。client 側の server 名は `mcphub`（portal ID の `wwwyo` とは別。agent・人が名前から中身を推測できるように付けた）で、tool は `mcp__mcphub__*`（Claude Code では plugin の名前空間が付いて `mcp__plugin_core_mcphub__*`）に見える（2026-10-21 に context7・fudoki の個別設定から切り替えた）。目的は context の節約で、Code Mode（`default_on`）により server・tool が増えても agent に載る tool 定義は Code Mode の少数の tool に留まる。2026-11-27 に一時 `opt_in` にしたが、同日に戻し、画像を返す server は Code Mode `off` の `mcp-media` に分けた（上記）。`mcp-media` は、カメラを使う client（claude.ai・スマホ）と Claude Code（core plugin の `mcp-media`）に別の entry として足す。Codex・pi・Devin には足していない。credential も client に渡さない。

- **載せる**: 個人で常用する MCP。credential を隠せるもの（context7）・認証の無い公開 MCP（fudoki）・upstream の OAuth 同意で scope を絞れるもの（queria）も同じ portal に入れる。Cloudflare API は以前 `mcphub` に載せていたが、2026-11-13 時点では `mcp-marketing` の server `cloudflare-small` にしか無い。Access・Cloudflare の障害でまとめて使えなくなるのは受け入れている
- **載せない**: 手元のアプリを操作する MCP（Blender の `blender`、OpenScreen の `openscreen`）。そのアプリが動く Mac の agent でしか意味が無く、外部 agent に出す理由が無いため、Claude Code の local plugin から直接つなぐ（[skill-plugins](skill-plugins.md)）。OpenScreen は 2026-11-17 まで Gateway・Tunnel 経由で portal に載せていたが、アプリを起動していないと server が `error` のまま残り、Tunnel・Gateway の構成も OpenScreen のためだけにあった
- **手元の MCP でも、Mac の外の client から使う理由があれば載せる**: personal-mcp のカメラ（`camera`）は電子工作中の手元を claude.ai・スマホからも見せるために載せている。手元を撮れる server なので、Access は本人のメールだけ・session 1h にし、使わないときは server を止める（止めている間は `error` のまま残るのは受け入れている）
- **自動実行はこの Mac では人の grant を継承する**: CI・他のマシンからは service token で server の tool が見えず（下記）、token も無いので portal は使えない。一方この Mac の無人実行（Orca automation の pi・codex）は、人が一度ログインした grant をそのまま使う — Managed OAuth は refresh token を背景で更新するので「人のログインが無い経路」にはならない。scheduled task は今のところ MCP を使っていないが、無人の実行から portal の全 upstream に届く状態は残る。止めたいときは client 側で切る（pi は `--no-mcp`、Codex は `[mcp_servers.mcphub] enabled = false` を local に置く。base が持たない key なので `chezmoi apply` で戻らない）
- **各 client の初回は OAuth ログインが要る**: `codex mcp login mcphub` / `pi mcp login mcphub` / `devin mcp login mcphub`、Claude Code は `/mcp`。redirect が localhost・loopback になるため portal Access app の DCR で `allow_any_on_localhost`・`allow_any_on_loopback` を有効にしている（Access policy で本人のメールに限るので、登録できても本人以外は通らない）。grant の `session_duration` は 720h（30 日。2026-10-21 に 24h から延長 — ローカル 4 client の日次再ログインを避ける）で、切れたら再ログインする。access token は 15m のまま
  - Codex は `oauth_resource` を設定しなくても `resource` を送る（discovery の protected resource metadata、無ければ server URL。`codex mcp login mcphub --no-browser` が出す authorization URL に `resource=https%3A%2F%2Fmcp.wwwyo.dev%2Fmcp` が入るのを確認済み）。`oauth_resource` を足すと `resource` が二重に付くので設定しない
- **Cloudflare API MCP の scope は Cloudflare の同意画面で選ぶ**（以下は `mcphub` に server `cloudflare` を載せていた 2026-10 の記録。いまは `mcp-marketing` の `cloudflare-small` で、2 回目の同意の redirect は `mcp-marketing.wwwyo.dev/servers-callback` になる）: Cloudflare MCP は `search`・`execute`（Code Mode）で全 API を呼ぶため、tool 単位では read/write を分けられず、境界は OAuth の scope だけ。同意画面の Read only に、実行・コストだけで壊れるものが無い write（`cache.purge` `browser-rendering.write` `url-scanner.write` `websearch.run` `ai.write` `aig.run` `ai-search.run` `rag.run` `workers-observability.write`）を Advanced で足して渡している（2026-10-22）。`access*`・`mcp-portals.write`・`account-api-tokens.write`・`memberships.write`・`teams*`・`argotunnel.write`・`dns.write`・`zone*.write`・`secrets-store.write` は portal・Access・Tunnel や domain を書き換えられるので渡さない。Workers デプロイ・D1/KV/R2 の write は用途が出たら個別に足す（不足 scope は Cloudflare MCP が再同意を求める）
  - 同意は 2 回ある。ダッシュボードの「サーバーの認証」（redirect `dash.cloudflare.com/.../oauth-callback/cloudflare`）は portal の tool 同期用で、これが無いと server が `waiting` のまま portal に出ない。`on_behalf: true` なので実際の呼び出しは利用者ごとの token を使い、利用者として portal にログインした最初の client で 2 回目の同意（redirect `mcp.wwwyo.dev/servers-callback`）が出る。利用者 token はメール単位で portal が持ち、client 間で共有される（Claude Code で同意した後、Codex は再同意なしで connected だった）。再同意すると全 client の scope が置き換わる。既定は Minimal なので毎回 scope を入れ直す
  - client（Claude Code 等）が持つのは portal への Access token だけで、Cloudflare の token は手元に来ない
- Claude Code の `mcphub` は wwwyo/skills の core plugin が宣言する（marketplace の core entry の inline `mcpServers`、2026-11-17 に `~/.claude.json` の user scope 登録から移した）。手元の `core@synced` を有効にすれば入り、`claude mcp add` は使わない。tool 名は plugin の名前空間が付いて `mcp__plugin_core_mcphub__*` になり、permission はこれを allow する（Devin は自前の設定で `mcp__mcphub__*`）。user scope に `mcphub` が残っていると、同じ URL の plugin server は重複として外され user scope 側が使われるので、移行したマシンでは、新しい session で `claude mcp list` に `plugin:core:mcphub` が出るのを確かめてから `claude mcp remove -s user mcphub` で消す（同期は次の session 開始時に届くので、先に消すと `mcphub` が無い時間ができる）。claude.ai の connector に同じ URL の portal があっても、Claude Code は endpoint で重複を判定し plugin 側を使う
  - この allow は portal の全 upstream の自動承認になる（旧 `mcp__context7__*` より広い）。portal は承認を server 単位でしか分けられず（tool 単位の呼び出し認証を持たない）、Code Mode では code 実行 tool 1 つが全 upstream を呼ぶため。personal の X 取得（1 回ごとに課金）も含む。カメラは `mcp-media` に分けたので、`mcphub` の allow には入らない。upstream の権限は context7・fudoki が読み取りのみで、shell・filesystem・画面操作は無い。queria は利用者ごとの OAuth で、レポートの作成・更新・削除・fork は portal で無効にしてあるので、自動承認の範囲は読み取りと `submit_feedback`。Cloudflare API は今の `mcphub` には無い（`mcp-marketing` の entry を allow すると、同意した scope がそのまま自動承認の範囲になる。下記）。都度確認に戻したければこの entry を消す

## 手元（dotfiles 管理）

Tunnel・Gateway network policy・CIDR route は loopback の upstream のための経路で、OpenScreen のために作り、2026-11-27 から personal-mcp のカメラ（`127.0.0.1:47822`）が使っている。Tunnel 名 `openscreen-mcp-proxy` は作成時のまま。

- Tunnel の常駐: `home/Library/LaunchAgents/dev.wwwyo.mcp-tunnel.plist`。ログは `~/Library/Logs/mcp-tunnel.log`。
- token: `MCP_PORTAL_TUNNEL_TOKEN`（`home/dot_config/mise/config.mcp-tunnel.toml`、age）。`MISE_ENV=mcp-tunnel` のときだけ読まれる global config に置き、通常の shell へ注入しない。
- cloudflared は global mise config の exact pin を使う。
- 再起動: `launchctl kickstart -k gui/$(id -u)/dev.wwwyo.mcp-tunnel`

## Cloudflare 側の state（`cf` CLI で作成。ダッシュボードに出ない設定がある）

portal・MCP server・それらの Access app の正本は dotfiles の [`mcp/cloudflare/`](https://github.com/wwwyo/dotfiles/tree/main/mcp/cloudflare) の宣言。`apply.py` で差分を表示し、`--apply` で反映する（使い方は dotfiles の AGENTS.md）。下の表は構成の説明なので、値が食い違ったら宣言と `apply.py` の差分表示を正とする。Tunnel・Gateway policy・DNS はまだ宣言に無い。

| 種類 | 値 |
| --- | --- |
| Tunnel | リモート管理。ingress は `http_status:404` だけ、`warp-routing` 有効 |
| Tunnel CIDR route | `127.0.0.1/32` → 上の Tunnel（default virtual network） |
| Gateway network policy | L4 block: `net.dst.ip in {127.0.0.1} and not(net.dst.port in {47822})`（名前 `Loopback via tunnel: only camera MCP port`。2026-11-27 に 47821 から変更） |
| MCP server | `personal`: `https://personal-mcp.mix-mix.workers.dev/mcp`（wwwyo/personal-mcp の `worker/`、Void で Cloudflare Workers）、`auth_type: bearer`、`secure_web_gateway: false`（token は Worker の secret と共有し、personal-mcp の `worker/fnox.local.toml` の `MCP_BEARER_TOKEN`）、portal `wwwyo` に `on_behalf: false`。Access app は本人のメールだけ・session 1h。手順は personal-mcp の `docs/setup.md` |
| MCP server | `camera`: `http://127.0.0.1:47822/mcp`、`auth_type: bearer`（token は camera サーバーと共有し、dotfiles の `config.camera-mcp.toml`（age、`MISE_ENV=camera-mcp`）の `CAMERA_MCP_TOKEN`）、`secure_web_gateway: true`。portal `media` に `on_behalf: false`（2026-11-27 に `wwwyo` から移した）。Access app は本人のメールだけ・session 1h。起動手順は personal-mcp の `docs/camera.md` |
| MCP server | `openscreen` は 2026-11-17 に portal `wwwyo` から外し、server と Access app を削除した（OpenScreen は Claude Code の local plugin から直接つなぐ） |
| MCP server | `context7`: `https://mcp.context7.com/mcp`、`auth_type: bearer`（`CONTEXT7_API_KEY` を Cloudflare に保存。context7 は `Authorization: Bearer` で key を受ける）、`secure_web_gateway: false`（公開 upstream なので Gateway・Tunnel を通さない） |
| MCP server | `fudoki`: `https://api.fudoki.dev/mcp`、`auth_type: unauthenticated`、`secure_web_gateway: false` |
| MCP server | `queria`: `https://mcp.queria.io`、`auth_type: oauth`（利用者ごとの OAuth）、`secure_web_gateway: false`。portal `wwwyo` に `on_behalf: true` で載せている。レポートを書き換える `create_report` `update_report` `delete_report` `fork_report` は portal の `updated_tools` で無効（2026-11-13）。`submit_feedback` は送信前に preview と確認を挟むので有効のまま |
| MCP server | `trustmrr`: `https://trustmrr.com/api/mcp`、`auth_type: bearer`（key は Cloudflare にだけある）、`secure_web_gateway: false`。portal `wwwyo` に `on_behalf: false` で載せている（2026-11-17 にコード外で足され、宣言へ取り込んだ） |
| MCP server | `cloudflare-small`: `https://mcp.cloudflare.com/mcp`、`auth_type: oauth`（DCR。client 登録は portal が自動で行い、手動の client_id は持たない）、`secure_web_gateway: false`。tool は `docs` `search` `execute` `whoami`。portal `marketing` にだけ載せている（以前 `wwwyo` にあった server `cloudflare` は今は無い） |
| MCP server | `buffercom`: `https://mcp.buffer.com/mcp`、`auth_type: bearer`（Buffer の key。mise の `BUFFER_API_KEY`（age）にもあり、宣言の `credential_env`）、`secure_web_gateway: false`。tool は投稿・アイデア・テンプレートの読み書きで、削除も含む。登録時に hostname の先頭へ入っていた空白は、2026-11-13 に dotfiles の `apply.py --recreate buffercom` で作り直して消した（Access app は残り、利用者ごとの portal 接続は認可し直しが要った） |
| MCP server | `composio`: portal `marketing` 用の Composio tool router session の `mcp.url`（`https://backend.composio.dev/tool_router/<session_id>/mcp`）、`auth_type: bearer`（`x-api-key` header に Platform の `ak_` key）、`secure_web_gateway: false`。toolkit は GSC と GA。GSC は読み取りの `LIST_SITES` `GET_SITE` `SEARCH_ANALYTICS_QUERY` `INSPECT_URL` `LIST_SITEMAPS` `GET_SITEMAP` と、書き込みの `SUBMIT_SITEMAP`。auth config は `gsc-sitemap`（scope `webmasters`）。GA は readOnlyHint の tool 60 件で、auth config は `ga-readonly`（scope `analytics.readonly`）。Composio 側の user_id は `wwwyo`。旧 `gsc-readonly` は 2026-11-13 に無効化した。tool の一覧は dotfiles の `mcp/composio/sessions/marketing.json` にある |
| MCP portal | `marketing`: `mcp-marketing.wwwyo.dev`、`code_mode: default_on`、portal 側 `secure_web_gateway: false`、server は `composio`・`buffercom`（`on_behalf: false`）と `cloudflare-small`（`on_behalf: true`）。Access policy は `Cloudflare account members` |
| MCP portal | `wwwyo`: `mcp.wwwyo.dev`、`code_mode: default_on`（2026-10-21 に `off` から変更。2026-11-27 に一時 `opt_in` にして同日戻した。client は `?codemode=off` で個別 tool に戻せる）、portal 側 `secure_web_gateway: false`、server は `context7`・`fudoki`・`personal`・`trustmrr`（`on_behalf: false`）と `queria`（`on_behalf: true`）。`fudoki` は upstream が 503（提供停止）を返している。 2026-11-27 に `paper` を外し、server と Access app も削除した |
| MCP portal | `media`: `mcp-media.wwwyo.dev`（DNS は `mcp-media` CNAME → `gateway.agents.cloudflare.com`、proxied）、`code_mode: off`、portal 側 `secure_web_gateway: false`、server は `camera`（`on_behalf: false`）。2026-11-27 に作った |
| Access app | portal 用（type `mcp_portal`、Managed OAuth + DCR、redirect は ChatGPT の callback・claude.ai の `https://claude.ai/api/mcp/auth_callback`・任意の localhost/loopback）と server 用（type `mcp`、`destinations: [{type: via_mcp_server_portal, mcp_server_id}]`、server ごとに 1 つ）。`wwwyo`・`media` portal と `context7`・`fudoki`・`camera`・`personal` の app は、本人のメールだけを Allow する app 専用の policy（session 1h）。`marketing` portal と、`composio`・`cloudflare-small`・`buffercom`・`queria`・`trustmrr` の server 用 app は reusable policy `Cloudflare account members`（session 24h）。`marketing` portal の app にも 2026-11-13 に `wwwyo` と同じ Managed OAuth・DCR（`oauth_configuration`）を入れた |
| DNS | `mcp` CNAME → `gateway.agents.cloudflare.com`（proxied） |

## MCP を追加するとき

1. `cf mcp servers create --body @file`（token を含む body はファイル経由で渡し、`--dry-run` に token を通さない）。loopback の server は `secure_web_gateway: true`、公開 remote の server は `false`。同期が `ready` になるまで `cf mcp servers read` で待つ。
2. server 用の Access app（type `mcp`）を作る。無いと portal 経由でその server が見えない。
3. 対象の portal（`wwwyo`・`marketing`・`media`。text 以外を返す tool があれば `media`）に `cf mcp portals update` で server を足す。どの portal でも省いた項目は既定値に戻るので、全項目を指定する。upstream が OAuth の server は、ダッシュボードの server 画面で「サーバーの認証」を押して同期させる（`cf` に相当コマンドが無い）。`on_behalf` は「その upstream の権限を利用者ごとに分けるか」で決める — 利用者ごとの同意・token を持つ OAuth upstream は `true`（現状 `cloudflare-small`・`queria`）、portal が共有 credential で呼ぶ bearer・認証なし upstream は `false`。1人運用なら `false` でも動くが、client を共有した時点で権限境界が消える。同意した scope 外の操作を upstream が拒否するかは未検証 — 拒否の挙動を前提に自動承認の範囲を広げない
   - 1段目（manager 側の同期）で止まっている signature は `status: waiting` + `authentication_status: required` + `last_successful_sync: null`。2段目の同意はその後に出るので、切り分けはこの3つで行う
4. loopback の server だけ、Gateway network policy の許可 port に足す。
5. shell・filesystem 書き込みなど強い権限の MCP は `wwwyo` に入れず（upstream の OAuth 同意で scope を絞れるものは除く）、`<name>-mcp.wwwyo.dev` の別 portal にする（hostname は 1 段。2 段は Universal SSL の対象外）。権限ではなく渡す agent を用途で絞るための portal は `mcp-<用途>.wwwyo.dev`（`mcp-marketing`）と名付けて区別する。
6. 最後に dotfiles の worktree で `python3 mcp/cloudflare/apply.py --import` を実行し、作った server・Access app・portal の変更を宣言へ取り込む。差分表示（`--apply` なし）が「宣言どおり」になるのを確かめてから PR にする。宣言が正本なので、取り込まないと次の apply が差分として報告する

## ハマりどころ

- **server ID に `-` を入れない。** portal は tool 名を `serverId_toolName` で扱い、`openscreen-local` だと ChatGPT からの呼び出しが `Invalid tool name format` で失敗した。英数字だけにする。
- **ChatGPT には `/mcp` まで含む URL を登録する。** ルートでも OAuth は通るが、その後の action discovery が失敗する。
- **`cf mcp portals update` は省いた項目を既定値に戻す。** `--servers` だけ送ると `code_mode` が `opt_in`、portal 側 `secure_web_gateway` が `true` に戻った。毎回全項目を指定する。
- **portal に server を足しても、既存の利用者 grant からは見えない。** server・Access app・portal を設定し sync も `ready` でも、接続し直した client にすら新 server の tool が出なかった（2026-11-10、`composio` 追加時）。client 側で portal の接続を切ってログインし直すと見えた。portal の server を差し替えるときは、旧 server を外す前に利用者の再ログインまで済ませるか、再ログインまで旧 server を残す
- **作成直後の portal は数十秒 403 を返す。** 401 と `WWW-Authenticate` が返るまで待ってから判断する。
- **service token では server の tool が見えなかった。** portal と server の両方に Service Auth policy を付け、`on_behalf: false` にしても portal 自身の管理用 tool しか出なかった。動作確認は本人ログインの経路で行う。
- **tool の無効化はダッシュボードに出ないことがある。** API の `servers[].updated_tools: [{name, enabled: false}]` なら設定できる。
- **`127.0.0.1/32` の route は loopback の全 port に届きうる。** network policy の対照実験（rule ON で接続失敗、OFF で到達）で効くことを確認済み。新しい port を公開するときは policy の許可も更新する。
- **Gateway の「Route traffic through Cloudflare Gateway」は server 側の設定が効く。** portal 側の同名設定は server の登録・tool 同期には効かない。private upstream へ portal から届かないときは server の `secure_web_gateway` を先に見る。route は IP 単位で port を指定できないため、port 制限は上記の L4 network policy で行う（doc に記載が無く、検証 server とルール on/off の対照で確認した）。
- **portal 経由の Composio 呼び出しが HTTP 429 になることがある。** 2026-11-13 に、session を同期した直後と旧接続を消す前後で、`composio_*` だけが数分 429 になった（同じ portal の buffer は通った）。Composio を直接呼ぶと org の上限 2000/60s に余裕があり、成功した。portal 側の制限か、portal に置いた key の上限かは未特定。数分待って再試行すると通るので、429 だけで設定の不備と判断しない
- **portal は upstream の Server Instructions を引き継がない。** upstream が `initialize` で `instructions` を返していても、portal 経由の接続では消える（2026-10-22 に codemode 有効・無効の双方で実測）。用途を初期コンテキストに載せたいなら client 側（`AGENTS.md`・system prompt）か upstream の tool description に書く — upstream の Instructions は client が server を直接登録する経路でだけ効く。有無は `initialize` を直叩きすれば確認できる。
- **codemode の値でモデルに見える tool 構成が変わる。** Code Mode が有効だと portal の Code Mode tool 5個だけが見え、無効だと upstream の個別 tool が見える（2026-11-27 の `wwwyo` で `?codemode=off` にすると、context7 2・fudoki 14・personal 7・queria 14・trustmrr 5 の 42 個）。Code Mode の execute は upstream の結果を文字列として返すので、image content は画像として届かない（base64 が出力上限で切れる）。MCP Apps（UI `_meta`）を Code Mode と併用できるかは未検証 — ChatGPT からの UI 動作確認は取れていない。
- **`cf` は `gh` と同じく sandbox 外で実行する。** sandbox 有効時は通信制限で `cf mcp servers list` 等が落ちる。権限設定を緩めず escalated で実行する。
- **Codex で mcphub の tool が載らないときは層で分ける。** (1) `~/.codex/config.toml` に `[mcp_servers.mcphub]` が実在するか（`home/.chezmoitemplates/codex-base.toml.tmpl` 由来）(2) session が見ている tool 一覧（Code Mode なら portal の 5 tool だけ、無効なら upstream の個別 tool）(3) `codex mcp login mcphub` の grant が残っているか。
- **portal は tool 単位の呼び出し認証を持たない**（tool の on/off と alias のみ）。強い権限の分離は別 portal + 短い Access セッション、または同一 MCP の 2 server 登録で行う。**portal を分けても ChatGPT は同一会話で複数コネクタの tool を混ぜられる**ため、分割の目的は権限・credential の分離であって tool mixing の防止ではない（基本は 1 portal、強い権限だけ別 portal）。
