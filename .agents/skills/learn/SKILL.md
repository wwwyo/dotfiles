---
name: learn
license: MIT
argument-hint: "[config [key value] | clean | update]"
description: >-
  概念・コード・仕組みを、拡張Markdownから生成するパネル型のHTMLで説明し、ユーザーの理解を確認する。
  動画は明示的に依頼されたときだけ生成する。「教えて」「仕組みを理解したい」「図で説明して」
  「解説動画を作って」「理解できたか確認して」や /learn で使う。実装・修正だけを求める依頼には使わない。
---
# Learn：図解動画・HTMLで説明し、理解を確認する

You write only the **content draft** (extended Markdown). The `am` CLI does all layout, colours, dark mode and diagram coordinates. **Do not hand-write HTML / CSS / SVG.**

Reply to the user, and write the draft, in the user's language.

[QingYunA/answer-me-with-html](https://github.com/QingYunA/answer-me-with-html/tree/4afe054b1a7f99b43c316c1951b113ae7c775f4e) を元にしたローカル適応。図の配置と描画は同梱 CLI に任せる。

## 出力形式と提示順

対象読者が既知の隣接概念がある場合は、その概念との比較・対応を冒頭に置き、既知との差分から説明する。

出力形式の指定があれば従う。教材を作る場合、指定がなければ第2節の `am render` でHTML図解シートを生成する。
短い定義や単純な手順など、文章の一読で十分伝わる場合は文章を使う。
動画・movie・解説動画などを明示的に依頼された場合だけ、第6節の `am video` を使う。通常の「教えて」「図で説明して」や `/learn` は動画生成の依頼として扱わない。
動画を作る場合は学習の入口に置く。図解シートも作る場合は、動画プレイヤーのリンクを先に提示し、文章・図・操作教材を続ける。
動画では状態遷移、処理の移動、分岐を図の段階表示や動きで説明する。色やフェードだけで動きを付けた動画で済ませない。
教材制作のCLIはLLMを呼ばない。制作に使うagentのモデルと、音声生成モデルを区別する。別agentに委譲するときのモデル選択は環境の `delegate` skill に従う。

## 共有成果物の制作

[reporting](../reporting/SKILL.md) などが成果物を作るときも、このskillの語彙・文章規範（第5節）、図解部品（第3・4節）、HTML描画（第2節）、成果物の検証（第7節）を使う。HTML・CSS・SVGや部品一覧を呼び出し側に複製しない。材料・読者・本文の構成は呼び出し側で決める。

共有用レポートは `am render` を使う。共有依頼だけでは動画や第8節の本人の理解確認を開始しない。学習も依頼された場合は理解確認を行い、動画も依頼された場合は第6節を使う。

CLIのパスはこの `learn/SKILL.md` と同じdirの `scripts/am.mjs` を解決する。呼び出し元skillの `CLAUDE_SKILL_DIR` を流用しない。

画像を含む単体HTMLでは、描画前のMarkdown画像リンクをdata URIにする。`am render` はローカル画像を自動で埋め込まない。たとえば次のコマンドの出力を原稿の画像位置に入れる（PNGの場合）:

```bash
mise exec -- python3 - shots/after.png <<'PY'
import base64
import pathlib
import sys
data = base64.b64encode(pathlib.Path(sys.argv[1]).read_bytes()).decode("ascii")
print(f"![反映後](data:image/png;base64,{data})")
PY
```

WebPなら `image/webp`、JPEGなら `image/jpeg` を使う。キャプションは画像の上にMarkdownで書く。画像の拡縮はCLIに任せ、生成後のHTMLを加工しない。保存した原稿とHTML内の `#am-source` に埋め込み済み画像が残るため、`am patch` でも単体ファイルを保てる。

## 0. When the user wants to change settings

Arguments for this call: `$ARGUMENTS`

When the arguments start with `config` (for example `/learn config open off`), this turn handles settings only and produces no page:

- `config`: run `am config` to show the current settings, then ask the user which one to change.
- `config <key> <value>`: run `am config set <key> <value>`.
- `config reset [key]`: run `am config reset [key]`.

When the user asks in natural language ("stop opening the browser", "turn off always-on mode", "use the card theme by default"), also convert it to `am config set`. Settings: `open` (auto-open the browser), `always` (always-on mode), `theme`, `mode`, `style`, `voice` (video narration), `update_check` (new-version notices). Run `am config` to see all descriptions.

When the arguments start with `clean`, or the user asks to clean up pages / the cache: first run `am clean --dry-run` and tell the user how many items and how much space will be deleted. Run `am clean` only after the user agrees (add `--all` to delete all pages and videos, `--days N` to change how many days to keep).

skill の取得・更新は環境の `skillctrl` skill に従う。原本更新時もHTMLの既定・動画の明示依頼時のみの生成・理解確認を保つ。

## 1. 判断：要不要制作教材

形式の明示指定があれば優先する。形式未指定では、下記のいずれかならHTML図解シートを作る。動画は明示依頼時だけ選ぶ：

- There are ≥3 interrelated concepts, and the reader needs to see how they relate.
- There is a flow, protocol, call chain or state transition (especially with branches or several actors).
- There is a comparison across ≥3 dimensions, a trade-off between options, or a "can / cannot" list.
- There is a hierarchy or an evolution over time.

Otherwise answer in plain text. When unsure: the more the question "needs a picture to understand", the more it calls for a page.

### Always-on mode

既存の `[answer-me-with-html always-on]` ルールがある場合、その日常返答への適用は図解シートを使う。このルールも動画生成の依頼として扱わない：

- Whenever this turn gives a conclusion, summary, plan, comparison, review or explanation, attach a page.
- Do not skip it because "the answer is short". If there is a conclusion, produce a page.
- For everyday conclusions use a small page with 2–4 panels: one callout with the conclusion, plus one table or one diagram. Do not add panels just to fill space.
- Render with `--no-open`, so no browser window interrupts the user. The user opens the page by clicking the path at the end of the reply.
- In the terminal, give the text conclusion first as usual, and put the page path on the last line.
- Produce no page for small talk, one or two sentences with no conclusion, pure command output, or when the user asks for plain text.

## 2. HTML 図解シートの生成

The CLI is bundled in this skill's directory: `scripts/am.mjs`, a single file with no dependencies to install; it needs only Node.js 20+. Below, `am` always means:

```bash
mise exec -- node "${CLAUDE_SKILL_DIR}/scripts/am.mjs"
```

In Claude Code, the path above is replaced with this skill's directory automatically. If you see the variable unreplaced (other agents), replace it with the absolute path of the directory that contains this SKILL.md. If the user installed the `am` command globally, you can also use `am` directly.

1. First list 3–8 panels in your head. Each panel answers one sub-question only.
 The draft language follows the language of the user's question: an English question gets an English draft, a Chinese question a Chinese draft, a Japanese question a Japanese draft. The page button labels, `<html lang>` and the STE check rules switch automatically by the draft language (a draft containing kana counts as Japanese); STE applies the English or Chinese rules to each sentence by its language (Japanese sentences get only the sentence-length and paragraph-length checks, with the same character limits as Chinese). To force the interface language, write `lang: en`, `lang: zh` or `lang: ja` in the frontmatter.
2. Choose components by the shape of the information (see section 4).
3. Render in one go with a heredoc:

```bash
mise exec -- node "${CLAUDE_SKILL_DIR}/scripts/am.mjs" render - <<'AM_EOF'
---
title: Title
---
## A Panel title
```flow
A -> B: label
```
AM_EOF
```

4. Read the output:
   - `✓ <path>`: success. Whether the browser opens automatically depends on the user's settings (`am config`); `--no-open` affects only this run.
   - `✗ L<line> [component] …` + `Correct example:`: fix that line following the example, then render again.
   - `STE n warnings`: rewrite the flagged lines as suggested, then render again. Retry at most 2 rounds; if warnings remain, keep the page and say so.
   - `! Cleanup hint: …` or `! Update hint: …`: pass it on to the user in one sentence at the end of the reply, and ask whether to clean up / update. **Do not run am clean or the update command yourself**; wait until the user agrees. The CLI throttles these: the cleanup hint appears at most once every 7 days, the update hint at most once every 3 days.
5. Reply in the terminal with only 2–3 lines: one core conclusion + the page path. Do not paste the draft or the HTML back into the terminal.

When a page already exists and only one panel needs to change, do not rewrite the whole page. Take the source draft from the HTML's `#am-source`, replace only the matching `##` section, and overwrite the page in place:

```bash
mise exec -- node "${CLAUDE_SKILL_DIR}/scripts/am.mjs" patch page.html --panel "Panel title" <<'AM_EOF'
## A Panel title
New content
AM_EOF
```

`--panel` matches the title, the letter ID, or `ID title`. If the panel is not found or the page has no `#am-source`, leave the file unchanged. patch keeps the original page's theme, light/dark mode and STE style; add `--theme` / `--mode` / `--style` to change them. Full usage: `am help patch`.

## 3. Draft format quick reference

```markdown
---
template: sheet     # sheet board (default, one-screen overview) | doc linear explanation (read step by step)
theme: blueprint    # blueprint drawing style (default) | shadcn card style
title: Title
subtitle: One-line summary     # optional
cols: 3             # most columns in a sheet row, default 3
source: RFC 9293    # any other key is shown in the page header's meta line
---
Lead: one or two sentences with the core conclusion (optional).

## A Panel title {span=2 meta="small text, top right"}
Plain Markdown: paragraphs, lists, tables, quotes.
Table status words: ok / no / warn (may carry text: "ok approved") → ✓ / ✗ / ! badges.

## B {bare}            ← bare: no title bar (suits a kv title block)
```

- The panel letter ID can be omitted; it is assigned automatically.
- `html /` svg fenced blocks are embedded as-is. **Use them only when no component can express the content.**
- Full reference: `am help format`; component syntax: `am help <component>`; component list: `am list`.

## 4. Choose components by the shape of the information


| Shape of the information                               | Component                          | Minimal syntax                                                                                                                   |
| ------------------------------------------------------ | ---------------------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| What connects to what, architecture, decision branches | `flow [LR]`                        | `A -> B: label`, `A --> C` dashed, `A -> B & C` fan-out, `{decision?}` `(start)` `[(database)]`, `*emphasis`, `group name: A, B` |
| Messages between actors over time                      | `sequence [num]`                   | `A -> B: request`, `B --> A: response`, `note A, B: note`, `== phase ==`                                                         |
| Hierarchy / directories / taxonomy                     | `tree [list]`                      | indentation for levels, `label | description`, ``id` label`                                                                      |
| History / phases                                       | `timeline [v]`                     | `time | title | description`, `*` highlights                                                                                     |
| Values and limits                                      | `limits`                           | `label | 13 / 20 | unit`, limit only: `label | max 20`                                                                           |
| Word-by-word comments on one sentence                  | `annot`                            | `# heading | right note`, `[span]{note}`, `[wrong word]{!red note}`, `> footnote`                                                |
| Metadata / title block                                 | `kv [cols=2]`                      | `key: value`, `* wide cell: value`                                                                                               |
| Conclusion / warning                                   | `callout <info|ok|warn|err> title` | Markdown body                                                                                                                    |
| Multi-dimension comparison, can / cannot list          | Markdown table                     | write ok / no / warn in the status column                                                                                        |


Selection rules:

- Conclusion first. The first panel or the lead gives the core answer; the following panels give the evidence.
- One panel, one question. With more than 8 panels, split the page or cut panels.
- `span` is a hint. In a browser the sheet sizes each panel to its content and fills every row, so write no `span` for a wide table or diagram. Write `span` only for a panel that must stand out (`span` = `cols` gives it a row of its own). `rows` applies only to the plain grid (without JavaScript, in print and on narrow screens); the browser layout ignores it.
- Do not invent data. Without real numbers, do not use limits; mark illustrative data as "illustrative" in the description.

## 5. STE controlled writing (the text in the draft)

語彙は読者が知る具体的な言葉を選び、専門用語は初出で意味を添える。同じ概念には同じ名前を使う。日本語の原稿は [japanese-tech-writing](../japanese-tech-writing/SKILL.md) に従う。以下のSTE検査はその補助であり、日本語の論理・語彙・不確実性の点検を代替しない。

`am render` checks automatically and only warns by default (`style: 80`); with `style: strict` a draft that fails produces no page; `style: off` turns the check off.

- One sentence says one thing.
- Use the active voice. Write steps in the imperative ("Close the valve", not "The valve should be closed").
- One word, one meaning. Call the same thing by the same name throughout.
- Sentence length limits: steps (ordered lists) 20 words in English / 35 characters in Chinese; descriptions 25 words in English / 45 characters in Chinese.
- No more than 6 sentences per paragraph. Use lists for complex content.
- In English, use common short words: use, not utilize; start, not commence; before, not prior to.
- In Chinese, do not use light verbs (`进行优化` → `优化`, `加以说明` → `说明`), do not chain more than three `的`, and do not use clichés (`赋能`, `闭环`, `至关重要`…).
- For counter-examples shown on purpose, use `~~strikethrough~~` or put them in a table row whose status is `no`; the check skips them.

## 6. Explainer videos (am video, 3Blue1Brown style)

ユーザーが動画を明示的に依頼した場合だけ、この動画生成を使う。形式未指定の通常の解説は第2節のHTML図解シートを使う。
音声はFish Audioを `--voice fish` で明示する。モデルは `s2.1-pro-free`、話者は旧learnと同じ「さとる（ナレーション）」の `297a6fd278df47c3b9da9bfdf55ac89a` を使う。
認証はmise + ageで管理した `FISH_API_KEY` を `mise exec` から渡す。話者変更は `FISH_VOICE_ID`。秘密情報は原稿・設定ファイル・ログに平文で置かず、privateな情報を含む台本をFish Audioへ送らない。
`mise exec` 後も `FISH_API_KEY` が見えないとき、空のprocess.envだけで未登録と結論しない。global/repo-local のmise設定への登録有無とage復号鍵（`MISE_AGE_KEY`）の注入を分けて確認する。確認だけでなく音声生成の `mise exec` 側にも同じ注入を付ける。登録済みキーが復号できれば再登録を求めずそのまま音声生成し、復号を確認しても不足する場合だけユーザーに質問する。
モデル名はCLIが固定ヘッダーで指定する。キー不足やAPI失敗時は停止し、有料モデル・システムTTS・別providerへ自動で切り替えない。
無料モデルの期間・条件は利用時に [公式案内](https://fish.audio/blog/s2-1-pro-free-api/) で確認する。2026-10-05確認時点で無料期間は2026-11-30まで。
各ナレーションをWAVで生成し、実際の音声長で図の段階表示と字幕を同期する。
日本語では表示用の原稿とTTS用の読みを分ける。字幕には漢字・正式な識別子を残し、読みは文脈に合わせたかな表記にする。`FISH_TTS_READINGS_FILE` にJSONファイルのパスを渡すと、字幕を保ったまま読みだけをFish Audioへ送る。JSONは各ナレーションの表示テキストをキー、読み上げテキストを値にする（例：`{"冪等キーで重複を防ぐ。":"べきとうキーで、ちょうふくをふせぐ。"}`）。全ナレーション分を用意し、フォーカス指定の `[名前]` は角括弧を外してキーにする。読みを直したら音声を再生成し、試聴で発音・間を確認する。
HTMLだけ、文章だけ、無音の指定があれば、その指定を優先する。音声が生成できなければ理由を報告し、音声付きとして完成扱いしない。

A video draft has the same format as a page draft, with one extra rule: lines starting with `>` are narration, one beat per line.

```bash
mise exec -- node "${CLAUDE_SKILL_DIR}/scripts/am.mjs" video - --voice fish --no-open <<'AM_EOF'
---
title: The TCP three-way handshake
subtitle: Why three
---
> Opening narration (optional).

## Both ends are waiting
```sequence
Client -> Server: SYN
Server -> Client: SYN-ACK
Client -> Server: ACK
```
> First the client sends SYN to ask for a connection.
> [Server] answers with SYN-ACK.
> The client replies with ACK, and the connection is open.
AM_EOF
```

- One `##`  is one scene. Put one component (or one table, one list) in a scene as the picture, and write 2–5 narration lines below it.
- When the Nth narration line plays, the picture shows step N. In flow / sequence / tree every source line is one step; timeline, limits, table rows and list items step by entry. So the line order of the component is the order of the explanation. When there are more narration lines than steps, the extra first lines serve as an opening and show nothing new.
- Write `[name]` in narration: the camera zooms in on the node or actor with that name and highlights it. The name must match how it is written in the component.
- Nodes with the same name in adjacent scenes move smoothly to their new position. To keep the viewer following one object, reuse the same name in the next scene.
- 3–6 scenes per video, one or two sentences per narration line.
- Narration is read aloud, so write it as speech, as if explaining to someone face to face: transitions like `你看`, `那问题来了`, `我们换个角度看` are fine, and characters' "lines" go in quotes. Do not write it like a manual (`客户端发送 SYN 报文以请求建立连接`). Sentence length is still subject to the STE check.
- The look follows the theme in the settings by default (usually the blueprint drawing style). When the user wants "that dark 3b1b style", write `theme: 3b1b` in the frontmatter.
- 音声：既定は `--voice fish`（`auto` もFish Audioを選ぶ）。他のproviderはユーザーが明示した場合だけ使い、無音指定は `--voice off`。音声とモデルの指定は `am help video` で確認できる。
- The output is a single-file player page under `~/.answer-me-with-html/videos/` (audio embedded). When the user wants a video file, add `--mp4`; this needs Chrome, ffmpeg and Node.js 22+ on the machine. The CLI uses libx264 when available, otherwise h264\_videotoolbox on macOS (8 Mbps), without installing extra libraries. Export speed depends on the machine.
- Full syntax: `am help video`. In the terminal, reply with one sentence plus the player page path (and the MP4 path).

## 7. 成果物の検証

完成した教材を実際に確認する。HTMLは表示と利用する操作を、動画は映像・音声・同期を確認する。
音声を試聴し、専門用語・数字・間を点検する。ブラウザ確認は環境の `orca-cli` skill に従い、同梱CLIの自動ブラウザ起動は `--no-open` で抑える。
実行や試聴ができなかった部分は未検証と伝える。文体検査の警告ゼロを、説明の真偽やユーザーの理解の証明にしない。

初見の読み手への伝わり方を検証するときは [first-reader](../first-reader/SKILL.md) を使い、HTMLと分けたMarkdown原稿を渡す。結果は「AI模擬reader」と明記し、本人の理解確認とは区別する。

## 8. 本人の理解確認（学習依頼時）

教材を渡した後、核心を理解したか、ユーザーの回答や操作で確かめる。
言い換え、別の具体例への適用、結果の予測、図やHTMLの操作、クイズ、対話から有効な方法を選ぶ。
説明の丸写しで答えられる問いより、別の例に考え方を使うなど、理解が見える確認にする。確認方法や問題数は固定しない。
ユーザーの応答を待ち、理由や考え方を含めて判断する。誤解や抜けがあれば説明を変え、別の例で再確認する。
教材の閲覧や「わかった」だけで理解済みとは判断しない。確認できた範囲を伝え、回答がなければ未確認とする。
他のagentによる回答で、ユーザー本人の理解確認を代行しない。