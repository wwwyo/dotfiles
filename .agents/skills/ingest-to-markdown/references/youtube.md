Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## YouTube の取り込み

YouTube 動画は anydoc の対象外(バイナリでもドキュメントでもない)なので、専用スクリプトで字幕を Markdown 化する。字幕が無い動画は yt-dlp で音声だけ落として[Anarlog 文字起こし](anarlog.md)に回す。

```bash
<skill_dir>/scripts/ingest-youtube.sh <youtube-url> [output_dir] [options]
```

`<skill_dir>/scripts/ingest.sh` に YouTube URL(youtube.com/watch, youtube.com/shorts, youtu.be)をそのまま渡してもよい。第1引数の URL 形式を見て内部で `ingest-youtube.sh` に委譲するので、入口は 1 つのままでよい。

| option | 既定 | 説明 |
|--------|------|------|
| `--lang <langs>` | `ja,en` | 字幕言語の優先リスト(yt-dlp の `--sub-langs` 形式) |
| `--name <stem>` | タイトルから自動生成 | 出力ファイル名の stem を明示指定 |
| `--keep-vtt` | 削除する | 変換前の vtt を `output_dir` に残す(既定は tmpdir ごと破棄) |
| `--` | — | 以降を位置引数扱い(dash 始まり URL 対策) |

手動字幕優先・自動字幕フォールバック: `--lang` の優先順に言語を1つずつ見て、その言語に手動字幕があれば即採用、無ければ自動生成字幕を見る、という探索を「見つかった時点で」止める。つまり言語の優先順位を manual/auto の優先順位より上位に置く(例: `--lang "ja,en"` で ja が自動字幕しか無く en に手動字幕があっても、ja の自動字幕を採る)。採否は yt-dlp のメタデータ(`--dump-json` の `subtitles`/`automatic_captions`)から先に決め、決まった1言語1種別だけを改めてダウンロードする(both flags を投げて結果から推測する方式だと、複数言語分のファイルが降ってきて種別判定が曖昧になるため)。

出力フォーマット: 冒頭にメタデータ(タイトル・元URL・チャンネル・公開日・取得日・採用した字幕の言語と種別)を bullet で置き、本文は cue のタイミング行・位置指定・インラインタグ(`<c>`, `<00:00:00.000>` 等)を除去してプレーンテキスト化する。cue 間のギャップが3秒超、または段落が800文字を超えたところで段落を割り、各段落の先頭に `[M:SS]`(1時間超は `[H:MM:SS]`)の開始タイムスタンプを付ける。

例:

```bash
<skill_dir>/scripts/ingest-youtube.sh "https://www.youtube.com/watch?v=xxxxxxxxxxx" raw/refs/ --lang "en,ja"
```
