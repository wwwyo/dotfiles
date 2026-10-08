# Cloudflare でサービスを公開する

Workers への公開設定・入口管理・abuse 対策・コストの一次情報。金額・制限・プラン別機能は変わりやすいため、各節末にリンクと確認日を置く。設定を実行する前に最新の公式ドキュメントで再確認する。確認日 2026-10-04。

Cloudflare 操作の優先順位（`cf` CLI 優先・`cf cli search` で探す・未移行プロジェクトは Wrangler 継続）は global ルールと dev-env skill が SSOT なのでここでは繰り返さない。この reference は公開設定に関わる state だけを扱う。Access アプリケーションや Builds の状態など、config ファイルで宣言できない resource がある — 「IaC に書いたから管理下」とは限らない（§7）。詳細は [cloudflare skill](../../cloudflare/SKILL.md)。

## 1. Custom domain と TLS

- Custom Domain は **その Worker を origin とする DNS レコード＋証明書を Cloudflare が自動発行する仕組み**。domain/subdomain の全 path がその Worker に向く。Workers & Pages > Worker > Settings > Domains & Routes から追加。
- Custom Domain と workers.dev は **同じ Worker への独立した入口**。custom domain に設定しても workers.dev へ転送・統合されない — 片方を公開してもう片方が残ったままだと、残った方が素通し入口になる（§2）。
- Route（`example.com/api/*` のような path 単位）と Custom Domain（host 全体、path 条件なし・wildcard 非対応）を混同しない。Worker を外部 origin の前段に置きたいなら Route、Worker 自体がサイトなら Custom Domain が推奨形。
- DNS レコード（CNAME で自分で張る方式）は Worker 向けでは不要 — Custom Domain が DNS と証明書を自動で作る。既存 CNAME がある hostname には作れない。生成される証明書は Advanced Certificate で、深いサブドメインも Universal SSL 非依存でカバーされる。Custom Domain 削除時に証明書は自動削除されない。
- 検証: `curl -sI https://app.example.com` が 200 と Worker の応答を返すこと、`https://<worker>.<subdomain>.workers.dev` の状態（有効か disable か）を別途確認すること。

出典: https://developers.cloudflare.com/workers/configuration/routing/custom-domains/ （確認 2026-10-04、doc updated 2026-09-29）

## 2. 不要な workers.dev 入口を disable する

- 公開入口を custom domain に絞るなら `workers.dev` route を disable にする。disable は **入口を閉じるだけで Worker 自体も custom domain も止まらない**。
- Cloudflare 側（dashboard の Domains & Routes で Disable、または API/cf）と repo 側を両方揃える。揃えないと次回 deploy で復活する:
  - `cf`（cloudflare.config.ts）: `workersDev: false`
  - Wrangler（wrangler.toml/jsonc）: `workers_dev = false`
- dashboard だけで disable して config を書かないと、Wrangler deploy で `workers.dev` route が再有効化される（公式 Caution）。逆に `routes` を書いて `workers_dev` を省略すると `false` と推論される。
- `workers.dev` disable は Version URLs（旧 preview URLs）・Previews・Deployment URLs を disable **しない**。別設定なので §3 を見る。
- 検証: `curl -sI https://<worker>.<subdomain>.workers.dev` が 404/エラーになること、custom domain は生きていること。deploy 後に再確認。

出典: https://developers.cloudflare.com/workers/configuration/routing/workers-dev/ （確認 2026-10-04、doc updated 2026-09-22）

## 3. Preview / Version URL を公開するときは先に Access で守る

用語: 旧「preview URLs」は **Version URLs** に改名（config キーは `preview_urls` のまま）。さらに別物として branch/PR ごとの隔離環境 **Previews**（`wrangler preview`、Wrangler 4.135.0+）がある。どちらも URL は公開される。

- Version URLs はデフォルトで `workers_dev` の設定に従う（workers.dev が disable なら Version URL もデフォルト disable）。**workers.dev disable と preview/version URL enable は別の設定** — `preview_urls = true` を明示した場合 workers.dev が無効でも preview 入口が開く。
- Version URL・Preview URL はデフォルトで公開。公開する前に Cloudflare Access でサインイン必須にする。設定はダッシュボード（Workers & Pages > Worker > Access、または overview の Protect all Workers）か Access applications API（self_hosted app の `destinations`）。
- 保護スコープの違い:
  - `preview_worker`（Worker 指定・preview のみ）/ `all_preview_workers`（アカウント全 Worker の preview）— **本番の traffic には認証を要求しない**。個人開発の既定はこれ。
  - `worker` / `all_workers`（production + preview 両方）— Worker の routes・custom domain・workers.dev・preview すべてに効く。公開サービスに `worker`/`All traffic` を付けると本番もログイン必須になるので用途を限定する。
  - hostname/path 単位の self-hosted Access app — `admin.example.com` や `example.com/internal/*` など部分公開に使う。その URL だけを守り、Worker 全体は守らない。
  - account 全体 Access 配下で特定 Worker だけ公開したい場合は、Worker-level の bypass ポリシーを付ける。
- 認証方式の選択: 個人なら policy は「Cloudflare アカウントのメンバー」が最も確実。メール条件を使う場合、`email_domain` はそのドメインの検証済みアドレスを持つ全員を許可する — `gmail.com` のような共有ドメインを指定すると事実上公開になる。自分だけなら Zero Trust 側でメールアドレス完全一致（`emails`）のポリシーにする。外部 IdP/OIDC・service token・複雑なポリシーは Zero Trust 側で高度設定。機械からのアクセス（CI・他サービス）は Service Auth ポリシー + service token（`CF-Access-Client-Id`/`CF-Access-Client-Secret` header）。**service token をクライアントアプリや公開リポジトリに埋め込まない** — 共有 token は全員が持つので制御にならず、漏洩時に全利用者を止められない。
- Worker 側は `ctx.access.getIdentity()` または JWT / `/cdn-cgi/access/get-identity` でサインイン済みユーザーを読める。
- 注意点:
  - Access のログインは `CF-Authorization` cookie で維持される。ブラウザの fetch が `credentials: "omit"` だと cookie が送られずログイン済みでも 403/302 になる — preview から API を呼ぶ SPA では `credentials: "include"` と cookie の SameSite/ドメインを確認。
  - preflight（OPTIONS）には cookie が付かないため Access が 403 を返す。Access app の CORS 設定で「Cloudflare に preflight 応答させる」または「OPTIONS を origin へ bypass」する（bypass するなら origin 側で CORS を強制すること）。
  - iframe・third-party cookie ブロック・Safari の挙動で Access cookie が送られないケースがある。Incognito での検証は避ける。
  - Turnstile の sitekey は hostname 紐付け — preview の hostname を widget の許可 hostname に含めるか、preview 用 widget を分ける（§5）。
  - preview は本番と secret/リソースを分離する。Previews 機能では `previews` block で変数・secret・binding を別定義でき、Durable Object/container は自動で preview 専用になる。KV/D1/R2 などは preview 専用 resource を明示的に bind して分離する — 本番と同じ resource を bind した場合だけ共有される。service binding は例外で、Preview から本番 deployment を呼ぶ — config を書かなくても本番へ届く経路なので、preview では bind 先を変えるか外す。preview 入口が本番 DB に届く構成は「preview だから安全」ではない。
  - Version URLs は Durable Object 使用 Worker では生成されない。Version URL のログは Workers Logs/tail で見られない。
- 検証: 未ログインの別セッションで preview URL が Access ログイン or 403 になること、本番 URL が認証なしで応答すること（previews-only なら）。`curl` で GET と OPTIONS（preflight）の両方を確認する — `-I` は HEAD なので OPTIONS の挙動は確認できない。

出典: https://developers.cloudflare.com/workers/versions-and-deployments/version-urls/、https://developers.cloudflare.com/workers/previews/、https://developers.cloudflare.com/workers/configuration/cloudflare-access/、https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/cors/、https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/ （確認 2026-10-04）

## 4. Rate limiting — 安い拒否を早い段に置く

課金はリクエストが Worker に届いて実行されると発生する。**Worker 内で弾く処理自体にも CPU/リクエスト課金が乗る**。高コスト処理（AI 呼出・重い計算）の前に、安い拒否をできるだけ前段に置く。

- **WAF rate limiting rules** — Worker 実行前に Cloudflare エッジで弾く。プラン差は 3 軸で分かれる（確認 2026-10-04）。ルール数: Free 1・Pro 2・Business 5（Enterprise 別途）。expression: Free は Path/Verified Bot のみ、Pro で Host/URI/Full URI/Query、Method/Source IP/User Agent は Business 以上。counting characteristics（何で数えるか）: Free/Pro は IP のみ、Business で IP with NAT support、Query/Host/Header/Cookie/ASN 等の key は Enterprise with Advanced Rate Limiting のみ。period: Free 10s・Pro 最大 1 分・Business 最大 10 分。重要な注意: **「正確に N リクエスト止める」仕組みではない** — counter 反映に最大数秒の遅延があり、data center 単位でカウントされる。絶対的な上限として扱わない。
- **Worker Rate Limiting binding** — Worker コード内から `env.X.limit({key})` で呼ぶ。key はユーザー ID・API key・tenant・path 等任意の文字列。period は 10 または 60 秒のみ。**カウンタは Cloudflare location 単位でローカル** — Sydney で 100/分を超えても他 location からは来る。global な厳密上限ではない。eventually consistent で「正確な会計」には使えないと公式が明記。dashboard に binding が出ないので、429 応答は Workers Logs / Analytics Engine で自分で観測する。IP を key にするのは非推奨（モバイル NAT で巻き込む）。
- 両者の使い分け: 単純な無差別アクセスの流量制御は WAF rule（エッジで止まり課金も減る）。「ログインユーザーごと」「課金が重い endpoint だけ」は binding で key 設計。分散攻撃・正規アカウントの大量呼出しは per-IP では防げない — ユーザー別 quota・全体 quota を別途設ける。
- rate limit は課金上限ではない。厳密な支出制御が必要なら、利用者別 quota・アカウント全体の日次/月次 quota・同時実行数制限・リクエスト body 上限・timeout・外部 API への fanout 制御・retry 回数・AI の最大 token を組み合わせる。quota の集計先は整合性を確認して選ぶ — KV は結果整合で原子的な read-modify-write がなく並行更新を取りこぼすため厳密な上限に使えず、厳密さが要るなら Durable Object（単一の強整合オブジェクト）や D1 の transaction で枠を先に確保する。増幅の分析は [cost.md](cost.md)。
- 検証: ローカル or preview で `limit()` が `{ success: false }` を返し Worker が 429 を返すこと。WAF rule の発動は zone の Security Events（Security > Events）で確認する。429 が返ってもログに記録されるか確認。

出典: https://developers.cloudflare.com/waf/rate-limiting-rules/、https://developers.cloudflare.com/workers/runtime-apis/bindings/rate-limit/ （確認 2026-10-04）

## 5. Turnstile

人が書き込む・高コスト処理を呼ぶ公開フォームに入れる。**人間性確認であって、認証・権限・確実な支出上限ではない** — token を渡した人が大量に呼べば課金は増える（§4 と併用）。

- sitekey は公開前提（HTML に出る）。secret key はサーバー側のみ — Worker の secret として管理し、フロントエンド・拡張・公開 repo に置かない（保管は secret-env skill）。
- **server-side の Siteverify 呼出しは必須**。widget だけでは何も守れない: token は偽造できる・300 秒で失効・**1 回しか検証できない**（replay は `timeout-or-duplicate`）。
- Siteverify 応答の `success` だけでなく `hostname`（意図した domain で発行されたか）・`action`/`cdata` を検証する。`idempotency_key` を付ければ検証呼出しを安全に retry できる。
- 公開前に、開発用 test keys が本番に残っていないか確認する。test sitekey の `1x…`（常に pass）/`2x…`（常に fail）はどの domain でも動く。`3x…` は interactive challenge を強制するキーで、pass/fail 固定ではないので混同しない。本番 secret key は dummy token を拒否するため、本番 secret と dummy sitekey の混在は必ず fail する — それで検出できる。
- preview 環境は hostname が違うため、widget の Hostname Management に preview hostname を足すか preview 用 key を分ける。

出典: https://developers.cloudflare.com/turnstile/get-started/server-side-validation/、https://developers.cloudflare.com/turnstile/troubleshooting/testing/ （確認 2026-10-04）

## 6. コストの発生源と止め方

発生源の把握: Workers（request・CPU time・Workers Logs の書込）、外部 AI API（provider 側課金、Cloudflare 外）、KV/D1/R2（read/write/storage）、Queues、Logpush、ビルド分。Workers Paid は $5/月 minimum で request・CPU が月次 included + 従量。無料枠は request 100k/日・CPU 10ms/回。**Workers 自体の egress・bandwidth は課金なし**（2026-10-04 時点の Workers 料金ページ）— ただし Containers の network egress や R2 Infrequent Access の data retrieval など製品ごとの例外がある。使う製品の pricing を個別に確認する。

- Free プランは日次 100k request 制限（UTC 0 時 reset）。超過時の挙動は route の fail mode 次第: **fail closed は `1027` を返し、fail open は Worker を bypass**（Worker が無いものとして扱う）— fail open だと請求は止まっても Worker 内の認証・quota・CPU 上限も同時に止まるため、security-critical な Worker は公式も fail closed を推奨。fail mode は route ごとに設定する。Paid は request 無制限・CPU 5 分/回（default 30s）なので **暴走はそのまま請求になる**。denial-of-wallet 対策として `limits.cpu_ms`（Wrangler/`cloudflare.config.ts` または Settings > CPU Limits）で 1 呼出あたり CPU を絞る — 1 リクエストの最大消費は絞れるが、リクエスト総量は別に抑える（§4）。
- 通知と強制の区別:
  - **Budget alerts**（Billing > Billable Usage）— アカウント横断の usage-based 支出が閾値を超えたらメール。**informational only で、サービスを止めない・上限でもない**。請求確定は invoice。
  - **Usage notifications**（Notifications）— 製品ごとの指標（bytes・request 数等）で通知。これも通知のみ。
  - Cloudflare の請求通知系は自動停止しない。**確実に止めたいなら自分で kill switch を持つ**（下記）。
- kill switch の作り方（予算を超えたら fail closed）: Worker 先頭で kill flag（KV/env var/config）を読み即 503 返却、workers_dev/route の disable、deploy の巻き戻し、外部 AI key の revoke。フラグを置く場所と操作手順を予め決めておく — 慌てて探すと遅い。
- 観測: Billable Usage dashboard（invoice と同じ系統の日次内訳）、Workers Analytics、Workers Logs/Logpush。通知は Budget alerts + 製品別 usage notification を併用し、閾値は「月予算の 50%/80%」のように段階化する。
- ロールバック: Versions/Deployments から前の version へ戻せる。version にはコード・binding・その時点の secret 値が含まれるため、rotate 後に巻き戻すと旧 secret が復活し得る（cost.md「運用・復旧」）。version 外の state（routes・workers.dev・custom domain・Access・保存データ）は戻らない — 入口の desired state は config 側で管理する。

出典: https://developers.cloudflare.com/workers/platform/pricing/、https://developers.cloudflare.com/workers/platform/limits/、https://developers.cloudflare.com/billing/manage/budget-alerts/、https://developers.cloudflare.com/billing/manage/billable-usage/ （確認 2026-10-04）

## 7. config/IaC と dashboard state の境界

- `cloudflare.config.ts`（cf）/ wrangler.toml で管理できる: Worker コード・routes・custom domain・workers_dev・preview_urls・bindings・limits・vars 等。**config にある項目は、deploy すると宣言値へ寄せられる** — dashboard で変えても次回 deploy で戻る（§2 の workers_dev が典型）。desired state は config 側に書く。
- config で管理できない・別管理の state: Access application・service token・WAF custom rule・Turnstile widget・Zero Trust 設定・Budget alerts・deploy された secret 値。これらは API/dashboard の操作対象。`cloudflare.config.ts` に書けないからと宣言できるとは限らない — 「管理対象外であること」をプロジェクトの docs に明記する。
- Wrangler にだけある設定と cf にだけある設定があるので、プロジェクトがどちらで deploy するかを確認してから config を書く。未移行 Wrangler プロジェクトに cf 前提の記述を足さない。
- secret の値そのものは config に書かない（`wrangler secret put` 相当の API / cf の secret 操作で入れる）。
- 公開サービスは https のみで配信する。セキュリティの前提として、zone 設定の Always Use HTTPS（`always_use_https`）を on にして http を 301 → https にする（確認: `curl -sI http://<domain>/`）。off のままだと http/https 両方で 200 配信され、平文アクセスを許すうえ重複コンテンツにもなり得る。
