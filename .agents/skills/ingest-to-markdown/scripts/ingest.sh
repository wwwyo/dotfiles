#!/usr/bin/env bash
# anydoc でドキュメント(PDF/pptx/docx/xlsx/odt/rtf/epub/csv 等)を Markdown に変換する薄いラッパー。
# 生バイナリを残さず、grep/diff/LLM が読める md へ倒すのが目的。
#
# 使い方:
#   ingest.sh <input> [output_dir] [options]
#
#   input        変換元ファイル (anydoc 対応形式)。YouTube URL なら ingest-youtube.sh へ委譲する。
#   output_dir   出力先ディレクトリ (省略時は input と同じ場所)。保存先は呼び出し側が決める。
#
# options:
#   --keep-source     変換後も元ファイルを残す (既定は削除。スキャン PDF でページを除外した
#                      ときは、除外ページを agent が原本で確認できるよう指定が無くても残す)
#   --format <fmt>    入力形式を明示 (doc/docx/odt/pdf/ppt/pptx/rtf/epub/xlsx/ods/odp/csv)。
#                     anydoc は中身のシグネチャで判定するので通常は不要。CSV など署名の無い
#                     形式で拡張子が当てにならないときだけ使う。
#   --                以降を全て位置引数として扱う (dash 始まりのパス対策)
#
# なぜ anydoc か (docling から差し替えた経緯):
#   実測(日本語スライド4本)で pptx は anydoc が明確に上回った。docling は ‹#› のような
#   ページ番号プレースホルダを大量に混ぜ、リンクの URL と bold/ネストリストを落とす。
#   anydoc はそれらを保持し、変換は 2分 → 1秒未満になる。docling の売りだった OCR は、
#   日本語スライドに対しては読めない記号列しか返さず実効性が無かった。
#   代わりに受け入れた劣化は「画像は痕跡ごと消える」「PDF でリンク URL が落ちる」の 2 点。
#   詳細と掃除の指針は SKILL.md「変換結果の確認」を見よ。
#
# 実行系:
#   anydoc は mise(npm backend)で入れたものを PATH から使う。変換はローカル完結でネットワーク不要。
set -euo pipefail

# 第1引数が YouTube URL ならエントリポイントを1つに保つため ingest-youtube.sh へそのまま委譲する。
first_arg_lc="${1:-}"; first_arg_lc="${first_arg_lc,,}"
case "$first_arg_lc" in
  http://*youtube.com/watch\?*v=*|https://*youtube.com/watch\?*v=*|http://*youtube.com/shorts/*|https://*youtube.com/shorts/*|http://youtu.be/*|https://youtu.be/*)
    exec "$(dirname "$0")/ingest-youtube.sh" "$@"
    ;;
esac

usage() {
  echo "usage: ingest.sh <input> [output_dir] [--keep-source] [--format <fmt>]" >&2
  exit 2
}
[[ $# -ge 1 ]] || usage

need_val() { [[ $# -ge 2 ]] || { echo "missing value for $1" >&2; exit 2; }; }

INPUT=""; OUTDIR=""; KEEP_SOURCE=0; FORMAT=""
END_OPTS=0

add_positional() {
  if [[ -z "$INPUT" ]]; then INPUT="$1"
  elif [[ -z "$OUTDIR" ]]; then OUTDIR="$1"
  else echo "unexpected extra argument: $1" >&2; exit 2
  fi
}

while [[ $# -gt 0 ]]; do
  if [[ $END_OPTS -eq 1 ]]; then add_positional "$1"; shift; continue; fi
  case "$1" in
    --) END_OPTS=1; shift ;;
    --keep-source) KEEP_SOURCE=1; shift ;;
    --format) need_val "$@"; FORMAT="$2"; shift 2 ;;
    --*) echo "unknown option: $1" >&2; usage ;;
    *) add_positional "$1"; shift ;;
  esac
done

[[ -n "$INPUT" ]] || usage
[[ -f "$INPUT" ]] || { echo "input not found: $INPUT" >&2; exit 1; }
[[ -z "$OUTDIR" ]] && OUTDIR="$(dirname "$INPUT")"
mkdir -p -- "$OUTDIR"

stem="$(basename -- "$INPUT")"; stem="${stem%.*}"
OUTFILE="$OUTDIR/$stem.md"

# input と output が同一ファイルに解決されると、変換後の rm で成果物を消す。事前に弾く。
in_real="$(cd "$(dirname -- "$INPUT")" && pwd -P)/$(basename -- "$INPUT")"
out_real="$(cd "$OUTDIR" && pwd -P)/$(basename -- "$OUTFILE")"
if [[ "$in_real" == "$out_real" ]]; then
  echo "!! input and output resolve to the same file: $in_real" >&2
  echo "   出力先を変えるか、別ディレクトリを指定してください。" >&2
  exit 1
fi

# 失敗終了時、この実行で書いた $OUTFILE(実行前から在った同名ファイルは対象外)と、
# PDF パスの一時ディレクトリを片付ける。
OUTFILE_PREEXISTED=0
[[ -f "$OUTFILE" ]] && OUTFILE_PREEXISTED=1
cleanup() {
  local rc=$?
  [[ -n "${WORKDIR:-}" ]] && rm -rf -- "$WORKDIR"
  if [[ $rc -ne 0 && "$OUTFILE_PREEXISTED" -eq 0 ]]; then
    rm -f -- "$OUTFILE"
  fi
}
trap cleanup EXIT

if ! command -v anydoc >/dev/null 2>&1; then
  echo "!! anydoc が PATH にありません。mise install で入れてください (npm:@firecrawl/anydoc)。" >&2
  exit 1
fi

echo ">> converting: $INPUT -> $OUTFILE${FORMAT:+ (format=$FORMAT)}" >&2

# 呼び出し側(agent)にもそのまま見えるよう、anydoc の stderr は捨てずに毎回中継する。
# 非 PDF 分岐と、PDF 分岐(除外前後で最大2回)の両方から使うので関数化する。
run_anydoc() {
  local src="$1" dst="$2" errfile
  errfile="$(mktemp "${TMPDIR:-/tmp}/ingest-anydoc-stderr.XXXXXX")"
  local args=("$src" --output "$dst")
  [[ -n "$FORMAT" ]] && args+=(--format "$FORMAT")
  ANYDOC_RC=0
  anydoc "${args[@]}" 2>"$errfile" || ANYDOC_RC=$?
  ANYDOC_ERR="$(cat "$errfile")"
  rm -f -- "$errfile"
  if [[ -n "$ANYDOC_ERR" ]]; then
    printf '%s\n' "$ANYDOC_ERR" >&2
  fi
  return 0
}

# 「文字層が完全に無い」失敗は PDF 分岐の2箇所(スキャン判定・anydoc 除外判定)から使う。
fail_no_text_layer() {
  echo "!! 文字層が無いので OCR が要ります: $INPUT" >&2
  echo "   md 化するには別途 OCR が要ります(anydoc は OCR しない)。元ファイルは残します。" >&2
  exit 1
}

# PDF かどうかは --format の明示指定を優先し、無ければ拡張子で見る。anydoc 自身は
# シグネチャ判定だが、ページ除外の要否を決める分岐はここで一度だけ判定すれば足りる。
is_pdf_input=0
if [[ -n "$FORMAT" ]]; then
  [[ "${FORMAT,,}" == "pdf" ]] && is_pdf_input=1
else
  ext="${INPUT##*.}"; ext="${ext,,}"
  [[ "$ext" == "pdf" ]] && is_pdf_input=1
fi

IS_SCAN=0
SKIPPED_CSV=""
NEED_TOTAL=""

if [[ "$is_pdf_input" -eq 1 ]]; then
  POPPLER_OK=1
  for tool in pdfinfo pdfimages pdffonts pdfseparate pdfunite; do
    command -v "$tool" >/dev/null 2>&1 || POPPLER_OK=0
  done
  [[ "$POPPLER_OK" -eq 1 ]] || echo ">> poppler(pdfinfo/pdfimages/pdffonts/pdfseparate/pdfunite)が無いため、スキャン判定とページ除外を飛ばします: $INPUT" >&2

  WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/ingest-pdf.XXXXXX")"

  # スキャン判定: 全ページの面積に対し画像1枚が50%以上を覆うページを「全面画像ページ」とし、
  # それが全ページの50%を閾値にしたのは、スキャン時の綴じ代・余白でページごとの被覆率が
  # ばらつくため(80%だと実測の scan PDF で大半のページが漏れた)。ただし被覆率だけでは
  # 背景画像を敷いた電子的な PDF(スライド等)も拾ってしまうので、埋め込みフォントが
  # 1つも無いことを AND 条件にする(電子的に作った PDF は通常フォントを埋め込む)。
  if [[ "$POPPLER_OK" -eq 1 ]]; then
    if pdfinfo -f 1 -l 999999 -- "$INPUT" > "$WORKDIR/pdfinfo.txt" 2>/dev/null \
        && pdfimages -list -- "$INPUT" > "$WORKDIR/pdfimages.txt" 2>/dev/null \
        && pdffonts -- "$INPUT" > "$WORKDIR/pdffonts.txt" 2>/dev/null; then
      IS_SCAN="$(python3 - "$WORKDIR/pdfinfo.txt" "$WORKDIR/pdfimages.txt" "$WORKDIR/pdffonts.txt" <<'PY'
import re
import sys

info_path, images_path, fonts_path = sys.argv[1], sys.argv[2], sys.argv[3]

page_size = {}
with open(info_path, encoding="utf-8") as f:
    for line in f:
        m = re.match(r"Page\s+(\d+)\s+size:\s+([\d.]+)\s+x\s+([\d.]+)\s+pts", line)
        if m:
            page_size[int(m.group(1))] = (float(m.group(2)), float(m.group(3)))

coverage = {}
with open(images_path, encoding="utf-8") as f:
    for line in f:
        fields = line.split()
        if len(fields) != 16 or not fields[0].isdigit():
            continue
        page = int(fields[0])
        if page not in page_size:
            continue
        width, height = float(fields[3]), float(fields[4])
        x_ppi, y_ppi = float(fields[12]), float(fields[13])
        if x_ppi <= 0 or y_ppi <= 0:
            continue
        page_w, page_h = page_size[page]
        page_area = (page_w / 72.0) * (page_h / 72.0)
        if page_area <= 0:
            continue
        ratio = (width / x_ppi) * (height / y_ppi) / page_area
        if ratio > coverage.get(page, 0.0):
            coverage[page] = ratio

# pdffonts の列幅は type 列がフォント種別によって1〜2語になり可変なので、
# emb/sub/uni/object/ID が固定で末尾5列という位置関係から数える。
# Acrobat の OCR(Paper Capture)が焼く不可視文字レイヤーは HiddenHorzOCR/HiddenVertOCR という
# 埋め込みフォントを使うので、これは「埋め込みフォントがある」に数えない(数えるとスキャン
# PDF が軒並み非スキャン扱いになってしまう)。
has_embedded_font = False
with open(fonts_path, encoding="utf-8") as f:
    for line in f:
        fields = line.split()
        if len(fields) < 6:
            continue
        name = fields[0]
        emb, sub, uni = fields[-5], fields[-4], fields[-3]
        if emb not in ("yes", "no") or sub not in ("yes", "no") or uni not in ("yes", "no"):
            continue
        if emb == "yes" and not re.match(r"Hidden(Horz|Vert)OCR$", name):
            has_embedded_font = True
            break

total = len(page_size)
full = sum(1 for r in coverage.values() if r >= 0.5)
is_scan = total > 0 and full / total >= 0.8 and not has_embedded_font
print(1 if is_scan else 0)
PY
)" || IS_SCAN=0
    else
      echo ">> poppler での判定に失敗したためスキャン判定を飛ばします: $INPUT" >&2
    fi
  fi

  if [[ "$IS_SCAN" -eq 1 ]]; then
    # スキャン PDF: poppler で作り直すと anydoc が文字層を読めなくなる不具合が実測で
    # 確認できたため anydoc を使わず pdftotext で抜く。OCR 本文に対する見出し・表の
    # 構造推定もそもそも意味が薄い。
    if ! pdftotext -- "$INPUT" "$WORKDIR/pdftotext.txt" 2>"$WORKDIR/pdftotext.err"; then
      cat "$WORKDIR/pdftotext.err" >&2
      echo "!! pdftotext での抽出に失敗しました: $INPUT" >&2
      exit 1
    fi

    PARSE="$(python3 - "$WORKDIR/pdftotext.txt" "$WORKDIR/pdfinfo.txt" "$WORKDIR/scan_body.md" <<'PY'
import re
import sys

txt_path, info_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

with open(info_path, encoding="utf-8") as f:
    m = re.search(r"^Pages:\s+(\d+)", f.read(), re.MULTILINE)
if not m:
    print("PARSE_ERROR:")
    sys.exit(0)
total_pages = int(m.group(1))

with open(txt_path, encoding="utf-8") as f:
    raw = f.read()

pages = raw.split("\f")
if pages and pages[-1] == "":
    pages = pages[:-1]

# ページ番号がずれたまま <!-- page N --> を書かないよう、pdftotext の改ページ数と
# pdfinfo の総ページ数が食い違ったら失敗にする。
if len(pages) != total_pages:
    print("PAGECOUNT_MISMATCH:")
    sys.exit(0)

MIN_CHARS = 20
skipped = []
with open(out_path, "w", encoding="utf-8") as out:
    for i, page in enumerate(pages, start=1):
        non_ws = re.sub(r"\s", "", page)
        if len(non_ws) < MIN_CHARS:
            skipped.append(i)
            continue
        out.write(f"<!-- page {i} -->\n{page.strip()}\n\n")

print(f"{total_pages}:{','.join(str(n) for n in skipped)}")
PY
)" || PARSE="PARSE_ERROR:"

    NEED_TOTAL="${PARSE%%:*}"
    SKIPPED_CSV="${PARSE#*:}"

    if [[ "$NEED_TOTAL" == "PAGECOUNT_MISMATCH" ]]; then
      echo "!! pdftotext のページ数が pdfinfo の総ページ数と一致しませんでした: $INPUT" >&2
      exit 1
    fi
    if ! [[ "$NEED_TOTAL" =~ ^[0-9]+$ ]]; then
      echo "!! pdftotext 出力の解析に失敗しました: $INPUT" >&2
      exit 1
    fi

    [[ -s "$WORKDIR/scan_body.md" ]] || fail_no_text_layer

    mv "$WORKDIR/scan_body.md" "$OUTFILE"
    if [[ -n "$SKIPPED_CSV" ]]; then
      echo ">> skipped pages (no text layer): ${SKIPPED_CSV}" >&2
    fi
  else
    run_anydoc "$INPUT" "$OUTFILE"

    if [[ "$ANYDOC_RC" -eq 3 ]]; then
      # exit 3 の診断は "pages 1, 8, 180 of 260 need OCR" / "page 5 of 260 needs OCR" /
      # "pages 1-2 of 3 need OCR" / "all 4 pages need OCR" のいずれか。ページ番号の列と
      # 総ページ数だけ緩く取り出す(将来の文面の細かな揺れにも耐えるようにする)。
      # mise で anydoc を bump するときは、下記の正規表現パターンが依然として当たるか再確認する。
      PARSE="$(python3 - "$ANYDOC_ERR" <<'PY'
import re
import sys

msg = sys.argv[1]

m = re.search(r"all (\d+) pages? needs? OCR", msg)
if m:
    total = int(m.group(1))
    print(f"{total}:{','.join(str(n) for n in range(1, total + 1))}")
    sys.exit(0)

m = re.search(r"pages? ([\d,\s-]+?) of (\d+) needs? OCR", msg)
if m:
    total = int(m.group(2))
    nums = []
    for part in m.group(1).split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-")
            nums.extend(range(int(a), int(b) + 1))
        else:
            nums.append(int(part))
    print(f"{total}:{','.join(str(n) for n in nums)}")
    sys.exit(0)

print("PARSE_ERROR:")
PY
)" || PARSE="PARSE_ERROR:"

      NEED_TOTAL="${PARSE%%:*}"
      NEED_LIST_CSV="${PARSE#*:}"

      if ! [[ "$NEED_TOTAL" =~ ^[0-9]+$ ]]; then
        echo "!! anydoc の診断メッセージを解釈できませんでした: $INPUT" >&2
        exit 1
      fi

      IFS=',' read -ra NEED_ARR <<< "$NEED_LIST_CSV"

      [[ "${#NEED_ARR[@]}" -eq "$NEED_TOTAL" ]] && fail_no_text_layer

      if [[ "$POPPLER_OK" -eq 0 ]]; then
        echo "!! 一部ページに文字層が無く、poppler が無いため除外変換もできません: $INPUT" >&2
        exit 1
      fi

      declare -A NEED_SET=()
      for p in "${NEED_ARR[@]}"; do NEED_SET["$p"]=1; done

      if ! pdfseparate -- "$INPUT" "$WORKDIR/page_%d.pdf" 2>"$WORKDIR/pdfseparate.err"; then
        cat "$WORKDIR/pdfseparate.err" >&2
        echo "!! ページ分割に失敗しました: $INPUT" >&2
        exit 1
      fi

      KEPT=()
      for ((i = 1; i <= NEED_TOTAL; i++)); do
        [[ -n "${NEED_SET[$i]:-}" ]] && continue
        KEPT+=("$WORKDIR/page_$i.pdf")
      done

      if ! pdfunite "${KEPT[@]}" "$WORKDIR/filtered.pdf" 2>"$WORKDIR/pdfunite.err"; then
        cat "$WORKDIR/pdfunite.err" >&2
        echo "!! 除外ページ分の結合に失敗しました: $INPUT" >&2
        exit 1
      fi

      echo ">> skipped pages (no text layer): ${NEED_LIST_CSV}" >&2

      run_anydoc "$WORKDIR/filtered.pdf" "$OUTFILE"

      if [[ "$ANYDOC_RC" -eq 3 ]]; then
        # 除外後も need OCR が返るケース(このページ集合では除外しきれない)は無限ループに
        # せずここで打ち切る。元ファイルは残す。
        echo "!! ページ除外後も一部ページが文字層なしと判定されたため中断します: $INPUT" >&2
        exit 1
      elif [[ "$ANYDOC_RC" -ne 0 ]]; then
        echo "!! ページ除外後の変換に失敗しました: $INPUT" >&2
        exit 1
      fi

      SKIPPED_CSV="$NEED_LIST_CSV"
    elif [[ "$ANYDOC_RC" -ne 0 ]]; then
      echo "!! conversion failed: $INPUT" >&2
      exit 1
    fi
  fi
else
  run_anydoc "$INPUT" "$OUTFILE"
  if [[ "$ANYDOC_RC" -ne 0 ]]; then
    echo "!! conversion failed: $INPUT" >&2
    echo "   'OCR is required' と出た場合、この資料は画像だけで文字が入っていません。" >&2
    echo "   md 化するには別途 OCR が要ります(anydoc は OCR しない)。元ファイルは残します。" >&2
    exit 1
  fi
fi

[[ -f "$OUTFILE" ]] || { echo "!! expected output not found: $OUTFILE" >&2; exit 1; }

if [[ "$IS_SCAN" -eq 1 || -n "$SKIPPED_CSV" ]]; then
  HEADER_LINES=("- 元ファイル: $(basename -- "$INPUT")")
  if [[ "$IS_SCAN" -eq 1 ]]; then
    HEADER_LINES+=("- 種別: スキャン PDF(pdftotext でページ本文のみ抽出。見出し・表の構造は無く、本文は取り込み時の OCR 結果で誤字が混じる)")
  fi
  if [[ -n "$SKIPPED_CSV" ]]; then
    HEADER_LINES+=("- 除外したページ: ${SKIPPED_CSV//,/, }(文字層なし。全 ${NEED_TOTAL} ページ)")
  fi
  {
    printf '%s\n' "${HEADER_LINES[@]}"
    printf '\n'
    cat "$OUTFILE"
  } > "$WORKDIR/header_prepend.md"
  mv "$WORKDIR/header_prepend.md" "$OUTFILE"
fi

echo ">> done: $OUTFILE ($(wc -l < "$OUTFILE") lines)" >&2

if [[ "$KEEP_SOURCE" -eq 0 ]]; then
  if [[ -n "$SKIPPED_CSV" ]]; then
    # 除外ページは agent が原本の画像で確認する運用なので、消すと確認できなくなる。
    echo ">> kept source (skipped pages need a look): $INPUT" >&2
  else
    rm -f -- "$INPUT"
    echo ">> removed source: $INPUT" >&2
  fi
fi

echo "$OUTFILE"
