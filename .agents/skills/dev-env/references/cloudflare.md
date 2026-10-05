# Cloudflare

`cf` CLI を優先する方針は global AGENTS.md 側。ここには触って分かった非自明な事実だけを置く。

- **`cf` は beta で未対応領域がある**（`tail`・secret の個別操作など）。未対応の操作は Wrangler に残す。`wrangler.jsonc` → `cloudflare.config.ts` への移行は `cf migrate` で機械的にできる
- **R2 の有効化には R2 subscription の追加が必要**（無料枠あり。有効化には支払い方法の登録が前提。Workers Paid 契約は不要 — 月 $5 は Workers Paid の最低料金で別の subscription）。subscription が無いアカウントでは API が `403 / error 10042`（`NotEntitled`）を返し続け、CLI 側では突破できない。10042 は KV namespace 不正等でも出る entitlement 汎用コード。支払い方法の登録はユーザー承認が要るので、R2 を使う設計では前提条件として早期に確認を上げる
- **公開データの配信は R2 public bucket 直配信 + CDN cache + rate limit で足りる**。ただし cache / rate limit / WAF / Bot Management は custom domain（bucket と同じ account に zone として追加した domain）必須 — `r2.dev` の公開 URL は rate-limit 付きの開発用で、本番配信には使わない。配信用 Worker を噛ませるのは「完成前の URL への直接アクセスを止めたい」等の制御が必要な場合だけ
- **Bot Fight Mode は API client にも challenge を出し得る**。機械的アクセスを受け付ける zone では有効化しない — bot 対策は一律排除ではなく cache + rate limit で受ける（こちらも custom domain 必須）
- **Workers Builds の結果は GitHub Actions の check には出ない**。build の成否・ログは `cf builds` か Cloudflare ダッシュボードで確認する（Actions 側を待っても来ない）。`watch_paths` には worker のエントリだけでなく共有依存ファイル（shared packages・共通設定）も含める — 含まれない変更では build が skip される
- **Workers AI binding のキャンセルは伝播しない** — 呼び出し側を abort・timeout しても binding 側の推論は走り切る（課金と log に残る）。AI Gateway の `collectLog` 系の設定はリクエスト側の指定が既定値を上書きする挙動なので、期待どおり収集されないときはリクエスト経路ごとの指定を疑う
