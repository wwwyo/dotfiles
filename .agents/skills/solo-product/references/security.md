# セキュリティ確認（個人開発）

公開するすべての入口に対して、誰が呼べる・何を読み書きできる・secret はどこにあるかを確認する。企業向けの網羅性は持ち込まず、「個人で破産・炎上しない」ラインを優先する。対策を見送る場合は「どのリスクを引き受けたか」を README か ADR に残す。

## アカウント（公開前に必須）

- プラットフォームのアカウント（Cloudflare・GitHub・AI provider・ドメイン registrar）に MFA/passkey を有効化し、回復コードを mise+age 等の安全な場所に保管する。アカウント乗っ取りは全防御を迂回するので、ここが最優先。
- API token は必要 scope・対象 zone/account に絞る（least privilege）。CI・hook・各 agent ごとに別 token を切り、1つ漏洩したらその token だけ revoke できるようにする。発行日・用途・scope を README か secret 管理のメモに残す（名前有効期間付きが望ましい）。

## Secret（保管・注入・漏洩時）

- secret は平文で repo・設定ファイル・frontend bundle・拡張の storage に置かない。ローカルは mise+age（[secret-env](../../secret-env/SKILL.md)）、サーバー側は provider の secret 機能（`wrangler secret put` 等）で注入。
- frontend・ブラウザ拡張・モバイルアプリに secret を持たせない — 利用者全員が同じ秘密を持つので制御にならない。サイトキー（Turnstile sitekey・publishable key 等「公開を前提に設計されたキー」）は例外で、それが本当に公開前提かを provider 資料で確認する。BYOK 等で利用者自身の key を拡張内に預かる設計は [extension.md](extension.md)。
- 漏洩時: まず revoke/rotate（新しい key を発行してから旧 key を無効化）、repo・コミット履歴・ログ・issue・AI への貼り付け跡を洗う、再発防止として該当経路を skill/フックに反映。rotate の手順は予め各 provider ごとに控えておく。

## 認証・認可・入口の設計

- 「誰が呼べるか」（認証）と「そのユーザーが何を見てよいか」（認可）は別。自分しか使わない管理 API と、全員が使う公開 API、他ユーザーにも開く API は別入口として数える。
- **CORS は認証ではない**。`Access-Control-Allow-Origin` はブラウザの同一生成元ポリシーの緩和であり、curl・別アプリからの直接呼出しは防げない。API の保護は認証（session/JWT/Access 等）で行い、CORS は許可 origin を最小化する補助。
- cookie ベースの認証は CSRF を考える（SameSite・Origin チェック・CSRF token）。bearer token なら CSRF はほぼ不要だが XSS 経由の窃取を考える。
- 認証のあるサービスでは、user A の ID を user B の token で引けないことを必須テストにする（tenant/owner チェック）。admin 系エンドポイントは別 Access ポリシーか別入口で厳しくする。
- webhook・外部サービスからのコールバックは署名検証か固定 secret header で送信者を検証し、重複処理の排除（idempotency key・event ID の記録）を付ける。決済を扱うなら provider 公式の検証ライブラリを使う。

## 入力・upload・外部到達

- 入力検証は server 側で行う。ファイルアップロードはサイズ・Content-Type・拡張子を制限し、保存先（R2 等）の公開設定と別署名付き URL の扱いを確認する。request body 上限を設定する（Workers の request body 上限は zone plan 依存、Free/Pro 100MB — 2026-10-04 確認）。
- ユーザー入力 URL や外部サイトをサーバーから fetch する機能（OGP 取得・インポート等）は SSRF になる — 内部 IP・メタデータ endpoint・`localhost`・private range を拒否リストする。redirect 先も検証する。
- 公開する storage・DB・backup（R2 バケット・エクスポート・ログ）は非公開を既定にし、公開するものだけ個別に開ける。backup が公開 bucket に置かれて全データ流出する事故は頻出。

## Dependency・CI

- 依存は global ルールどおり exact pin + cooldown 7day とし、lock file を commit して定期更新を回す。
- CI の権限を最小にする: deploy token は production deploy だけに、PR preview では secret を読ませない（fork PR で secret が読めてしまう設定は致命傷）。deploy は approve または main 限定にする。
- 公開 repo・issue・PR に secret・内部 URL・個人情報を書かない。過去 commit の履歴も含めて漏洩を確認する。

## ログ・AI trace・プライバシー

- ログ・AI trace（Langfuse 等）・error reporting に、ユーザーの入力全文・API key・個人情報・決済情報を送らない。送る必要がある場合はマスク・サンプリング・保持期間を決める。削除要求に応えられるかを確認する。
- プライバシーポリシー・利用規約・cookie バナーは、収集するデータと法域に応じて必要になる — 法的判断はここで断定せず、対象ユーザーの法域（GDPR・日本の個情保等）を確認して判断する。個人・非商用・データをほぼ持たないサービスでも、メールアドレスや投稿内容を集めるなら何を集めるかの明示が最低ライン。

## 緊急時（漏洩・侵害の兆候）

- まず被害拡大を止める: 該当 token/key の revoke、入口の一時閉鎖（Access・route disable・deploy 巻き戻し）。
- 影響範囲を特定: アクセスログ・audit log・直近の deploy/issue/PR を遡り、いつから・何にアクセスされたかを記録する。
- 恒久対策: 漏洩経路を塞ぎ、学びを skill・hook・check に還元する。

参照: OWASP Top 10 (https://owasp.org/www-project-top-ten/)、OWASP Cheat Sheet Series (https://cheatsheetseries.owasp.org/) — 詳細は各項目の該当 cheat sheet（Authentication / CSRF / SSRF / Secrets Management）を参照。確認日 2026-10-04。
