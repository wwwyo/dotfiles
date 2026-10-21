# 個人の MCP を MCP Server Portal に集約する

ChatGPT・claude.ai（web・スマホ）とローカル agent から、この Mac の loopback で動く MCP（OpenScreen）と公開 remote MCP（context7・fudoki）を 1 つの入口で使う構成。2026-10-13 に自前 proxy（wwwyo/access-mcp-proxy、archive 済み）から置き換えた。判断の経緯は同 repo の ADR 0002 と PRD `docs/prd/mcp-portal/` に残っている。

```text
ChatGPT / claude.ai / ローカル agent ──OAuth──▶ portal mcp.wwwyo.dev ─┬─▶ Gateway ──▶ Tunnel ──▶ 127.0.0.1:<port>
                                                                       ├─▶ https://mcp.context7.com/mcp（key は Cloudflare 保管）
                                                                       └─▶ https://api.fudoki.dev/mcp（認証なし）
```

## portal に載せる MCP の基準

portal は個人の MCP の入口を 1 つにまとめる経路。ChatGPT・claude.ai に加え、ローカル agent（Codex・pi・Devin・Claude Code）も `https://mcp.wwwyo.dev/mcp` の 1 entry だけを持つ。client 側の server 名は `mcphub`（portal ID の `wwwyo` とは別。agent・人が名前から中身を推測できるように付けた）で、tool は `mcp__mcphub__*` に見える（2026-10-21 に context7・fudoki の個別設定から切り替えた）。入口と credential を portal に集約する。Code Mode は `opt_in`（通常モードが標準）。MCP Apps は描画 tool 自体の UI metadata が host に見える必要があり、Code Mode を標準にすると画面を出せなくなるため。画面を使わず context を節約する接続だけ、URL に `?codemode=search_and_execute` を付ける。

- **載せる**: 個人で常用する MCP。credential を隠せるもの（context7）・loopback にしか無いもの（OpenScreen）・認証の無い公開 MCP（fudoki）も同じ portal に入れる。Access・Cloudflare の障害でまとめて使えなくなるのは受け入れている
- **自動実行はこの Mac では人の grant を継承する**: CI・他のマシンからは service token で server の tool が見えず（下記）、token も無いので portal は使えない。一方この Mac の無人実行（Orca automation の pi・codex）は、人が一度ログインした grant をそのまま使う — Managed OAuth は refresh token を背景で更新するので「人のログインが無い経路」にはならない。scheduled task は今のところ MCP を使っていないが、無人の実行から portal の全 upstream（loopback の OpenScreen を含む）に届く状態は残る。止めたいときは client 側で切る（pi は `--no-mcp`、Codex は `[mcp_servers.mcphub] enabled = false` を local に置く。base が持たない key なので `chezmoi apply` で戻らない）
- **各 client の初回は OAuth ログインが要る**: `codex mcp login mcphub` / `pi mcp login mcphub` / `devin mcp login mcphub`、Claude Code は `/mcp`。redirect が localhost・loopback になるため portal Access app の DCR で `allow_any_on_localhost`・`allow_any_on_loopback` を有効にしている（Access policy で本人のメールに限るので、登録できても本人以外は通らない）。grant の `session_duration` は 720h（30 日。2026-10-21 に 24h から延長 — ローカル 4 client の日次再ログインを避ける）で、切れたら再ログインする。access token は 15m のまま
  - Codex は `oauth_resource` を設定しなくても `resource` を送る（discovery の protected resource metadata、無ければ server URL。`codex mcp login mcphub --no-browser` が出す authorization URL に `resource=https%3A%2F%2Fmcp.wwwyo.dev%2Fmcp` が入るのを確認済み）。`oauth_resource` を足すと `resource` が二重に付くので設定しない
- Claude Code の MCP は `~/.claude.json`（dotfiles 管理外）にあるため、各マシンで `claude mcp add --transport http -s user mcphub https://mcp.wwwyo.dev/mcp` で登録する。permission は `mcp__mcphub__*` を allow（Devin も同じ）
  - この allow は portal の全 upstream の自動承認になる（旧 `mcp__context7__*` より広い）。portal は承認を server 単位でしか分けられず（tool 単位の呼び出し認証を持たない）、Code Mode では code 実行 tool 1 つが全 upstream を呼ぶため。upstream の権限は context7・fudoki が読み取りのみ、OpenScreen が編集中の動画プロジェクトの編集で、shell・filesystem・画面操作は無い。都度確認に戻したければこの entry を消す

## 手元（dotfiles 管理）

- Tunnel の常駐: `home/Library/LaunchAgents/dev.wwwyo.mcp-tunnel.plist`。ログは `~/Library/Logs/mcp-tunnel.log`。
- token: `MCP_PORTAL_TUNNEL_TOKEN`（`home/dot_config/mise/config.mcp-tunnel.toml`、age）。`MISE_ENV=mcp-tunnel` のときだけ読まれる global config に置き、通常の shell へ注入しない。
- cloudflared は global mise config の exact pin を使う。
- 再起動: `launchctl kickstart -k gui/$(id -u)/dev.wwwyo.mcp-tunnel`

## Cloudflare 側の state（`cf` CLI で作成。ダッシュボードに出ない設定がある）

| 種類 | 値 |
| --- | --- |
| Tunnel | リモート管理。ingress は `http_status:404` だけ、`warp-routing` 有効 |
| Tunnel CIDR route | `127.0.0.1/32` → 上の Tunnel（default virtual network） |
| Gateway network policy | L4 block: `net.dst.ip in {127.0.0.1/32} and not(net.dst.port in {<公開する port>})` |
| MCP server | `openscreen`: `http://127.0.0.1:47821/mcp`、`auth_type: bearer`（OpenScreen の token を Cloudflare に保存）、`secure_web_gateway: true`。tool は編集中の動画プロジェクト（クリップ・トリム・ズーム・字幕・音声）の読み書きで、shell・filesystem・画面操作は持たない |
| MCP server | `context7`: `https://mcp.context7.com/mcp`、`auth_type: bearer`（`CONTEXT7_API_KEY` を Cloudflare に保存。context7 は `Authorization: Bearer` で key を受ける）、`secure_web_gateway: false`（公開 upstream なので Gateway・Tunnel を通さない） |
| MCP server | `fudoki`: `https://api.fudoki.dev/mcp`、`auth_type: unauthenticated`、`secure_web_gateway: false` |
| MCP portal | `wwwyo`: `mcp.wwwyo.dev`、`code_mode: opt_in`（2026-10-21 に `default_on` から変更。MCP Apps 用の接続は通常 URL、Code Mode が必要な client だけ `?codemode=search_and_execute` を付ける）、portal 側 `secure_web_gateway: false`、server ごとに `on_behalf: false` |
| Access app | portal 用（type `mcp_portal`、Managed OAuth + DCR、redirect は ChatGPT の callback・claude.ai の `https://claude.ai/api/mcp/auth_callback`・任意の localhost/loopback）と server 用（type `mcp`、`destinations: [{type: via_mcp_server_portal, mcp_server_id}]`、server ごとに 1 つ）。どれも本人のメールだけ Allow |
| DNS | `mcp` CNAME → `gateway.agents.cloudflare.com`（proxied） |

## MCP を追加するとき

1. `cf mcp servers create --body @file`（token を含む body はファイル経由で渡し、`--dry-run` に token を通さない）。loopback の server は `secure_web_gateway: true`、公開 remote の server は `false`。同期が `ready` になるまで `cf mcp servers read` で待つ。
2. server 用の Access app（type `mcp`）を作る。無いと portal 経由でその server が見えない。
3. `cf mcp portals update wwwyo` に server を足す。
4. loopback の server だけ、Gateway network policy の許可 port に足す。
5. shell・filesystem 書き込みなど強い権限の MCP は `wwwyo` に入れず、`<name>-mcp.wwwyo.dev` の別 portal にする（hostname は 1 段。2 段は Universal SSL の対象外）。

## ハマりどころ

- **Code Mode は MCP Apps の描画 tool を隠す。** `tools/list` に出るのは検索・実行と管理用の5 tool で、`_meta.ui.resourceUri` はない。通常モードでは `fudoki_render_expenditure_view` の UI metadata と `resources/read` の HTML を取得できることを実測した。ChatGPT で画面を使う接続は通常モードにし、接続先の tool 定義を再取得する。
- **upstream の Server Instructions は portal から返らない。** 風土記への直接の `initialize` は `instructions` を返すが、portal の応答には通常モード・Code Mode ともに無い（2026-10-21 実測）。upstream に設定しただけでモデルに用途が伝わると扱わない。
- **server ID に `-` を入れない。** portal は tool 名を `serverId_toolName` で扱い、`openscreen-local` だと ChatGPT からの呼び出しが `Invalid tool name format` で失敗した。英数字だけにする。
- **ChatGPT には `/mcp` まで含む URL を登録する。** ルートでも OAuth は通るが、その後の action discovery が失敗する。
- **`cf mcp portals update` は省いた項目を既定値に戻す。** `--servers` だけ送ると `code_mode` が `opt_in`、portal 側 `secure_web_gateway` が `true` に戻った。毎回全項目を指定する。
- **作成直後の portal は数十秒 403 を返す。** 401 と `WWW-Authenticate` が返るまで待ってから判断する。
- **service token では server の tool が見えなかった。** portal と server の両方に Service Auth policy を付け、`on_behalf: false` にしても portal 自身の管理用 tool しか出なかった。動作確認は本人ログインの経路で行う。
- **tool の無効化はダッシュボードに出ないことがある。** API の `servers[].updated_tools: [{name, enabled: false}]` なら設定できる。
- **`127.0.0.1/32` の route は loopback の全 port に届きうる。** network policy の対照実験（rule ON で接続失敗、OFF で到達）で効くことを確認済み。新しい port を公開するときは policy の許可も更新する。
- **Gateway の「Route traffic through Cloudflare Gateway」は server 側の設定が効く。** portal 側の同名設定は server の登録・tool 同期には効かない。private upstream へ portal から届かないときは server の `secure_web_gateway` を先に見る。route は IP 単位で port を指定できないため、port 制限は上記の L4 network policy で行う（doc に記載が無く、検証 server とルール on/off の対照で確認した）。
- **portal は tool 単位の呼び出し認証を持たない**（tool の on/off と alias のみ）。強い権限の分離は別 portal + 短い Access セッション、または同一 MCP の 2 server 登録で行う。**portal を分けても ChatGPT は同一会話で複数コネクタの tool を混ぜられる**ため、分割の目的は権限・credential の分離であって tool mixing の防止ではない（基本は 1 portal、強い権限だけ別 portal）。
