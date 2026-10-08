# Vercel の設定・公開・課金

Vercel プロジェクトの公開・保護・課金まわりの非自明な仕様。料金表の転記ではなく、設定ミス・誤認を防ぐ制約を中心に置く。各節は 2026-10-08 に公式 docs で確認。アカウントの実効設定は未変更・未検証。公開判断と共通の security/cost 概念は [solo-product](../SKILL.md) を参照する。

## 入口と保護範囲

出典: [Generated URLs](https://vercel.com/docs/deployments/generated-urls) / [Deployment Protection](https://vercel.com/docs/deployment-protection) / [Automation bypass](https://vercel.com/docs/deployment-protection/methods-to-bypass-deployment-protection/protection-bypass-automation)

- **生成 URL は保護を設定しなければ公開**。`<project>-<hash>-<scope>.vercel.app`（commit 単位）・`<project>-git-<branch>-<scope>.vercel.app`（branch 最新）・`<project>-<scope>.vercel.app`（production 最新）など複数の URL が同じ deployment を指す。custom domain を足しても生成 URL は残るので、custom domain だけ守ればよいわけではない
- **保護は「method（Vercel Authentication / Password / Trusted IPs / Passport）× scope（保護する URL 群）」の組み合わせ**。scope として Standard Protection（production domain 以外すべて）と All Deployments（production domain 含む全部）がある。**Standard Protection でも production の生成 URL は守られる** — `VERCEL_URL`/`VERCEL_BRANCH_URL` で production 内部に fetch していると公開前提が崩れて 401 系になるので、リクエストが来た domain を使うよう書き換える必要がある
- Password Protection は Pro で $20/月・project 単位（Hobby 不可）、Trusted IPs・Passport は Enterprise 専用。production のみを守る設定は Trusted IPs ＝ Enterprise でしかできない
- **Protection Bypass for Automation**（全 plan）: project ごとの secret を `x-vercel-protection-bypass` header または同名 query param で送ると全 deployment の保護を bypass できる。webhook 等 header を持てない相手は URL に secret が載る — **ログ・履歴に残る経路なので header を優先**し、漏れたら secret を再生成する。deployment では選択した secret が `VERCEL_AUTOMATION_BYPASS_SECRET` の System env に入る。build log では常に redact される。複数 secret を tool ごとに分けられる。更新・削除後は古い deployment の env 値が無効になるため、新しい値で redeploy する。共有 secret を frontend や repo に配布しない
- team 設定で新規 project の保護デフォルトを決められる（None も選べるので、作られた project が無防備にならないか team 側を見る）

## Firewall / rate limit / Bot 対策

出典: [Firewall](https://vercel.com/docs/vercel-firewall) / [WAF Rate Limiting](https://vercel.com/docs/vercel-firewall/vercel-waf/rate-limiting) / [Bot Management](https://vercel.com/docs/bot-management)

- 実行順序は固定: DDoS mitigation（全 plan 無料・自動）→ IP blocking → WAF custom rules → managed rulesets。期待と違う評価順で悩まないこと
- **rate limit のカウンタはリージョン単位**。同一 key が複数リージョンから来ると設定値を超えて通る — 「グローバルで N req/min」を期待すると過小評価する。Fixed window は全 plan、Token bucket は Enterprise のみ。Hobby は project あたり 1 ルール、Pro は従量課金（料金はリージョン別）
- **Bot protection ruleset は既定 Off**で、有効化してもまず log モードにして効果を見る。JS challenge を出すので、API client・webhook・curl 系の正規トラフィックを自分で塞ぎうる — 信頼済みの機械トラフィックには bypass action の custom rule を先に用意する。AI bots ruleset も既定 Allow（無評価）で、deny を明示しないと AI crawler は通る
- **Cloudflare 等の reverse proxy を前に置くと Bot Protection は正しく機能しない**（検出シグナルが隠れ、proxy の IP ローテーションで再 challenge が多発）。front に別 CDN を噛ませる構成では Vercel 側の bot 対策に頼らない

## Spend Management（課金ストップ）

出典: [Spend Management](https://vercel.com/docs/spend-management)

- **「spend amount の設定」自体は何も止めない**。通知・webhook・Pause Production Deployments のうち pause を ON にしないと従量課金は止まらない（Pro / Enterprise Flex Commit のみ、Hobby には無い）
- **課金チェックは数分ごとで連続ではない**。超過検出から pause まで数分の遅延があり、その間も課金が伸びる — 厳密な hard cap にはならないため、予算より低い閾値とアプリ側の制限を組み合わせる。pause 対象は **全 project の production deployment だけ**で、AI Gateway の API key 利用・v0 課金は止まらない
- pause は project ごとに手動 resume が必要。spend amount を上げても自動では戻らない。visitor には `503 DEPLOYMENT_PAUSED` が出る
- 通知は 50/75/100% の閾値で web/email（100% で SMS も可）、SMS の通知設定はユーザー個人単位で、Owner/Billing 権限の各利用者が設定する
- 対象は metered resource のみで、seat・Marketplace 等の月額 add-on は含まない。billing cycle 途中で現在の spend より低い額を設定すると次回チェックで即 pause される

## Functions の制限と計量

出典: [Functions Limits](https://vercel.com/docs/functions/limitations)

- **maxDuration**: Fluid compute 有効時はデフォルト 300s が全 plan 共通。無効な既存プロジェクトは別の上限・既定値なので、有効状態を先に確認する。Hobby は 300s が上限、Pro/Ent は 800s まで GA、1800s は Beta（runtime 版数制約あり、Secure Compute/Static IPs では使えない）。「timeout した」= 504 `FUNCTION_INVOCATION_TIMEOUT`。無制限が要る処理は Vercel Workflows 側の設計
- **request/response body はともに 4.5MB 上限**（413 `FUNCTION_PAYLOAD_TOO_LARGE`）。アップロード系は Function 経由にせず Blob 等への direct upload にする
- 計量は **active CPU time + provisioned memory time**。Edge runtime は 25s 以内に応答を開始しないと streaming 継続できない（合計 300s まで）
- env var の合計サイズは deployment あたり 64KB（edge runtime の function/Middleware は 1 変数 5KB まで）

## env / secret / preview 分離

出典: [Environment variables](https://vercel.com/docs/environment-variables) / [Config and Secret](https://vercel.com/docs/environment-variables/sensitive-environment-variables)

- env var は **Production / Preview / Development / Custom environments のスコープ単位**で、Preview はさらに branch 指定で上書きできる（branch 固有値が同名の汎用 Preview 値を上書き）。**preview 用の DB・API key を分ける仕組みはこの env scope で自分で張る** — Vercel が preview を自動で分離するわけではない。本番値を Preview に scope しないのが最低ライン
- 型は **Config（保存後も閲覧可）/ Secret（write-only、再表示不可）**。Secret の key 名は後から編集不可・Config へ in-place 変換不可。Secret 値が 32 文字以上なら build log で `[REDACTED]` 化される（32 文字未満の短い secret は redact 対象外なので注意）
- **env var の変更は既存 deployment に適用されない** — 新規 deployment で初めて効く。ローテーションしただけでは稼働中の値は変わらない
- Marketplace integration が注入する env var は connection の scope に従う。Custom environment は provider に preview 値があればそれを、なければ default の secret を使う — 分離したつもりでも共有 credential が降り得るので、provider の default 値と実際の接続先を確認する

## rollback

出典: [Instant Rollback](https://vercel.com/docs/instant-rollback)

- Instant Rollback は **deployment（build 成果物とその時点の env var スナップショット）を指す alias の付け替え**で、プロジェクト設定や現在の env var 値は巻き戻らない。rollback 後の deployment は「その時点の env var」で動くので、rollback 時に rotate 済みの secret が旧値に戻る事故がありうる
- rollback 後は **production domain の自動割当が止まる** — production branch に push しても本番に反映されない。復帰は「別 deployment を promote」する Undo Rollback で、元に戻す操作は別途必要
- custom alias は rollback 対象に含まれない（project の domain 設定と別物）。cron jobs は rollback 先の deployment 時点に戻る
- Hobby は直前の deployment にしか戻せない。Pro/Ent は production に alias された全 deployment が対象

## vercel.json / CLI vs dashboard

出典: [Project Configuration](https://vercel.com/docs/project-configuration) / [vercel.json](https://vercel.com/docs/project-configuration/vercel-json) / [WAF Custom Rules](https://vercel.com/docs/vercel-firewall/vercel-waf/custom-rules)

- file 系（`vercel.json`/`vercel.ts` など、1 project につき 1 つ）が書けるのは build/routing/functions/cron など。domains・Deployment Protection・Spend Management 等は、この build/routing 設定ファイルと別に dashboard/API/CLI で管理する。secret は repo に値を書かず provider の環境設定へ注入する。「vercel.json を見れば全設定が分かる」とは扱わず、外部 state の正本と変更経路も記録する
- 優先順位は一方向ではない: `buildCommand`/`installCommand`/`outputDirectory`/`devCommand`/`framework`/`ignoreCommand`/`regions` は **vercel.json が dashboard の Project Settings を上書きする**。逆に **Fluid compute 有効時は function の memory を vercel.json に書けず dashboard 設定が正**（vercel.json では `functions.maxDuration` だけ上書き可）。項目ごとにどちらが正本か変わるので両方を確認する
- WAF の宣言は `vercel.json` の `routes[].mitigate` でもできるが、対応 action は `challenge`/`deny` のみ。`log`/`bypass`/`rate_limit`/`redirect` まで含む管理は dashboard/API/CLI/Terraform を使う。全 WAF state を `vercel.json` へ移せるわけではない。管理面を混ぜるとどこが正か分からなくなるので経路を一本化する
- ローカルの secret 管理は [secret-env](../../secret-env/SKILL.md)、CLI の pin は [mise](../../dev-env/references/mise.md)を参照する

## 設定後の検証

- 未ログインの HTTP client で custom domain・production 生成 URL・preview URL をそれぞれ呼び、指定した protection scope と一致するかを見る。protected endpoint を自動テストする場合も bypass secret をログへ出さない。
- preview の env scope と接続先 DB を確認する。環境名だけで本番 resource への到達を否定しない。
- Spend Management は通知先だけでなく Pause Production Deployments の有効状態と停止対象を確認する。本番を止める実試験は通常の文書調査では実行しない。
