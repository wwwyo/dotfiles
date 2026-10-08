# 課金・abuse 対策（個人開発）

個人で破産しないための課金防御の考え方。中心は「誰かが増幅ループを回せるか」を公開前に潰すことと、「止まる手段」と「気づく手段」を分けて用意すること。

## 増幅経路の分析（公開前に必須）

1 リクエスト・1 操作が何を消費するか書き出す。特に危険なのは「安い入口 → 高い裏処理」の形:

- 公開 API → AI 呼出（1 回 ¥x）・外部有料 API・大きな storage write・queue 投入 → fanout して複数処理。
- retry ループ・queue の再送・cron の多重起動・AI の自動 retry で、1 回の失敗が N 回の課金になる。
- 無限ループ・相互呼出し（Worker→Worker、webhook→自分）、再帰的な queue enqueue。
- 大きな request body・レスポンス、長い wall time（CPU 時間外だが timeout 設計は必要）。
- ビルド・preview・CI の実行コスト（公開 repo で誰でも PR を出せると CI が回る）。

**対策の順序**: まず安い拒否を前に置く（認証・Turnstile・WAF rate limit、いずれも cloudflare.md §3-5）。拒否チェーンの内部順序もコストになる — Turnstile の siteverify 呼出し自体が外部 subrequest なので **rate limit より後に置く**。先に siteverify へ送ると偽トークンの連打がそのまま外部への subrequest 増幅になる。token の有無・形式の確認（外部送信しないローカル検証）は先にしてよい。次に量を絞る（ユーザー別 quota・全体 quota・同時実行・body/timeout/fanout 上限）。最後に消費の上限（CPU limit・AI の最大 token・retry 上限）。rate limit は「流量」であって「支出上限」ではない — 分散・長時間・正規アカウント経由を抜かれるので、**厳密な月次上限が必要なら自分のアプリ側で quota を集計する**か provider の課金制御を使う。強制（enforcement）できる制御がある provider もある — Cloudflare AI Gateway の spend limits は window 内の累計支出が上限に達すると以降を 429 で block できる（Access 経由なら `cf.user_id` 単位も）。使っている gateway/provider に強制手段があるかを先に確認する。ただし Cloudflare AI Gateway の spend limits は同時実行中のリクエストが設定額を超え得るうえ支出集計がベストエフォートの推定なので、厳密な月次上限の代替にはならない — 厳密さが要るなら自前 quota と併用する。AI Gateway には別途 rate limit（期間あたりの request 数上限）も付けられるので、spend limits と併せて設定しておくと増幅の早期遮断になる。AI Gateway を使うなら Authenticated Gateway も on にしてリクエストの認証を必須にする — off のままだと gateway URL を知る第三者が自前の provider key でこちらの gateway を通せる。token は secret として管理し、自前の Worker/バックエンドからのみ付ける。gateway を挟まない構成では、provider 側に支出上限の設定（budget limit・usage limit）があれば有効化しておく — key が駆動されても口座全体で止まる最後の砦になる。

## quota と fail closed の設計

- ユーザー別 quota: 「1 ユーザー 1 日 N 回」など認証ユーザー単位でカウントする。集計先は精度要件で選ぶ — KV は結果整合で取りこぼしがあるため概算向き、厳密な上限なら Durable Object や D1 transaction で枠を先に確保する（cloudflare.md §4）。匿名なら Turnstile + IP を補助にするが、IP は NAT で共有されるので厳密な単位ではない。
- 全体 quota: アカウント全体の 1 日/1 月あたりの予算を決め、カウンタが閾値を超えたら新規の高コスト処理を拒否する（fail closed）。「閾値超えても通る」仕組みを quota と呼ばない。
- kill switch: 予算を超えた・abuse を検知したとき即座に止める手段を公開前に決める。Worker の flag による 503 返却・route/Access 変更・deploy 巻き戻し・外部 AI key の revoke・provider 側の quota 設定。手順と置き場所を控え、必要な権限で実行できることを確認する。
- 「止める」は「検知する」と別。通知・ダッシュボードは気づく手段であり、止めない。**通知が来てから寝ていて気づかない、の間に請求は増える** — 夜間・不在時の暴走を想定して、自動で閉じる or 閾値の低い段階で自動拒否する仕組みを持つ。

## 観測・通知

- コストの可視化: provider の usage/billable usage ダッシュボード（Cloudflare なら Billing > Billable Usage が invoice と同系統）、外部 AI なら provider 側の usage・予算設定。
- 通知: 予算の段階閾値（例 50% / 80% / 100%）で alert を設定。通知先は自分が実際見る channel。通知だけで安心しない（上記 fail closed）。
- 異常の兆候: request 数・CPU・AI 呼出数の急増、429 の増加、特定 user/IP への集中。Workers Logs/Analytics で自分で `rate_limited` 等のイベントを出すと追いやすい（rate limit binding は dashboard に出ない）。
- 定期確認: 週次で usage と請求見込みを見る。増加の原因が正常利用か abuse かを区別する。

## 運用・復旧

- バックアップと復元を公開前に一度試す（DB・storage・secret の再発行手順）。バックアップがあっても復元手順が無ければ機能しない。
- rollback: 前の version へ戻す手順を確認しておく。version にはコードだけでなく binding・互換性設定・その時点の secret 値も含まれるため、rollback で旧 secret へ戻り得る — rotate 直後に巻き戻すと旧値が復活する。version 外の state（routes・workers.dev・custom domain・Access・保存データ）は rollback では戻らないので、「元通り」になる範囲を区別する。
- 監視: uptime・エラー率・コストの 3 点を最低限見る。個人では網羅的監視より「異常時に自分へ届く通知」の確実性を優先する。
- 本番と preview/開発を分ける: preview が本番 DB・本番 secret・本番 quota に届かないようにする。分離できるのは Previews 機能（`previews` block）— Version URL はその version の既存 resource を共有するため隔離できない（cloudflare.md §3）。
- インシデント後: 被害額・原因・時系列を記録し、恒久対策（quota・kill switch・通知の追加）を入れてから再公開する。

## 見送ってよいもの（個人開発）

- 複雑な WAF ルール・Bot Management・Enterprise 級の DDoS 対策 — Cloudflare 既定の DDoS 防御に任せ、個人でカスタムは要所だけ。
- 厳密な会計システムの自作 — 「おおよそ閾値で止める」で足りるなら自作 quota は簡易カウンタでよい。厳密さが要るのは課金請求や SLA があるとき。
- 多層の冗長化 — 単一障害点を引き受ける代わりに、復旧手順を明確にしておく方が個人では現実的。
出典: https://developers.cloudflare.com/ai-gateway/features/spend-limits/、https://developers.cloudflare.com/workers/platform/pricing/、https://developers.cloudflare.com/billing/manage/budget-alerts/ （確認 2026-10-04）
