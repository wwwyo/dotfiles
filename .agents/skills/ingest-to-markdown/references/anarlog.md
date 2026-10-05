Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## 字幕なし動画・ローカル動画の文字起こし(Anarlog)

字幕が無い YouTube 動画、手元の mp4/mov、会議録画は Anarlog に取り込んで文字起こしする。Anarlog.app が起動している必要があり、Settings で Transcription model が選ばれていることが前提(未設定だと import が始まらない。その場合はユーザーに設定を依頼する)。

音声の import は GUI しか無い — 同梱 CLI(`anarlog-cli`)に音声 import 系のコマンドはない。新規 note を開き、••• → Upload audio かファイルのドラッグ&ドロップで取り込む。WAV / MP3 / OGG / MP4 / M4A / FLAC / WebM / AAC をそのまま渡せる(ffmpeg で音声抽出する必要はない)。この手順は agent 単独では完結しないので、ユーザーに import を依頼するか、GUI を操作できる手段(computer-use 等)で行う。文字起こしが終わるまで Anarlog を開いたままにする。

```bash
# YouTube で字幕が無かった場合: 音声だけ落とす
yt-dlp -f bestaudio -x --audio-format m4a -o "$TMPDIR/%(id)s.%(ext)s" "<youtube-url>"
# (GUI で Anarlog に import し、文字起こしの完了を待つ)
# 取り込んだ meeting を特定して transcript を書き出す
anarlog meetings list --json
anarlog meetings export <id> --format json -o <out.json>
```

CLI はアプリの起動時に `~/.local/bin/anarlog` へ自動で install される(App Store build には CLI が無い。cask/DMG build を使う)。入っていなければ Settings → Developers → Install で install するか、同梱バイナリのフルパス `/Applications/Anarlog.app/Contents/MacOS/anarlog-cli` を直接呼ぶ。

- `meetings list --json` の出力は `{command, data, pagination}` の envelope で、meeting は `.data[]` に入る(export の `--format json` は envelope 無しで `.transcripts[]` が直下)。取り込んだ meeting は直近に作成されたもの・title が一致するもので特定する。複数候補で絞れないときは id を推測で選ばずユーザーに確認する
- transcript の word は `.transcripts[].words[]` にあり、`text` / `start_ms` / `end_ms` / `state`(`final`|`pending`)を持つ。`meetings transcript` でも同じ word が取れるが、ワード数でページングされる(既定 200・上限 500)ので長い meeting は複数呼び出しになる。全文は `meetings export` で取るほうが簡単。大きい transcript はそのままコンテキストに載せず、jq で必要な分だけ project して読む
- `meetings export` は既存の出力ファイルを拒否する(exit 4)。上書きするなら `--force` を付けるが、既存ファイルを消すので確認してからにする

出力 md は YouTube 字幕と同じ形式(冒頭メタデータ + `[M:SS]` 付き段落)に揃える。export の markdown/json はこの形式そのままでは出ないので、自分で整形し直す。メタデータの「字幕の種別」は `anarlog` と書く。

- 映像が主役の動画(スライド・デモ画面)は文字起こしだけでは欠ける。必要な区間だけ `ffmpeg -ss <start> -to <end> -i in.mp4 -vf "select='gt(scene,0.3)'" -vsync vfr frame_%03d.jpg` でフレームを切り、md から相対パスで参照する。`scene` は前フレームとの画素差分(SAD)を正規化した 0〜1 の値で、閾値 0.3 は固定の目安に過ぎない。動画ごとに以下を踏まえて調整する。
  - 60fps のような高フレームレートは 1 コマあたりの差分が薄まり、緩やかな変化(フェード・スライドのアニメーション)を拾い損ねる。`fps=2` 等で先に間引いてから `select` に通す。
  - 判定と出力は分離する: 縮小(`scale=320:-1`)してから `select` を通すと計算量が落ちるが、出てくる jpg も縮小されてしまう。文字起こしを補う目的(スライドの文字を読む)なら判定は縮小版・切り出しは元解像度の2段構えにする。
  - 閾値が合っているか分からないときは `ffmpeg -i in.mp4 -vf "select='gte(scene,0)',metadata=print:file=scene.txt" -f null -` で全フレームの `scene` 値を吐かせ、実際の分布を見てから閾値を決める。
