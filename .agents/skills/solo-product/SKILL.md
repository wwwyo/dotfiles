---
name: solo-product
description: "個人開発のサービスを公開・運用・緊急停止するときの安全確認の入口。インターネット公開・custom domain 設定・認証・rate limit・Turnstile・課金対策を設計するとき、公開前レビュー、abuse・請求異常の調査で参照する。実装一般・Cloudflare 製品選定は対象外（cloudflare skill 側）。"
---

# Solo Product

個人・少人数で運営するサービスを公開し、事故らせず運用し続けるための判断 skill。「何を確認すれば安全か」の一覧ではなく、「このプロジェクトのリスクはどこか」を特定して対策・検証へ進むためのルーター。セキュリティと課金が主軸。

## この skill が扱うもの・扱わないもの

- 扱う: 公開の是非と入口設計（ドメイン・preview・認証）、abuse・課金暴走への防御設計、公開前/運用中/緊急時の確認、provider 固有の公開・保護・課金設定（Cloudflare・Vercel）の管理。
- 扱わない: Cloudflare 製品の選定全般（[cloudflare](../cloudflare/SKILL.md)）、secret の保管・注入の手順（[secret-env](../secret-env/SKILL.md)）、コード品質のレビュー。

## 判断の順序

新しい公開・設定変更を始める前に、まずリスクの形を特定する。対策の優先順位はプロジェクトで決める — 全部を一律に適用する正解はない。

1. **入口を数える。** そのサービスへ到達できる URL をすべて挙げる（custom domain・provider の生成 URL・preview URL・deployment URL・管理画面・webhook）。入口ごとに「誰が呼んでよいか」を決める。入口の存在に気づかないまま「ログイン必須にした」と誤認するのが最頻出の事故。
2. **課金の増幅経路を数える。** 1 リクエストが何を消費するか（AI 呼出・外部 API・ストレージ write・queue・ログ）。無料枠内で収まるか、超えたら誰が払うか。公開 = 他人が増幅ループを回せる、と考える。
3. **人間 vs 機械の判定を分ける。** 誰でも読める静的ページと、bot 耐性・認証・課金上限が要る動的 API は別の入口として扱う。人間性確認と認証と rate limit（流量）は別物で、互いに代替しない。
4. **fail closed の出口を決める。** 月予算を超えた・abuse を検知したとき「何を止めるか、どうやって止めるか」を公開前に決める。通知しかない制御と実際に止まる制御を混同しない。

## Routing

| やること | 読む reference |
| --- | --- |
| Cloudflare の公開・保護・課金設定 | [Cloudflare の設定・公開・課金](references/cloudflare.md) |
| Vercel の公開・保護・課金設定 | [Vercel の設定・公開・課金](references/vercel.md) |
| アカウント・secret・認証/認可・input・dependency・プライバシーの確認 | [references/security.md](references/security.md) |
| 課金対策の設計・観測・kill switch・abuse 増幅の分析 | [references/cost.md](references/cost.md) |
| ブラウザ拡張の公開（BYOK の key 保管・content script の脅威モデル） | [references/extension.md](references/extension.md) |

フェーズ別の読み方:

- **公開前** — 上の「判断の順序」を実行し、利用する provider reference の該当節（公開する入口だけ読めばよい）と security.md の「公開前に必須」へ進む。
- **運用中** — cost.md の観測・通知を設定済みか定期的に確認し、security.md のローテーション・依存更新を回す。
- **緊急時（abuse・請求異常・secret 漏洩）** — cost.md の kill switch / 停止操作と security.md の漏洩時対応から先に実行し、事後に恒久対策へ戻る。

## 未確立

- Cloudflare・Vercel 以外の provider（AWS・GCP・Fly 等）の個別手順は未整備。使うときは同じ分類（入口・人間判定・流量・課金上限・観測）で一次資料を当たり、学んだら reference を追加する。
- 決済処理の設計は現状対象外 — 扱う場合は payment provider の webhook 検証・idempotency の公式資料を必須確認とし、ここに追記する。
