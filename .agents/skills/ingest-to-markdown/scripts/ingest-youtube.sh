#!/usr/bin/env bash
# YouTube 動画の字幕(手動優先、無ければ自動生成)を yt-dlp で取得し、整形した Markdown として保存する。
# 音声DL + ASR文字起こしはスコープ外(字幕が無い動画はエラーにする。将来手段として SKILL.md に記載)。
#
# 使い方:
#   ingest-youtube.sh <youtube-url> [output_dir] [options]
#
#   youtube-url  youtube.com/watch, youtube.com/shorts, youtu.be のいずれか
#   output_dir   出力先ディレクトリ (省略時はカレントディレクトリ)
#
# options:
#   --lang <langs>    字幕言語の優先リスト (yt-dlp の --sub-langs 形式、既定 "ja,en")
#   --name <stem>     出力ファイル名の stem を明示指定 (省略時はタイトルをサニタイズ)
#   --keep-vtt        中間の vtt を output_dir に残す (既定は tmpdir ごと削除)
#   --                以降を全て位置引数として扱う (dash 始まりパス対策)
#
# 字幕の選び方(手動優先):
#   --lang の優先順に言語を1つずつ見て、その言語に手動字幕があれば即採用、無ければ自動生成字幕を見る。
#   採用できた時点で走査を止める(例: --lang "ja,en" で ja に自動字幕しか無く en に手動字幕があっても、
#   ja の自動字幕を優先する。言語の優先順位を「手動/自動」より上位に置く設計)。
#   採否は yt-dlp のメタデータ(--dump-json の subtitles/automatic_captions)を見て「先に」決め、
#   決まった1言語1種別だけを改めてダウンロードする。yt-dlp 自身に --write-subs/--write-auto-subs を
#   両方渡して結果から推測する方式だと、複数言語分のファイルが降ってきて種別判定が曖昧になるため。
#
# 注意: yt-dlp は youtube.com へのネットワークアクセスが要るため、agent の sandbox が
#   network を止める環境では sandbox 外で呼ぶ(docling 版 ingest.sh と同じ理由)。
set -euo pipefail

usage() {
  echo "usage: ingest-youtube.sh <youtube-url> [output_dir] [--lang <langs>] [--name <stem>] [--keep-vtt]" >&2
  exit 2
}
[[ $# -ge 1 ]] || usage

need_val() { [[ $# -ge 2 ]] || { echo "missing value for $1" >&2; exit 2; }; }

URL=""; OUTDIR=""; LANGS="ja,en"; NAME=""; KEEP_VTT=0
END_OPTS=0

add_positional() {
  if [[ -z "$URL" ]]; then URL="$1"
  elif [[ -z "$OUTDIR" ]]; then OUTDIR="$1"
  else echo "unexpected extra argument: $1" >&2; exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  if [[ $END_OPTS -eq 1 ]]; then add_positional "$1"; shift; continue; fi
  case "$1" in
    --) END_OPTS=1; shift ;;
    --lang) need_val "$@"; LANGS="$2"; shift 2 ;;
    --name) need_val "$@"; NAME="$2"; shift 2 ;;
    --keep-vtt) KEEP_VTT=1; shift ;;
    --*) echo "unknown option: $1" >&2; usage ;;
    *) add_positional "$1"; shift ;;
  esac
done

[[ -n "$URL" ]] || usage
[[ -z "$OUTDIR" ]] && OUTDIR="."
mkdir -p -- "$OUTDIR"

# youtube.com(watch/shorts) / youtu.be の軽い検証。大文字ドメインなども拾えるよう小文字化して比較する。
url_lc="${URL,,}"
case "$url_lc" in
  http://*youtube.com/watch\?*v=*|https://*youtube.com/watch\?*v=*|http://*youtube.com/shorts/*|https://*youtube.com/shorts/*|http://youtu.be/*|https://youtu.be/*)
    ;;
  *)
    echo "error: YouTube の URL ではありません(youtube.com/youtu.be のみ対応): $URL" >&2
    exit 1
    ;;
esac

echo ">> metadata: $URL" >&2

# --dump-json は simulate 扱いになり実ファイルは書かれない(空 tmpdir で確認済み)。
# --write-subs/--write-auto-subs を一緒に渡すと automatic_captions の全量リストまで JSON に載るので、
# 「この動画にどの言語の手動/自動字幕があるか」を追加のネットワーク往復なしで判定できる。
METAFILE="$(mktemp "${TMPDIR:-/tmp}/ingest-youtube-meta.XXXXXX")"
cleanup_meta() { rm -f -- "$METAFILE"; }
trap cleanup_meta EXIT

if ! yt-dlp --skip-download --no-playlist --write-subs --write-auto-subs \
    --sub-langs "$LANGS" --dump-json -- "$URL" > "$METAFILE" 2>&1; then
  echo "!! メタデータ取得に失敗しました:" >&2
  cat "$METAFILE" >&2
  exit 1
fi

# メタデータと字幕言語一覧を、bash から安全に読める形(shlex.quote 済みの代入文)へ落とす。
META_ASSIGN="$(python3 - "$METAFILE" <<'PY'
import json
import shlex
import sys

with open(sys.argv[1], encoding="utf-8") as f:
    d = json.load(f)


def q(value):
    return shlex.quote("" if value is None else str(value))


manual_langs = sorted((d.get("subtitles") or {}).keys())
auto_langs = sorted((d.get("automatic_captions") or {}).keys())

print(f"YTM_ID={q(d.get('id'))}")
print(f"YTM_TITLE={q(d.get('title'))}")
print(f"YTM_CHANNEL={q(d.get('channel') or d.get('uploader'))}")
print(f"YTM_UPLOAD_DATE={q(d.get('upload_date'))}")
print(f"YTM_WEBPAGE_URL={q(d.get('webpage_url') or sys.argv[1])}")
print(f"YTM_MANUAL_LANGS={q(','.join(manual_langs))}")
print(f"YTM_AUTO_LANGS={q(','.join(auto_langs))}")
PY
)"
eval "$META_ASSIGN"

# 出力ファイル名: --name 指定があればそれ、無ければタイトルをサニタイズ、空になれば video id。
# 字幕ダウンロード前にここで決めて重複チェックする(どうせ失敗するダウンロードを避ける)。
if [[ -n "$NAME" ]]; then
  STEM="$NAME"
else
  STEM="$(python3 - "$YTM_TITLE" <<'PY'
import re
import sys

title = sys.argv[1]
# ファイル名として問題になりやすい記号だけを '-' に置換する。日本語はそのまま維持。
cleaned = re.sub(r'[/\\:*?"<>|]', '-', title)
cleaned = re.sub(r'-{2,}', '-', cleaned).strip(' -')
print(cleaned)
PY
)"
  [[ -z "$STEM" ]] && STEM="$YTM_ID"
fi

OUTFILE="$OUTDIR/$STEM.md"
[[ -e "$OUTFILE" ]] && {
  echo "!! 出力先に同名ファイルが既に存在します: $OUTFILE (--name で別名を指定するか削除してください)" >&2
  exit 1
}

# --lang の優先順に「手動があれば手動、無ければ自動」で最初に見つかった1言語だけを採用する。
IFS=',' read -ra LANG_ARR <<< "$LANGS"
IFS=',' read -ra MANUAL_ARR <<< "$YTM_MANUAL_LANGS"
IFS=',' read -ra AUTO_ARR <<< "$YTM_AUTO_LANGS"

contains() {
  local needle="$1"; shift
  local x
  for x in "$@"; do [[ "$x" == "$needle" ]] && return 0; done
  return 1
}

WIN_LANG=""; WIN_TYPE=""
for l in "${LANG_ARR[@]}"; do
  if contains "$l" "${MANUAL_ARR[@]}"; then WIN_LANG="$l"; WIN_TYPE="manual"; break; fi
  if contains "$l" "${AUTO_ARR[@]}"; then WIN_LANG="$l"; WIN_TYPE="auto"; break; fi
done

if [[ -z "$WIN_LANG" ]]; then
  echo "!! 字幕なし(--lang '$LANGS' に該当する手動/自動字幕が見つからない): $URL" >&2
  echo "   ASR(音声認識)での文字起こしは未対応。yt-dlp -x + Whisper 等は将来手段。" >&2
  exit 1
fi

echo ">> subtitle: lang=$WIN_LANG type=$WIN_TYPE" >&2

# 採用が決まった1言語1種別だけを改めて取得する(曖昧さを残さないため tmpdir へ)。
WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/ingest-youtube.XXXXXX")"
cleanup_all() { rm -rf -- "$WORKDIR"; cleanup_meta; }
trap cleanup_all EXIT

(
  cd "$WORKDIR"
  if [[ "$WIN_TYPE" == "manual" ]]; then
    yt-dlp --skip-download --no-playlist --write-subs \
      --sub-langs "$WIN_LANG" --sub-format vtt -o "%(id)s.%(ext)s" -- "$URL"
  else
    yt-dlp --skip-download --no-playlist --write-auto-subs \
      --sub-langs "$WIN_LANG" --sub-format vtt -o "%(id)s.%(ext)s" -- "$URL"
  fi
)

VTT_FILE="$WORKDIR/$YTM_ID.$WIN_LANG.vtt"
[[ -f "$VTT_FILE" ]] || { echo "!! 字幕ファイルが見つかりません: $VTT_FILE" >&2; exit 1; }

echo ">> converting: $VTT_FILE -> $OUTFILE" >&2

VTT_FILE="$VTT_FILE" OUTFILE="$OUTFILE" \
YTM_ID="$YTM_ID" YTM_TITLE="$YTM_TITLE" YTM_CHANNEL="$YTM_CHANNEL" \
YTM_UPLOAD_DATE="$YTM_UPLOAD_DATE" YTM_WEBPAGE_URL="$YTM_WEBPAGE_URL" \
WIN_LANG="$WIN_LANG" WIN_TYPE="$WIN_TYPE" \
python3 <<'PY'
import html
import os
import re
from collections import deque
from datetime import date

VTT_PATH = os.environ["VTT_FILE"]
OUT_PATH = os.environ["OUTFILE"]

CUE_RE = re.compile(r'^((?:\d{2}:)?\d{2}:\d{2}\.\d{3})\s*-->\s*((?:\d{2}:)?\d{2}:\d{2}\.\d{3})')
TAG_RE = re.compile(r'<[^>]*>')
WS_RE = re.compile(r'\s+')

PARA_GAP_SEC = 3.0
PARA_MAX_CHARS = 800


def parse_ts(ts: str) -> float:
    parts = [float(p) for p in ts.split(':')]
    while len(parts) < 3:
        parts.insert(0, 0.0)
    h, m, s = parts
    return h * 3600 + m * 60 + s


def fmt_ts(sec: float) -> str:
    total = int(sec)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"[{h}:{m:02d}:{s:02d}]"
    return f"[{m}:{s:02d}]"


def parse_cues(text: str):
    """vtt を (start_sec, end_sec, [clean_line, ...]) のリストへ分解する。

    ヘッダ(WEBVTT/Kind/Language)・cue 識別子・タイミング行の位置指定(align/position)は、
    どれもタイミング行の正規表現にマッチしないので自然に読み飛ばされる。
    cue 本文は行ごとに保持する(dedupe を行単位で行うため。cue 単位で結合すると
    ローリング表示の再掲行が新規行と混ざり、重複判定できなくなる)。
    """
    lines = text.splitlines()
    cues = []
    i, n = 0, len(lines)
    while i < n:
        m = CUE_RE.match(lines[i].strip())
        if not m:
            i += 1
            continue
        start_sec = parse_ts(m.group(1))
        end_sec = parse_ts(m.group(2))
        i += 1
        body = []
        # cue の終端は「長さ0の空行」。yt-dlp の auto 字幕は cue 内に空白1文字の
        # プレースホルダ行を置くので、strip して判定すると新規行を cue 外へ取りこぼす。
        while i < n and lines[i] != '' and not CUE_RE.match(lines[i].strip()):
            # インラインのタイムスタンプタグ(<00:00:00.000>)や <c> 等の装飾タグを除去し、
            # 残った HTML エンティティを戻す(auto 字幕の話者交代マーカー >> は &gt;&gt; で来る)。
            # unescape をタグ除去より先にやると &lt;c&gt; のような字幕本文が偽タグ化して消えるので、この順序。
            clean = WS_RE.sub(' ', html.unescape(TAG_RE.sub('', lines[i]))).strip()
            if clean:
                body.append(clean)
            i += 1
        if body:
            cues.append((start_sec, end_sec, body))
    return cues


def dedupe_rolling(cues):
    """自動生成字幕特有のローリング表示の再掲行を落とし、(start_sec, end_sec, text) の列にする。

    auto 字幕の各 cue は「確定済みの前行の再掲 + 新規行」の2行構成で、同じ行が
    連続する2〜3個の cue に跨って再出現する。隣接1行の比較では cue 内の行構成
    (空行や部分行の interleave)次第で取りこぼすため、直近に出力した数行の
    ウィンドウと照合して落とす。
    """
    out = []
    recent = deque(maxlen=3)
    for start_sec, end_sec, body in cues:
        for line in body:
            if line in recent:
                continue
            recent.append(line)
            out.append((start_sec, end_sec, line))
    return out


def group_paragraphs(cues):
    """cue 間のギャップが3秒超、または段落が800文字を超えたら段落を割る。"""
    paragraphs = []
    para_start = None
    para_end = None
    parts: list[str] = []

    def flush():
        if parts:
            paragraphs.append((para_start, ' '.join(parts)))

    for start_sec, end_sec, text in cues:
        if para_start is None:
            para_start, para_end, parts = start_sec, end_sec, [text]
            continue
        gap = start_sec - para_end
        prospective_len = sum(len(p) for p in parts) + len(text)
        if gap > PARA_GAP_SEC or prospective_len > PARA_MAX_CHARS:
            flush()
            para_start, parts = start_sec, [text]
        else:
            parts.append(text)
        para_end = end_sec
    flush()
    return paragraphs


with open(VTT_PATH, encoding="utf-8") as f:
    raw = f.read()

cues = dedupe_rolling(parse_cues(raw))
if not cues:
    raise SystemExit(f"字幕本文が空です(パース結果0件): {VTT_PATH}")

paragraphs = group_paragraphs(cues)

upload_date_raw = os.environ.get("YTM_UPLOAD_DATE", "")
if len(upload_date_raw) == 8:
    upload_date = f"{upload_date_raw[0:4]}-{upload_date_raw[4:6]}-{upload_date_raw[6:8]}"
else:
    upload_date = upload_date_raw or "不明"

win_type = os.environ["WIN_TYPE"]
type_label = "manual" if win_type == "manual" else "auto"

header = (
    f"# {os.environ['YTM_TITLE']}\n\n"
    f"- 元動画: {os.environ['YTM_WEBPAGE_URL']}\n"
    f"- チャンネル: {os.environ['YTM_CHANNEL']}\n"
    f"- 公開日: {upload_date}\n"
    f"- 取得日: {date.today().isoformat()}\n"
    f"- 字幕: {os.environ['WIN_LANG']} ({type_label})\n\n"
)

body = "\n\n".join(f"{fmt_ts(s)} {t}" for s, t in paragraphs)

with open(OUT_PATH, "w", encoding="utf-8") as f:
    f.write(header + body + "\n")
PY

if [[ "$KEEP_VTT" -eq 1 ]]; then
  cp -- "$VTT_FILE" "$OUTDIR/$STEM.vtt"
  echo ">> kept vtt: $OUTDIR/$STEM.vtt" >&2
fi

echo ">> done: $OUTFILE ($(wc -l < "$OUTFILE") lines)" >&2

echo "$OUTFILE"
