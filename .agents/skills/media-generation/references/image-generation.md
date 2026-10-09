# Image generation

画像生成・1枚の編集・複数画像の合成の詳細。入口は [SKILL.md](../SKILL.md)。

**優先順位付きの3経路**（いずれも新規生成・1枚の編集・複数画像の合成に対応）:

| 経路 | 使う場面 | key |
| --- | --- | --- |
| **A: ブラウザ ChatGPT** | 第一選択。ログイン済みアカウントの無料枠で生成する | 不要（認証は本人の既存ログイン） |
| **B: 実行中 session の組み込み画像生成ツール** | A が使えないとき（未ログイン・上限等）で、ツールが実際に提供されているとき | 不要 |
| **C: OpenRouter `generate_image.py`** | A・B が使えないとき | `OPENROUTER_API_KEY`（global mise に age 暗号化で登録済み） |

## 経路 A — ブラウザ ChatGPT（第一選択・無料枠）

Orca 内蔵ブラウザの ChatGPT で画像を生成する。**ログイン済みアカウントの利用可能な無料枠・既存契約内の枠を使い、追加購入しない**。無制限無料・全アカウントで利用可能とは断言しない。操作は `orca` CLI（[orca-cli skill](../../orca-cli/SKILL.md)）経由で行い、別ブラウザ・隠し API・認証情報は使わない。

### 手順（検証済み 2026-10-09）

1. orca-cli skill の手順で既存の ChatGPT タブへ入る（なければ新規 chat を開く）
2. `orca snapshot` で要素を取り、prompt を入力し、再度 snapshot して**送信ボタンを `click` する**。Enter キーは投稿を保証しない — **Enter だけを完了扱いしない**
3. 生成完了を確認する: 画像件数の増加と「画像作成中」表示の消失を snapshot で再確認し、表示画像の `naturalWidth > 0` を `orca eval` で確かめる
4. 画像を保存する。UI の download が利用可能ならそれを使う。なければ表示済み画像（alt は生成画像、src は blob URL、`naturalWidth`/`naturalHeight` が原寸）の `currentSrc`/`src` を `orca eval` で `fetch` → `blob` → `FileReader.readAsDataURL` にし、返値を local subprocess で capture して decode 保存する（**base64 を会話ログへ全出力しない**）
5. 保存したファイルを view で目視確認する
6. metadata（prompt・provider=ChatGPT・日付・生成イメージである旨）を保存する

### fallback・扱いの注意

- 未ログイン・passkey/MFA・利用上限で使えないときは本人に引き継ぐか、次の経路（B → C）へ fallback する。credentials/tokens を agent が扱わない
- モデル名・内部 API など未確認の事項を断言しない
- real-place の依頼では生成イメージと現地写真を混同しない。参照画像を使う場合は利用可能なものに限定する

## 経路 B — 実行中 session の組み込み画像生成ツール

Codex に**組み込まれた画像生成ツール**を呼ぶ。**提供されている場合のみ**使う（下の「判定」）。提供されていれば **`OPENAI_API_KEY` の新規設定は不要**。提供形態の例: この作業を行った Codex セッションでは `image_gen.imagegen` というツールとして提供されていた（**ツール ID はセッション・バージョンに依存するため固定しない**）。

### 判定

- **Codex という名前だけでツールの提供を断定しない**。実際のセッションの tool availability を確認してから使う
- 未提供なら「このセッションには組み込みの画像生成ツールが提供されていない」ことを説明し、経路 C（OpenRouter・`OPENROUTER_API_KEY` が必要）に代替できることを示す

### 対応する作業

新規生成、実写真参照の編集、複数画像の合成、透過背景。

### 手順

1. prompt をそのセッションのツールに入れる
2. **編集対象がローカルの場合は、先に `view_image` で会話に読み込んでから**、当該セッションの **tool schema に従って**参照画像を指定する（パスをそのまま渡せるとは限らない）
3. 生成後は**出力の実ファイルを確認**し、ユーザーの指定保存先があればそこへコピーする
4. 透過背景が必要ならその旨を依頼し、得られた alpha を保ったまま扱う

### 断定しないこと

ツールが公開していない機能は書かない・約束しない:

- **モデル名指定は保証しない**。OpenAI 公式の [Image generation](https://learn.chatgpt.com/docs/image-generation) は Codex の built-in image generation を `gpt-image-2` と記載する（確認日 2026-10-08）が、観測したツールの schema は `model` 引数も backend API endpoint も公開していない。モデル名が必要なら**実行環境の現行ドキュメントで確認**し、この skill 内ではモデルを保証・固定しない
- **「無料 / 無制限」とは断定しない**。公式 docs は built-in が Codex の general usage limits に計上されると記載している（確認日 2026-10-08）
- **保存先を生成時の引数で指定できるとも断定しない**（既定の保存場所は実行環境に依存する。指定保存先には生成後の確認・コピーで対応する）
- 画像生成の主題は**実行経路の選択**であって、モデルの優劣比較ではない

### UI 自動操作との違い

ブラウザ UI 経由の生成は経路 A（ブラウザ ChatGPT）の手順を使う。この経路 B はあくまで**実行中 session に組み込まれた画像生成ツールの呼び出し**であり、UI 自動操作と混同しない。

## 経路 C — OpenRouter（既存）

経路 A（ブラウザ ChatGPT）・経路 B（組み込みツール）がいずれも使えないときの既存経路。

### Prompt-only generation

```
uv run {baseDir}/scripts/generate_image.py \
  --prompt "A cinematic sunset over snow-capped mountains" \
  --filename sunset.png
```

### Edit a single image

```
uv run {baseDir}/scripts/generate_image.py \
  --prompt "Replace the sky with a dramatic aurora" \
  --input-image input.jpg \
  --filename aurora.png
```

### Compose multiple images

```
uv run {baseDir}/scripts/generate_image.py \
  --prompt "Combine the subjects into a single studio portrait" \
  --input-image face1.jpg \
  --input-image face2.jpg \
  --filename composite.png
```

### Model selection

Default to the cheapest model. Only step up when the user asks for quality or the default result is not good enough.

| `--model`                            | Price (prompt / completion per 1M) | Resolutions | When            |
| ------------------------------------ | ---------------------------------- | ----------- | --------------- |
| `google/gemini-3.1-flash-lite-image` | $0.25 / $1.5                       | 1K          | Default         |
| `google/gemini-3.1-flash-image`      | $0.50 / $3.0                       | 1K, 2K      | Quality matters |

Other OpenRouter image models can be passed to `--model` as-is. `google/gemini-3-pro-image` is the only one that reaches 4K, at $2.0 / $12.0.

価格は変動する。実行前に [OpenRouter の model ページ](https://openrouter.ai/models) で単価を確認する（確認日を添える）。この経路は価格優先 — 既定は最安モデル。

### Resolution

- Use `--resolution` with `1K`, `2K`, or `4K`. Default is `1K`.
- Support is per-model — see the table above. The script rejects unsupported combinations before calling the API.

### System prompt customization

The skill reads an optional system prompt from `assets/SYSTEM_TEMPLATE`. This allows you to customize the image generation behavior without modifying code.

### Behavior and constraints

- Accept up to 3 input images via repeated `--input-image`.
- `--filename` accepts relative paths or absolute paths. Default output directory is `~/Desktop` (e.g. `--filename ~/Desktop/output.png`).
- The saved extension follows the returned MIME type, so a `.png` request may be written as `.jpg`. Use the path printed in `MEDIA:`, not the one passed in.
- If multiple images are returned, append `-1`, `-2`, etc. to the filename.
- Print `MEDIA: <path>` for each saved image. Do not read images back into the response.

### Troubleshooting

If the script exits non-zero, check stderr against these common blockers:

| Symptom                                   | Resolution                                                                                                 |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `OPENROUTER_API_KEY is not set`           | The key lives in mise (age-encrypted). Run from a shell where mise env is loaded.                          |
| `does not support <resolution>`           | Pick a model from the table above that covers the requested resolution.                                    |
| `uv: command not found` or not recognized | Use `mise install aqua:astral-sh/uv` for the configured version, then run through `mise exec -- uv`. Manage version changes in the canonical dotfiles mise config. |
| `AuthenticationError` / HTTP 401          | Key is invalid or has no credits. Verify at <https://openrouter.ai/settings/keys>.                         |

For transient errors (HTTP 429, network timeouts), retry once after 30 seconds. Do not retry the same error more than twice — surface the issue to the user instead.
