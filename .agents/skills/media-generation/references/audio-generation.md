# Audio generation — 読み上げ・ナレーション

入口は [SKILL.md](../SKILL.md) の Audio 節。音声生成の運用仕様はこのファイルを正本とし、`learn` などの呼び出し側は参照する。

## モデルと話者

音声はFish Audioを使う。モデルは `s2.1-pro-free`、既定の話者は女性の声の「しおり（ナレーション）」の `5da7f24e9e274f91b2b677669c818ce9` を使う。ユーザーが別の話者を指定した場合は `FISH_VOICE_ID` で変更する。

女性の声を既定にするのはユーザーの希望。2026-10-09に [Fish Officialの話者ページ](https://fish.audio/m/5da7f24e9e274f91b2b677669c818ce9/) で、日本語の女性ナレーション話者であることを確認した。変更後の音声は未試聴なので、生成時に下記の手順で確認する。

モデル名をリクエストの `model` ヘッダーで明示する。キー不足やAPI失敗時は停止し、有料モデル・システムTTS・別providerへ自動で切り替えない。他のproviderはユーザーが明示した場合だけ使う。

無料モデルの期間・条件は利用時に [公式案内](https://fish.audio/blog/s2-1-pro-free-api/) で確認する。2026-10-09確認時点で無料期間は2026-11-30まで。

## 感情・話し方のタグで自然な音声を作る

音声原稿を作るときは、台詞の意図と場面に合う感情・話し方・間をタグで指示する。説明なら好奇心や穏やかな強調、発見なら喜び、会話ならためらいや反応など、聞き手に伝わる演技を付ける。タグは変化が必要な箇所に絞り、全ての文を強く演じさせない。

**タグは英語を基本にし、本文はユーザーの言語を保つ。** 喜びなら `[喜び]` をそのまま送る代わりに `[happy]`、高揚感なら `[excited]` を選ぶ。英語タグを既定にするのはこの環境の運用方針。Fishは日本語の指示も扱えるが、英語が常により安定するという比較結果を公式仕様として断定しない。

### provider・モデルごとの仕様

2026-10-09に次の公式資料を確認した。実行時も選んだモデルの対応を確認し、古いモデルへ同じ構文を流用しない。

- **Fish Audio S2-Pro / S2.1-Pro系**: `text` 内の角括弧 `[tag]` が感情・発声の指示になる。自由な自然言語の説明も使える。既定の `s2.1-pro-free` はS2.1-Proと同じモデル。旧S1は丸括弧 `(happy)` の別構文なので混ぜない。（[Emotion Control](https://docs.fish.audio/developer-guide/core-features/emotions)、[Models Overview](https://docs.fish.audio/overview/capabilities)）
- **ElevenLabs**: `eleven_v3`、`eleven_v4`、`eleven_v4_turbo` がAudio Tagsに対応する。APIでもタグを `text` に含めて送り、`model_id` に対応モデルを明示する。他モデルの対応を推測しない。ElevenLabsを選んだ場合の認証はmise + age管理の `ELEVENLABS_API_KEY`。（[Audio Tags対応モデル](https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/how-do-audio-tags-work-with-eleven-v3-and-v4)）

### タグの選び方と配置

次は公式資料の代表例と、その指示を短くした例。全タグを付けるチェックリストではなく、文脈に合うものを選ぶための候補とする。ElevenLabsの `[warm, conversational tone]` は公式作例の短縮形。

| 狙い | Fish S2系 | ElevenLabs v3・v4系 |
| --- | --- | --- |
| 喜び・高揚 | `[happy]` / `[excited]` | `[happy]` / `[excited]` |
| 好奇心 | `[curious]` | `[curious]` |
| 穏やかな説明 | `[calm]` / `[soft voice]` | `[warm, conversational tone]` |
| ささやき | `[whispering]` | `[whispers]` |
| 軽い笑い・ため息 | `[chuckling]` / `[sigh]` | `[chuckles]` / `[sighs]` |
| 間 | `[short pause]` / `[long pause]` | `[short pause]` / `[long pause]` |
| 重要語の強調 | 語の直前に `[emphasis]` | 文脈に合う発声指示と句読点で調整 |

Fishの配置・英語以外の指示・間の例は [S2の細かな音声制御](https://fish.audio/blog/fish-audio-s2-fine-grained-ai-voice-control-at-the-word-level/)、ElevenLabsの発声例・句読点・声との相性は [TTS Best practices](https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices) を参照する。

1. 元の言葉と意味を保ち、声の演技だけを追加する。聞こえない動作や映像の演出を音声タグにしない。
2. 文全体の感情は文頭、途中で変える話し方や強調はその語句の直前に置く。タグだけで終わる発声指示は避ける。
3. まず1文に主な感情を1つ置く。必要なら間や発声を足す。矛盾する感情や細かな切替を詰め込まない。
4. モデルと話者で効き方が変わるので短い区間を生成し、意図した演技・発音・間になったか試聴する。タグを読み上げた、過剰な笑いや効果音が入った場合は完成扱いせず、タグの語・配置・数を調整する。
5. 音声原稿にはタグを残し、字幕・表示原稿にはタグを出さない。タグや読みを直した区間は音声を再生成し、動画側の同期も確認する。

以下は日本語本文に英語タグを加える自作例（音声は未生成）:

```text
Fish:
[curious] 同じ要求が二回来たら、どうなるでしょう？ [short pause] [calm] ここで使うのが、[emphasis] べきとうキーです。

ElevenLabs:
[curious] 同じ要求が二回来たら、どうなるでしょう？ [short pause] [warm, conversational tone] ここで使うのが、べきとうキーです。
```

## 認証

認証はmise + ageで管理した `FISH_API_KEY` を `mise exec` から渡す。秘密情報は原稿・設定ファイル・ログに平文で置かず、privateな情報を含む台本をFish Audioへ送らない。認証情報の管理は [secret-env](../../secret-env/SKILL.md) に従う。

`mise exec` 後も `FISH_API_KEY` が見えないとき、空のprocess.envだけで未登録と結論しない。global/repo-local のmise設定への登録有無とage復号鍵（`MISE_AGE_KEY`）の注入を分けて確認する。確認だけでなく音声生成の `mise exec` 側にも同じ注入を付ける。登録済みキーが復号できれば再登録を求めずそのまま音声生成し、復号を確認しても不足する場合だけユーザーに質問する。

## 日本語の読み分けと確認

日本語では表示用の原稿とTTS用の読みを分ける。字幕には漢字・正式な識別子を残し、読みは文脈に合わせたかな表記にする。読みを直したら音声を再生成し、試聴で発音・数字・間を確認する。

## learn の動画から使う

教材の構成・動画生成コマンド・図と字幕の同期は [learn の動画生成](../../learn/SKILL.md#6-explainer-videos-am-video-3blue1brown-style) に従う。`am` CLIのパスは `learn/SKILL.md` と同じdirの `scripts/am.mjs` を解決し、呼び出し元skillの `CLAUDE_SKILL_DIR` を流用しない。

- `am video` は `--voice fish` を明示する。既定もFish Audioで、`auto` はその別名。無音指定は `--voice off`。
- モデル名はCLIが固定ヘッダーで指定する。CLIの引数は `am help video` で確認する。
- 各ナレーションはWAVで生成する。動画側は実際の音声長を使って同期する。

`FISH_TTS_READINGS_FILE` にJSONファイルのパスを渡すと、字幕を保ったまま読みだけをFish Audioへ送る。JSONは各ナレーションの表示テキストをキー、読み上げテキストを値にする:

```json
{"冪等キーで重複を防ぐ。":"[calm] べきとうキーで、[emphasis] ちょうふくをふせぐ。"}
```

全ナレーション分を用意し、フォーカス指定の `[名前]` は角括弧を外してキーにする。読みを直したら音声を再生成し、試聴で発音・間を確認する。

**Fishの感情タグはJSONの値（読み上げ専用テキスト）に入れる。** `> [happy] ...` のように動画の表示原稿へ直接書くと、`am` は角括弧をカメラのフォーカス指定として解釈する。TTS用テキストでは角括弧だけが外れて `happy` が残り、字幕にもタグ名が表示される。表示原稿とJSONのキーには感情タグを入れない。読み上げ専用テキストならタグが保持され、字幕にも出ない。タグを変更すると音声キャッシュも更新される。

ElevenLabsを明示的に使う場合、`am video --voice elevenlabs` は `ELEVENLABS_MODEL_ID` でモデルを指定できる（現行CLIの既定は `eleven_v4_turbo`）、話者は `ELEVENLABS_VOICE_ID`。ただし現行CLIの `FISH_TTS_READINGS_FILE` はFish専用で、ElevenLabsにはタグを保った読み上げ専用テキストを渡す経路がない。`am video` にタグを直接書けば有効になると案内しない。ElevenLabs APIへ直接渡す音声原稿では上のタグを使えるが、`learn` の動画で字幕と分けて使うにはCLI側の対応が必要。
