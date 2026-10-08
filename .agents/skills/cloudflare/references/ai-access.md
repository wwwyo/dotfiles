# Cloudflare AI experiments through Access

Cloudflare AI / Workers AI を手元で試すときは、Cloudflare Access で保護した AI Gateway の custom domain を使う。長期の gateway key を global に配布する代わりに、ユーザーのログインと期限付き Access session で呼び出す。

## Request

URL は global mise の `CF_AI_ACCESS_URL` に age 暗号化して格納する。これは `/compat/chat/completions` を含む完全な request URL。平文の URL を skill・コード・設定へ転記しない。環境変数が見えない agent / GUI の実行経路では `mise exec --` で注入する。未設定なら設定を確認し、長期 gateway token や既定の gateway endpoint へ迂回しない。

mise 管理の `cloudflared` を使い、Access の認証済み session で呼び出す:

```bash
mise exec -- sh -c 'cloudflared access curl "${CF_AI_ACCESS_URL:?CF_AI_ACCESS_URL is required}" -sS --fail-with-body \
  --json '\''{
    "model": "workers-ai/@cf/meta/llama-3.1-8b-instruct-fast",
    "messages": [{"role": "user", "content": "Reply with hello."}],
    "max_tokens": 16
  }'\'''
```

`workers-ai/` prefix は AI Gateway の compat endpoint 用。モデルは用途に合う安価な open model を選び、モデルごとの現行仕様を確認する。

未認証・session 期限切れなら `cloudflared` のブラウザログインをユーザーに完了してもらう。必要なら先に `cloudflared access login "$CF_AI_ACCESS_URL"` を実行する。認証後も各 request に Access credential が必要で、`cloudflared access curl` が付与する。SDK / 別 HTTP client を使う場合も、その session の credential を request に付ける。Access JWT を global env・repo・ログに保存しない。

## Verification and scope

- 認証なしの request が Access に拒否され、認証済み request は gateway key なしで成功することを確かめる。HTTP status に加えて JSON の `choices` にモデルの応答があることを見る。ログイン画面の HTML を成功とみなさない。
- この方針は対話的な Cloudflare AI の実験に適用する。PoC のプロダクトから AI を呼ぶ場合は共通の OpenCode 方針に従う。デプロイ済みサービスや無人の定期処理へ個人の Access session を持ち込まない。
- URL の暗号化は repo への平文掲載を避けるため。接続先を隠すことを認証の代わりにしない。

公式仕様: [AI Gateway と Cloudflare Access](https://developers.cloudflare.com/ai-gateway/configuration/cloudflare-access/)、[CLI から Access を使う](https://developers.cloudflare.com/cloudflare-one/tutorials/cli/)。custom domain に有効な Access JWT を送れば、AI Gateway token を併送する必要はない。
