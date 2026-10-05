#!/usr/bin/env bash
# HTML 内の <img src="相対パス"> を base64 data URI に置き換え、単体ファイルにする。
# 単体配布が前提の作業レポートは、外部ファイル参照を残したまま渡さない。
#
# 使い方:
#   tools/embed.sh report.html
#   → report.embedded.html を同じディレクトリに生成する
#
# 画像は先に webp へ圧縮しておく（cwebp が入っていれば）:
#   cwebp -q 80 in.png -o out.webp
#
# src の ?query / #fragment は無視してファイル解決する。見つからない画像があれば
# stderr に warn を出し、最後に非 0 で終了する。
set -euo pipefail

in="${1:?usage: embed.sh <report.html>}"
dir="$(cd "$(dirname "$in")" && pwd)"
base="$(basename "$in" .html)"
out="$dir/${base}.embedded.html"

cp "$in" "$out"

set +e
perl -CSD -i -e '
  use strict;
  use warnings;
  use MIME::Base64;

  my ($outfile, $dir) = @ARGV;
  open(my $fh, "<:raw", $outfile) or die "cannot open $outfile: $!";
  local $/;
  my $html = <$fh>;
  close $fh;

  my %mime = (
    webp => "image/webp",
    png  => "image/png",
    jpg  => "image/jpeg",
    jpeg => "image/jpeg",
    gif  => "image/gif",
    svg  => "image/svg+xml",
  );

  my $missing = 0;

  $html =~ s{(<img\b[^>]*>)}{
    my $tag = $1;
    if ($tag =~ /\bsrc\s*=\s*(["\x27])(.*?)\1/is) {
      my ($q, $src) = ($1, $2);
      if ($src !~ m{^(?:https?:|data:)}i) {
        (my $clean = $src) =~ s/[?#].*$//;
        my $path = "$dir/$clean";
        if (-f $path) {
          my ($ext) = lc($clean) =~ /\.([^.\/]+)$/;
          my $type = $mime{$ext // ""} // "application/octet-stream";
          open(my $ifh, "<:raw", $path) or die "cannot open $path: $!";
          local $/;
          my $data = <$ifh>;
          close $ifh;
          my $b64 = encode_base64($data, "");
          my $newsrc = "data:$type;base64,$b64";
          $tag =~ s/\Q$src\E/$newsrc/;
        } else {
          warn "warn: image not found, skipped: $src\n";
          $missing++;
        }
      }
    }
    $tag
  }gse;

  open(my $ofh, ">:raw", $outfile) or die "cannot write $outfile: $!";
  print $ofh $html;
  close $ofh;

  exit($missing ? 1 : 0);
' "$out" "$dir"
status=$?
set -e

echo "$out"
exit "$status"
