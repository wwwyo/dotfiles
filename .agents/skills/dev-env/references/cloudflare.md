# Cloudflare AI Gateway の開発環境設定

この reference は、手元で Cloudflare AI Gateway を試すための tool・認証・環境設定だけを扱う。Cloudflare の公開入口・保護・課金・復旧設定は [solo-product の Cloudflare 設定](../../solo-product/references/cloudflare.md)に置く。

## Access 経由で試す

- `cloudflared` は global mise config で exact pin する。
- request URL は global mise の `CF_AI_ACCESS_URL` に age 暗号化して保持する。URL を repo・skill・ログへ平文で転記しない。
- 試用時は [Access 経由の実験手順](../../cloudflare/references/ai-access.md)に従い、認証後に `cloudflared access curl` で呼ぶ。global の長期 gateway key は配布せず、Access JWT も global env・repo・ログへ保存しない。
- PoC の dev 環境のプロダクトから AI を呼ぶ経路は、従来どおり OpenCode を使う。手元の試用とプロダクトの呼び出し経路を混同しない。

secret の保管・注入は [secret-env](../../secret-env/SKILL.md)、mise の pin・trust は [mise](mise.md)を参照する。

## Gateway のログ設定

AI Gateway の `collectLog` 系の設定はリクエスト側の指定が既定値を上書きする挙動なので、期待どおり収集されないときはリクエスト経路ごとの指定を疑う。
