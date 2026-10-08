# Image generation (OpenRouter)

画像生成・1枚の編集・複数画像合成の詳細。入口は [SKILL.md](../SKILL.md)。

## Overview

Generate or edit images through OpenRouter. Support prompt-only generation, single-image edits, and multi-image composition.

Required key: `OPENROUTER_API_KEY`（global mise に age 暗号化で登録済み）。

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

## Model selection

Default to the cheapest model. Only step up when the user asks for quality or the default result is not good enough.

| `--model`                            | Price (prompt / completion per 1M) | Resolutions | When            |
| ------------------------------------ | ---------------------------------- | ----------- | --------------- |
| `google/gemini-3.1-flash-lite-image` | $0.25 / $1.5                       | 1K          | Default         |
| `google/gemini-3.1-flash-image`      | $0.50 / $3.0                       | 1K, 2K      | Quality matters |

Other OpenRouter image models can be passed to `--model` as-is. `google/gemini-3-pro-image` is the only one that reaches 4K, at $2.0 / $12.0.

価格は変動する。実行前に [OpenRouter の model ページ](https://openrouter.ai/models) で単価を確認し、見積りに確認日を添える。

## Resolution

- Use `--resolution` with `1K`, `2K`, or `4K`. Default is `1K`.
- Support is per-model — see the table above. The script rejects unsupported combinations before calling the API.

## System prompt customization

The skill reads an optional system prompt from `assets/SYSTEM_TEMPLATE`. This allows you to customize the image generation behavior without modifying code.

## Behavior and constraints

- Accept up to 3 input images via repeated `--input-image`.
- `--filename` accepts relative paths or absolute paths. Default output directory is `~/Desktop` (e.g. `--filename ~/Desktop/output.png`).
- The saved extension follows the returned MIME type, so a `.png` request may be written as `.jpg`. Use the path printed in `MEDIA:`, not the one passed in.
- If multiple images are returned, append `-1`, `-2`, etc. to the filename.
- Print `MEDIA: <path>` for each saved image. Do not read images back into the response.

## Troubleshooting

If the script exits non-zero, check stderr against these common blockers:

| Symptom                                   | Resolution                                                                                                 |
| ----------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `OPENROUTER_API_KEY is not set`           | The key lives in mise (age-encrypted). Run from a shell where mise env is loaded.                          |
| `does not support <resolution>`           | Pick a model from the table above that covers the requested resolution.                                    |
| `uv: command not found` or not recognized | Use `mise install aqua:astral-sh/uv` for the configured version, then run through `mise exec -- uv`. Manage version changes in the canonical dotfiles mise config. |
| `AuthenticationError` / HTTP 401          | Key is invalid or has no credits. Verify at <https://openrouter.ai/settings/keys>.                         |

For transient errors (HTTP 429, network timeouts), retry once after 30 seconds. Do not retry the same error more than twice — surface the issue to the user instead.
