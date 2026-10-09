---
name: media-generation
description: "Generate or edit images and videos, and generate speech or narration. Routes image generation, single-image edits, and multi-image compositing to the running session's built-in image tool when a Codex session provides one, otherwise to OpenRouter's generate_image.py; speech and narration through Fish Audio; generative video (text-to-video, image-to-video from a real photo, reference-based generation, real-footage editing) through fal as the primary route with WaveSpeed and the Google Veo API as named alternatives; and demos, product launches, motion graphics, captions, numbers, and reproducible edits/compositions through HyperFrames. Use for 「画像を生成」「画像を編集」「音声を作って」「ナレーションを作って」「動画を作って」「プロモ動画」「demo動画」「モーショングラフィックス」などの依頼で."
metadata:
  emoji: 🎬
---

# Media Generation

画像・音声・動画の生成を扱うルーター。実行手順の詳細は下の reference に出すので、まず経路を選ぶ。

| やりたいこと | 経路 |
| --- | --- |
| 画像の生成・1枚の編集・複数画像の合成 | **Image** — 実行環境で二択（Codex の組み込みツール / OpenRouter）（[references/image-generation.md](references/image-generation.md)） |
| 読み上げ音声・ナレーションの生成 | **Audio** — Fish Audio（[references/audio-generation.md](references/audio-generation.md)） |
| テキスト→動画、実写真を基準にした短いカット、必要時の実写編集 | **Video A** — 生成AI（[references/video-generation.md](references/video-generation.md)） |
| demo / product launch / motion graphic、図・字幕・数値、再現できる編集・合成 | **Video B** — HyperFrames（下節） |
| 生成したカットを1本に組み立てる | **併用** — A で撮影単位を作り、B で組み立てる |

必要な key は経路ごとに異なる（値は表示しない。登録済みの key は global mise に age 暗号化で入っている）:

- Image = **経路 A（Codex の組み込み画像生成ツール）は key 不要**、**経路 B（OpenRouter）のみ `OPENROUTER_API_KEY`**（登録済み）。`OPENROUTER_API_KEY` は全ルートの必須条件ではない
- Audio = [音声生成手順](references/audio-generation.md) の認証設定を使う
- Video A / fal = `FAL_KEY`（登録済み）、Video A / Google Veo API = `GEMINI_API_KEY`（登録済み）
- Video A / WaveSpeed = `WAVESPEED_API_KEY`（**未登録**。WaveSpeed を選んだときに [secret-env](../secret-env/SKILL.md) の手順で `mise set --age-encrypt` して登録する）
- Video B = key 不要

## Image

**実行環境による二択**（どちらも新規生成・1枚の編集・複数画像の合成に対応）。手順の詳細は [references/image-generation.md](references/image-generation.md)。

1. **Codex + 組み込み画像生成ツールあり → 第一選択**
   - **そのセッションに組み込みの画像生成ツールが実際に提供されている場合のみ**使う。ここで新規生成・実写真参照の編集・複数画像の合成・透過背景を行い、**`OPENAI_API_KEY` の新規設定は不要**
   - 提供形態の例: この作業を行った Codex セッションでは `image_gen.imagegen` というツールとして提供されていた（**ツール ID はセッション・バージョンで変わりうるため固定しない**）
   - **Codex という名前だけでツールの提供を断定しない** — 実際の tool availability を確認する。未提供ならその旨を説明し、経路 B（OpenRouter）に代替できることを示す
   - **ツールが公開していない機能は断定しない**: モデル名を指定できる・無料/無制限・保存先を生成時の引数で指定できる、など。公式 docs は built-in を `gpt-image-2` と記載するが、このツールの schema は `model` 引数も backend API endpoint も公開していない。モデル名が必要なら実行環境の現行ドキュメントで確認する
   - 編集対象がローカルなら、先に `view_image` で会話に読み込んでから、**当該セッションの tool schema に従って**参照画像を指定する
   - 指定保存先があれば、生成後に**出力の実ファイルを確認してコピー**する
   - **ChatGPT UI（デスクトップ/ブラウザ）の自動操作は手順にしない** — Codex に組み込まれた画像生成ツールの呼び出しとして扱う
2. **Codex 以外、または組み込みツールが未提供 → OpenRouter（既存）**
   - 既存の `generate_image.py`。`OPENROUTER_API_KEY` が必要（mise + age 管理、価格優先の既定モデル）

   ```
   uv run {baseDir}/scripts/generate_image.py \
     --prompt "A cinematic sunset over snow-capped mountains" \
     --filename sunset.png
   ```

## Audio — 読み上げ・ナレーション

音声生成のモデル・話者・認証・感情や話し方のタグ・日本語の読み分け・失敗時の扱いは [references/audio-generation.md](references/audio-generation.md) を正本とする。音声を作る前に読む。`learn` などの呼び出し側にはこの手順を複製せず、参照を置く。

## Video A — 生成AI

**使いどころ**: 実写に見せる短いクリップ、実写真からの image-to-video、テキスト→動画、必要時の実写編集。

名前付きの利用経路は次の3つ。**同一モデル名でもホストが違えば別モデル・別単価として扱う**:

1. **fal（主経路）** — `FAL_KEY`。MiniMax H3 / H3 Max（`minimax/h3-max/*`）、Veo 3.1（`fal-ai/veo3.1/*`）等。既定はこちら
2. **WaveSpeed（代替）** — `WAVESPEED_API_KEY`（利用時に登録）。`wavespeed-ai/minimax-h3/*` は **open-weights 版 MiniMax H3 の WaveSpeed 自社ホスト**で、fal の H3 Max（fal が post-train した variant）とは**同一モデル・同一料金として扱わない**。**利用は console（Web）のみ確認済み — API 利用は未確認（reference の備考参照）**
3. **Google Veo API（代替）** — `GEMINI_API_KEY`。Gemini API の `veo-3.1-*`。Google の課金・尺制約に置きたいとき

進め方の原則:

- 実写真を基準フレームにして、**小さな動きを短いカット**で作る。1本を長く任せない
- 生成後は必ず**実物と照合**する（場所・物・人物・配色が写真と一致するか）
- **文字・金額・固有の表示は生成映像に任せない**。必要なら HyperFrames（Video B）で重ねる
- **実在場所の架空改変を避ける**。現物が保てなければ**実写・原写真の編集へ戻す**
- 実行前に**料金・無料枠を公式で確認**する（プロモ価格と通常価格、動画編集系の入力課金に注意）。GUI/ブラウザの無料枠と API 課金を混同しない
- 無料枠は「確認できたもの」だけ使う。額や適用が未確認なら断定せず、公式で確認する
- 新しいモデル = 目的への最適ではない。無料/低コスト優先で、ユーザーの予算を厳守する（予算が厳しいときの例: 有料生成の合計上限を先に決めてから無料枠と短いカットで試す。この上限は案件ごとの例であって、この skill の固定手順ではない）

手順・コピペ可能な prompt/command 例・尺/縦横比の制約は [references/video-generation.md](references/video-generation.md) を読む。**この repo に動画生成 CLI は無い** — reference のコピペ可能な例（curl / JS client）をそのまま使う。

## Video B — HyperFrames

demo・product launch・motion graphic、図・字幕・数値、再現できる編集・合成はこちら。

1. cwd を `~/src/github.com/wwwyo/hyperframes` にして `/hyperframes` skill から入る
2. `/hyperframes` のルーティング表に従って適切な workflow を選ぶ
3. 既存プロジェクトの inspect / preview / render も同じ入口

HyperFrames の実装・workflow の中身をこの skill に複製しない。必要な手順は都度 `/hyperframes` 側で読む。

## 併用

生成AIのカット（Video A）を素材として、HyperFrames（Video B）で組み立てる:

- A で撮影単位の短いクリップを複数作り、B の workflow に読み込んで図・字幕・数値・編集・音を載せる
- 文字や金額が絡む演出は必ず B 側で行う（A に描かせない）
- 素材の sourcing / 生成の扱いは HyperFrames の `/media-use` 側の責務なので、B の案内に従う

## 共通ルール

- 料金・機能・API schema は**公式資料で確認**してから動く（この skill の調査確認日: 2026-10-08。価格・提供形態は変動するため実行前に再確認する）
- 画像生成の主題は**実行経路の選択**であって、モデルの優劣比較ではない（[references/image-generation.md](references/image-generation.md) の「断定しないこと」）。モデル名・料金・提供機能は経路ごとに現行ドキュメントで確認する
- 実課金・素材アップロード・実生成は、ユーザーが明示的に許可するまで行わない。検証は `--help`・dry-run・公開 schema の読解で行う
