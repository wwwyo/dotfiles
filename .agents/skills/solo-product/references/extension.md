# ブラウザ拡張を公開する

ブラウザ拡張（Chrome Extensions / WXT 等）を個人プロダクトの入口にするときの、secret の置き方と content script の脅威モデル。Web アプリ側の入口・認証・abuse 対策は [security.md](security.md)・[cost.md](cost.md) を参照。

## BYOK の key の置き場

BYOK で利用者自身の API key を預かる場合は拡張内に置くことになる（開発者の共有 secret を拡張に持たせない、という security.md の原則とは別の話）。

- 置き場は `chrome.storage.local`（拡張 ID スコープ）。`window.localStorage` はページ origin の storage でページ JS から読めるので使わない。
- `chrome.storage.local.setAccessLevel({ accessLevel: 'TRUSTED_CONTEXTS' })` で content script からの読み取りを遮断する（既定は `TRUSTED_AND_UNTRUSTED_CONTEXTS` で content script も読める）。
- 粒度は領域全体でアイテム単位ではない — キーと同居する mode・model 等も content script から読めなくなる。それらが要るなら別領域に分けるか background 経由で渡す。
- `setAccessLevel` のブラウザ対応状況は確認してから使う（MDN は Firefox 向けにも文書化しているが、storage 領域ごとの対応差がある）。対象ブラウザで使えない・同じ防御が要るなら、content script に実値を持たせず background への問い合わせ（`chrome.runtime.sendMessage`）で必要最小限（キーの有無・mode・model）だけ受け取る設計にする。設定変更は background が broadcast する。

## content script の脅威モデル

- ページ JS は拡張 API を直接叩けない（isolated world と拡張 ID 境界）。共有面は DOM・イベント・メッセージ中継だけ。
- 最小権限の考え方は「長期秘密をページ同居プロセス（content script）に置かない」こと。侵害時の被害を「キー漏洩」から「機能の駆動（料金・濫用）」へ一段下げられる。
- 機能駆動への対策はリクエスト経路で分ける: 自前のバックエンドを経由する場合は人間性確認・rate limit・同時実行上限を設けられる（[共通の課金・abuse 設計](cost.md)）。Cloudflare 固有の検証 API と設定は [Cloudflare の設定・公開・課金](cloudflare.md)。BYOK key で background から provider へ直接送る構成ではそれらは効かず、濫用は利用者 key の枠を消費する — ページ由来メッセージの検証と、provider 側の quota/spend limits で受ける。

出典: https://developer.chrome.com/docs/extensions/reference/api/storage、https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/API/storage/StorageArea/setAccessLevel （確認 2026-10-08）
