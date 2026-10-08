# Image generation

画像生成・1枚の編集・複数画像の合成の詳細。入口は [SKILL.md](../SKILL.md)。

**実行環境による二択**（どちらも新規生成・1枚の編集・複数画像の合成に対応）:

| 経路 | 使う場面 | key |
| --- | --- | --- |
| **A: Codex の組み込み画像生成ツール** | Codex セッションでツールが実際に提供されているとき（第一選択） | 不要 |
| **B: OpenRouter `generate_image.py`** | Codex 以外、または A が未提供のとき | `OPENROUTER_API_KEY`（global mise に age 暗号化で登録済み） |

## 経路 A — Codex の組み込み画像生成ツール（第一選択）

Codex に**組み込まれた画像生成ツール**を呼ぶ。この親セッションには `image_gen.imagegen` が実際に提供されており、**`OPENAI_API_KEY` の新規設定は不要**。

### 判定

- **Codex という名前だけでツールの提供を断定しない**。実際のセッションの tool availability を確認してから使う
- 未提供なら「このセッションには組み込みの画像生成ツールが提供されていない」ことを説明し、経路 B（OpenRouter・`OPENROUTER_API_KEY` が必要）に代替できることを示す

### 対応する作業

新規生成、実写真参照の編集、複数画像の合成、透過背景。

### 手順

1. prompt をそのセッションのツールに入れる
2. **編集対象がローカルの場合は、先に `view_image` で会話に読み込んでから**、当該セッションの **tool schema に従って**参照画像を指定する（パスをそのまま渡せるとは限らない）
3. 生成後は**出力の実ファイルを確認**し、ユーザーの指定保存先があればそこへコピーする
4. 透過背景が必要ならその旨を依頼し、得られた alpha を保ったまま扱う

### 断定しないこと

ツールが公開していない機能は書かない・約束しない:

- **モデル名指定は保証しない**。OpenAI 公式の [Image generation](https://learn.chatgpt.com/docs/image-generation) は Codex の built-in image generation を `gpt-image-2` と記載する（確認日 2026-10-08）が、この親セッションの `image_gen.imagegen` の schema は `model` 引数も backend API endpoint も公開していない。モデル名が必要なら**実行環境の現行ドキュメントで確認**し、この skill 内ではモデルを保証・固定しない
- **「無料 / 無制限」とは断定しない**。公式 docs は built-in が Codex の general usage limits に計上されると記載している（確認日 2026-10-08）
- **保存先を生成時の引数で指定できるとも断定しない**（既定の保存場所は実行環境に依存する。指定保存先には生成後の確認・コピーで対応する）
- この技能の主題は**実行経路の選択**であって、モデルの優劣比較ではない

### UI 自動操作は別物

ChatGPT の**デスクトップ/ブラウザ UI を自動操作して画像を生成する手順は持たない**。ここでは Codex に組み込まれた画像生成ツールの呼び出しとして扱う。

## 経路 B — OpenRouter（既存）

Codex 以外の実行（pi / Devin / Claude Code 等）、または経路 A が未提供のときの既存経路。

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
