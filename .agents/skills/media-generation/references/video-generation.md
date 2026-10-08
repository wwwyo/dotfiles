# Video generation — Video A（生成AI）

入口は [SKILL.md](../SKILL.md) の Video A 節。このファイルは実行手順・見積り・制約の詳細。

**確認日: 2026-10-08**（料金・schema は変動する。実行前に出典を再確認し、見積りに確認日を添える）

## 利用経路の選び方

| 経路 | key | 主なモデル | 使いどころ |
| --- | --- | --- | --- |
| **fal（主）** | `FAL_KEY`（登録済み） | `minimax/h3-max/{text,image,reference}-to-video`、`fal-ai/veo3.1/fast/*` 等 | 既定。短い実写系カット、静止画→動画 |
| **WaveSpeed（代替）** | `WAVESPEED_API_KEY`（利用時に登録） | `wavespeed-ai/minimax-h3/{text,image}-to-video` 等 | open-weights 版 H3 を WaveSpeed 自社ホストで回す経路 |
| **Google Veo API（代替）** | `GEMINI_API_KEY`（登録済み） | `veo-3.1-generate-preview` / `-fast` / `-lite` | Google の課金・尺制約に置きたいとき |
| MiniMax 公式 API（参考） | MiniMax 側の key | `MiniMax-H3` / `MiniMax-H3-Max` | 2K や video editing が必要なとき。価格は公式で要確認 |

**区別して扱うこと（重要）**:

- **fal の H3 Max** は fal が open-weight の MiniMax H3 に post-training を施した **fal 固有の variant**（`minimax/h3-max/*` エンドポイント）。
- **WaveSpeed の H3** は **open-weights 版 MiniMax H3 の WaveSpeed 自社ホスト**（`wavespeed-ai/minimax-h3/*`）。WaveSpeed の公式ページ自身が「official `minimax/h3` API とは別の endpoint、独自の解像度・単価」と明記している。
- **同じ「H3」の名前でも、モデル・解像度体系・単価・尺制約が違う。同一モデル・同一料金として計算しない。**
- fal の標準 `minimax/h3`（非 Max）は別 endpoint。2K・reference・video editing はこちら側。

### WAVESPEED_API_KEY の登録（条件付き）

WaveSpeed を選んだときだけ登録する。[secret-env](../../secret-env/SKILL.md) と [mise-age](../../secret-env/references/mise-age.md) に従い、値を平文で表示しない:

```bash
mise set --age-encrypt WAVESPEED_API_KEY='…'   # recipient が自動導出できない場合は skill 内の手順参照
```

登録後は `mise env` で復号値が出ることを確認するだけにする。**現在この変数は未登録** — WaveSpeed を使わないなら登録しない。

## 無料枠と課金を混同しない

- **fal のブラウザ（sandbox / playground）**: サインインで **5本/日まで無料**、1本最大15秒、音声付き、24時間ローリングリセット（[H3 Max ページ](https://fal.ai/minimax-h3-max)、確認日 2026-10-08）。**これはブラウザ枠。API 呼び出しは常に課金で、API 側の無料枠は無い。**
- **Gemini API の Veo 3.1**: Free Tier は「Not available」（[Gemini pricing](https://ai.google.dev/gemini-api/docs/pricing)、確認日 2026-10-08）。
- **WaveSpeed**: 無料枠の額・適用は未確認。**断定せず、公式の確認結果だけを使う。**
- GUI / playground の無料枠と API の課金を同じ予算計算に混ぜない。

## 実行前の見積り

`単価 × 課金秒数` で出し、出典 URL と確認日を添える。**プロモ価格と通常価格、入力側の課金を必ず見る。**

### 単価の目安（確認日 2026-10-08）

- **fal H3 Max**（[H3 Max ページ Pricing 節](https://fal.ai/minimax-h3-max)）: 480p $0.05/秒、768p $0.08/秒、1080p $0.16/秒。Turbo は各半額。text-to-video / image-to-video は同単価。
  - **75% のローンチ割引は 2026-09-14 に終了** — これより前の記事・表を信用しない。
  - [fal pricing ページ](https://fal.ai/pricing) は最小単価（例: $0.05/秒）で表示する。解像度別の実単価は model page で確認する。
  - 例: 768p で 5 秒 = $0.40。
- **fal Veo 3.1 Fast**（model page の課金表示）: 720p/1080p で $0.10/秒（音声オフ）・$0.15/秒（音声オン）。4k は $0.30 / $0.35。
- **Gemini API Veo 3.1**（[pricing](https://ai.google.dev/gemini-api/docs/pricing)）: Fast $0.10/秒 (720p)・$0.12 (1080p)・$0.30 (4k)、Standard $0.40/秒 (720p/1080p)、Lite $0.05/秒 (720p)。
- **WaveSpeed `wavespeed-ai/minimax-h3/image-to-video`**（[model page](https://wavespeed.ai/models/wavespeed-ai/minimax-h3/image-to-video)）: 480p $0.04/秒、540p $0.06/秒、768p $0.08/秒、1080p $0.16/秒。duration 3–15秒（フレームグリッドに揺られるため 5秒要求は ~5.2秒になる）。
  - このページ自身が「ドキュメント価格は参考・古い可能性がある。**Generate ボタンの見積もりが最新、最終課金はタスク実績**」と注記している。ページ内部には割引率付きの promo 表示も混ざっている — **プロモ価格と通常価格を同じ見積に混ぜない。**
- **WaveSpeed の動画編集系（例: `bytedance/seedance-2.0/video-edit`）は入力+出力の秒数を合算で課金**（例: 入力5秒+出力5秒 = 課金10秒。入力は2–15秒に丸められる。[model page](https://wavespeed.ai/models/bytedance/seedance-2.0/video-edit)、確認日 2026-10-08）。実写編集を WaveSpeed で回すときは**入力側の秒数も見積に入れる**。
- WaveSpeed の MCP / playground は **spending 前の見積もり**を出す機能を持つ（llms.txt 記載）。API から回す場合も、送信前に model page の見積もりか価格表で確認する。

### 見積りの作り方（例）

```bash
python3 - <<'PY'
# fal H3 Max 768p（出典: https://fal.ai/minimax-h3-max, 確認日 2026-10-08）
rate, seconds = 0.08, 5
print(f"estimate: ${rate * seconds:.2f} / clip")
PY
```

予算が厳しいとき: 有料の合計上限を先に決める（例: $1）。上限内なら「768p 5秒 ×1本 = $0.40」のように積み、超過しそうなら fal ブラウザの無料枠（5本/日）か 480p / Turbo に落とす。**この上限は案件ごとの例であって、この skill の固定値ではない。**

## 手順

### 1. 入力と設定を決める

- **9:16 で作る場合、開始画像の縦横比に依存する経路が多い**: fal H3 Max i2v・MiniMax 公式 i2v・WaveSpeed i2v は**出力キャンバスが開始画像の縦横比を踏襲**する。9:16 の開始画像（現物写真を縦にトリミングするか、Image 経路で生成）を先に用意する。
- fal `fal-ai/veo3.1/fast/image-to-video` は入力画像が **16:9 / 9:16 でないと切り落とされる**（720p 以上）。
- Gemini API の Veo は `aspectRatio: "16:9" | "9:16"` をパラメータで指定する。
- text-to-video で縦横比を指定できる経路（fal H3 Max t2v: `21:9 / 16:9 / 4:3 / 1:1 / 3:4 / 9:16`）では、指定を明示する。
- **尺は最初は最短クラス（4〜5秒）で1本**。うまくいかないなら prompt を直してから次の1本。

### 2. prompt を書く（コピー例）

実写真を基準フレームにした短いカット:

```
Slow, subtle push-in on the storefront in this photo. A pedestrian passes,
the awning moves slightly, reflections shift on the window glass.
Keep the signage, colors, proportions, and people exactly as in the photo.
No text changes, no new objects. Natural daylight. Ambient street sound only.
```

- 指示は「動き」に絞り、**文字・金額・看板の文言は書かない**（生成が壊す。載せるなら HyperFrames 側）
- 場所の固有描写は現物どおりを明示する（例: 「exactly as in the photo」「no changes to the building」）
- 音声は生成経路が持っている場合が多い（H3 系・Veo はネイティブ音声）。不要ならその旨を書く

### 3. 送信 → 待機 → 取得

**fal（主経路）** — JS client（[公式 API ドキュメント](https://fal.ai/models/minimax/h3-max/image-to-video/api) の例に基づく）:

```js
import { fal } from "@fal-ai/client";
// FAL_KEY は環境変数から自動で読まれる
const { request_id } = await fal.queue.submit("minimax/h3-max/image-to-video", {
  input: {
    prompt: "…上の prompt…",
    image_url: "https://…/first-frame.jpg", // 開始画像（縦横比が出力に踏襲される）
    duration: 5,                            // 既定 5（秒）
    resolution: "768P",                     // 既定 768P。480P / 768P / 1080P
    prompt_expansion_mode: "balanced",      // disabled / balanced(既定) / quality
  },
  logs: true,
});
const status = await fal.queue.status("minimax/h3-max/image-to-video", {
  requestId: request_id, logs: true,
});
const result = await fal.queue.result("minimax/h3-max/image-to-video", {
  requestId: request_id,
});
console.log(result.data.video.url);   // ここで取得
```

- `duration` の出力は要求より最大 ~0.7秒長いことがある。課金は実出力基準で見積もる
- `image_url` を省略すると text-to-video として扱われ 16:9 になる
- 最終フレームを固定したい場合は `end_image_url`、参照素材で人物・スタイルを揃えたい場合は `minimax/h3-max/reference-to-video`（`reference_image_urls` / `reference_video_urls` / `reference_audio_urls`、合計12ファイル・合計15秒まで）

**WaveSpeed（代替）** — 公式 llms.txt の例（`jq` 必要）:

```bash
SUBMIT=$(curl --silent --show-error --fail-with-body \
  --request POST \
  --url https://api.wavespeed.ai/api/v3/wavespeed-ai/minimax-h3/image-to-video \
  --header "Authorization: Bearer ${WAVESPEED_API_KEY}" \
  --header "Content-Type: application/json" \
  --data '{"prompt":"…","image":"https://…/first-frame.jpg","resolution":"480p","duration":5}')
ID=$(printf '%s' "$SUBMIT" | jq -r '.data.id')

RESULT_URL="https://api.wavespeed.ai/api/v3/predictions/${ID}/result"
while true; do
  RESP=$(curl --silent --show-error --fail-with-body --request GET \
    --url "$RESULT_URL" --header "Authorization: Bearer ${WAVESPEED_API_KEY}")
  DATA=$(printf '%s' "$RESP" | jq -e '.data')
  case "$(printf '%s' "$DATA" | jq -er '.status')" in
    completed) printf '%s\n' "$DATA" | jq '.outputs'; break ;;
    failed|cancelled|timeout|deleted) printf '%s\n' "$DATA" | jq . >&2; exit 1 ;;
    *) sleep 2 ;;   # 長いタスクほど間隔を広げる
  esac
done
```

**Google Veo API（代替）** — REST（[公式ドキュメント](https://ai.google.dev/gemini-api/docs/veo) の例に基づく。text-to-video の形。image-to-video は同ドキュメントの `image` フィールド / Python SDK の `image=` を使う）:

```bash
operation_name=$(curl -s \
  "https://generativelanguage.googleapis.com/v1beta/models/veo-3.1-fast-generate-preview:predictLongRunning" \
  -H "x-goog-api-key: ${GEMINI_API_KEY}" -H "Content-Type: application/json" -X POST \
  -d '{"instances":[{"prompt":"…"}],
       "parameters":{"aspectRatio":"9:16","durationSeconds":"4"}}' | jq -r .name)

while true; do
  r=$(curl -s -H "x-goog-api-key: ${GEMINI_API_KEY}" \
    "https://generativelanguage.googleapis.com/v1beta/${operation_name}")
  [ "$(jq -r .done <<<"$r")" = "true" ] && break
  sleep 10
done
video_uri=$(jq -r .response.generateVideoResponse.generatedSamples[0].video.uri <<<"$r")
curl -L -o out.mp4 -H "x-goog-api-key: ${GEMINI_API_KEY}" "$video_uri"
```

- **生成動画はサーバ側で2日で削除される**（公式記載）。2日以内にダウンロードする
- Veo は SynthID で透かしが入る

### 4. 確認（実物と照合）

- [ ] 出力のアスペクトが意図どおりか（9:16 経路で開始画像の縦横比が効いているか）
- [ ] 実物写真と並べて、建物・物・人物・配色が一致するか。崩れていたら次は prompt で絞る、ダメなら**実写・原写真の編集へ戻る**
- [ ] 文字・金額・看板が生成で壊れていないか（壊れているならそのカットは不採用。文字は HyperFrames で載せる）
- [ ] 実在場所が勝手に変わっていないか（架空改変があるなら不採用）
- [ ] 課金が見積りと大きくずれていないか（実績を確認）

## 尺・縦横比の制約（確認日 2026-10-08）

| 経路 | 尺 | 縦横比 | 備考 |
| --- | --- | --- | --- |
| fal `minimax/h3-max/image-to-video` | 5–15秒（既定5、+~0.7秒まで） | 出力は開始画像に追従 | 480P/768P/1080P（既定 768P） |
| fal `minimax/h3-max/text-to-video` | 5–15秒 | `21:9/16:9/4:3/1:1/3:4/9:16` | 画像なしなら 16:9 |
| fal `minimax/h3-max/reference-to-video` | 5–15秒 | `adaptive` 他 | 参照は合計12ファイル・15秒まで |
| WaveSpeed `minimax-h3/*`（自社ホスト） | 3–15秒（フレームグリッドで ~5.2秒等に丸め） | 出力は開始画像に追従 | 480p/540p/768p/1080p（既定 480p） |
| fal `fal-ai/veo3.1/fast/image-to-video` | `4s/6s/8s`（既定 8s） | `auto/16:9/9:16` のみ | 入力画像は 16:9/9:16・720p+、それ以外は切り落とし |
| Gemini `veo-3.1-*` | 4/6/8秒。**1080p・4k・参照画像・拡張を使うと 8秒のみ** | `16:9`(既定) / `9:16` | 720p 既定、24fps、音声常時生成 |
| MiniMax 公式 `MiniMax-H3` | 4–15秒 | i2v は常に adaptive（**入力画像が決める、ratio 指定は無視**） | 768P / 2K |
| MiniMax 公式 `MiniMax-H3-Max` | 5–15秒（4秒は不可） | 同上 | 480P / 768P（2K 不可） |

**尺制約は経路で違う** — Veo 系の 4/6/8秒と H3 系の 5–15秒（WaveSpeed は 3–15秒）を同じ前提で設計しない。

## 戻り先

- 現物が保てない・実在場所の改変が出る → **実写・原写真の編集**に戻る（生成を使わない）
- 文字・金額・図表・字幕 → **HyperFrames（Video B）** で載せる
- 再現できる編集・合成、長い構成 → **HyperFrames（Video B）**
- 有料が合わない → fal ブラウザの無料枠（5本/日）に切り替える、または下位解像度 / Turbo / 別経路の見積を出す
