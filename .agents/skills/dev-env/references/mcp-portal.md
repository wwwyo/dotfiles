# 個人の MCP を MCP Server Portal に集約する

ChatGPT・claude.ai（web・スマホ）とローカル agent から、この Mac の loopback で動く MCP（OpenScreen）と公開 remote MCP（context7・fudoki）を 1 つの入口で使う構成。2026-10-13 に自前 proxy（wwwyo/access-mcp-proxy、archive 済み）から置き換えた。判断の経緯は同 repo の ADR 0002 と PRD `docs/prd/mcp-portal/` に残っている。

```text
ChatGPT / claude.ai / ローカル agent ──OAuth──▶ portal mcp.wwwyo.dev ─┬─▶ Gateway ──▶ Tunnel ──▶ 127.0.0.1:<port>
                                                                       ├─▶ https://mcp.context7.com/mcp（key は Cloudflare 保管）
                                                                       └─▶ https://api.fudoki.dev/mcp（認証なし）
```

## portal に載せる MCP の基準

portal は個人の MCP の入口を 1 つにまとめる経路。ChatGPT・claude.ai に加え、ローカル agent（Codex・pi・Devin・Claude Code）も `https://mcp.wwwyo.dev/mcp` の 1 entry だけを持つ（2026-10-21 に context7・fudoki の個別設定から切り替えた）。目的は context の節約で、Code Mode（`default_on`）により server・tool が増えても agent に載る tool 定義は Code Mode の少数の tool に留まる。credential も client に渡さない。

- **載せる**: 個人で常用する MCP。credential を隠せるもの（context7）・loopback にしか無いもの（OpenScreen）・認証の無い公開 MCP（fudoki）も同じ portal に入れる。Access・Cloudflare の障害でまとめて使えなくなるのは受け入れている
- **自動実行からは使わない前提**: service token では server の tool が見えない（下記）ため、CI・scheduled task など人のログインが無い経路から portal は使えない。必要になったら個別に判断する（ユーザーの許可を取る）
- **各 client の初回は OAuth ログインが要る**: `codex mcp login wwwyo` / `pi mcp login wwwyo` / `devin mcp login wwwyo`、Claude Code は `/mcp`。redirect が localhost・loopback になるため portal Access app の DCR で `allow_any_on_localhost`・`allow_any_on_loopback` を有効にしている（Access policy で本人のメールに限るので、登録できても本人以外は通らない）。grant の `session_duration` は 24h で、切れたら再ログインする
- Claude Code の MCP は `~/.claude.json`（dotfiles 管理外）にあるため、各マシンで `claude mcp add --transport http -s user wwwyo https://mcp.wwwyo.dev/mcp` で登録する。permission は `mcp__wwwyo__*` を allow

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
| MCP server | `openscreen`: `http://127.0.0.1:47821/mcp`、`auth_type: bearer`（OpenScreen の token を Cloudflare に保存）、`secure_web_gateway: true` |
| MCP server | `context7`: `https://mcp.context7.com/mcp`、`auth_type: bearer`（`CONTEXT7_API_KEY` を Cloudflare に保存。context7 は `Authorization: Bearer` で key を受ける）、`secure_web_gateway: false`（公開 upstream なので Gateway・Tunnel を通さない） |
| MCP server | `fudoki`: `https://api.fudoki.dev/mcp`、`auth_type: unauthenticated`、`secure_web_gateway: false` |
| MCP portal | `wwwyo`: `mcp.wwwyo.dev`、`code_mode: default_on`（2026-10-21 に `off` から変更。client は `?codemode=off` で従来の tool 一覧に戻せる）、portal 側 `secure_web_gateway: false`、server ごとに `on_behalf: false` |
| Access app | portal 用（type `mcp_portal`、Managed OAuth + DCR、redirect は ChatGPT の callback・claude.ai の `https://claude.ai/api/mcp/auth_callback`・任意の localhost/loopback）と server 用（type `mcp`、`destinations: [{type: via_mcp_server_portal, mcp_server_id}]`、server ごとに 1 つ）。どれも本人のメールだけ Allow |
| DNS | `mcp` CNAME → `gateway.agents.cloudflare.com`（proxied） |

## MCP を追加するとき

1. `cf mcp servers create --body @file`（token を含む body はファイル経由で渡し、`--dry-run` に token を通さない）。loopback の server は `secure_web_gateway: true`、公開 remote の server は `false`。同期が `ready` になるまで `cf mcp servers read` で待つ。
2. server 用の Access app（type `mcp`）を作る。無いと portal 経由でその server が見えない。
3. `cf mcp portals update wwwyo` に server を足す。
4. loopback の server だけ、Gateway network policy の許可 port に足す。
5. shell・filesystem 書き込みなど強い権限の MCP は `wwwyo` に入れず、`<name>-mcp.wwwyo.dev` の別 portal にする（hostname は 1 段。2 段は Universal SSL の対象外）。

## ハマりどころ

- **server ID に `-` を入れない。** portal は tool 名を `serverId_toolName` で扱い、`openscreen-local` だと ChatGPT からの呼び出しが `Invalid tool name format` で失敗した。英数字だけにする。
- **ChatGPT には `/mcp` まで含む URL を登録する。** ルートでも OAuth は通るが、その後の action discovery が失敗する。
- **`cf mcp portals update` は省いた項目を既定値に戻す。** `--servers` だけ送ると `code_mode` が `opt_in`、portal 側 `secure_web_gateway` が `true` に戻った。毎回全項目を指定する。
- **作成直後の portal は数十秒 403 を返す。** 401 と `WWW-Authenticate` が返るまで待ってから判断する。
- **service token では server の tool が見えなかった。** portal と server の両方に Service Auth policy を付け、`on_behalf: false` にしても portal 自身の管理用 tool しか出なかった。動作確認は本人ログインの経路で行う。
- **tool の無効化はダッシュボードに出ないことがある。** API の `servers[].updated_tools: [{name, enabled: false}]` なら設定できる。
- **`127.0.0.1/32` の route は loopback の全 port に届きうる。** network policy の対照実験（rule ON で接続失敗、OFF で到達）で効くことを確認済み。新しい port を公開するときは policy の許可も更新する。
- **Gateway の「Route traffic through Cloudflare Gateway」は server 側の設定が効く。** portal 側の同名設定は server の登録・tool 同期には効かない。private upstream へ portal から届かないときは server の `secure_web_gateway` を先に見る。route は IP 単位で port を指定できないため、port 制限は上記の L4 network policy で行う（doc に記載が無く、検証 server とルール on/off の対照で確認した）。
- **portal は tool 単位の呼び出し認証を持たない**（tool の on/off と alias のみ）。強い権限の分離は別 portal + 短い Access セッション、または同一 MCP の 2 server 登録で行う。**portal を分けても ChatGPT は同一会話で複数コネクタの tool を混ぜられる**ため、分割の目的は権限・credential の分離であって tool mixing の防止ではない（基本は 1 portal、強い権限だけ別 portal）。
