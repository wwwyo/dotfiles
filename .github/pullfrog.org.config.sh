#!/usr/bin/env bash
# Server-side Pullfrog org defaults for the wwwyo personal account — SSOT.
#
# Repo-level settings live in each repo's .github/pullfrog.config.sh.
# This file covers the org scope (`--org wwwyo`). Keys accepted at org level
# are only: model, effort, instructions, xrepo.brief, billing.*.
# A repo-level `config unset` restores inheritance of these org values.
#
# Apply:  .github/pullfrog.org.config.sh        (uses gh auth)
# Audit:  mise exec -- pullfrog config list --org wwwyo
#
# billing.* is managed in the Pullfrog console, not here — payment settings
# are consequential writes and stay out of this script.
set -euo pipefail

PF=(mise exec -- pullfrog)

pf_unset() { "${PF[@]}" config unset "$1" --org wwwyo --yes; }

# explicit unsets — keep the backend converged on this file
pf_unset model   # repos pin their own model (see each pullfrog.config.sh)
pf_unset effort  # repos pin their own effort
pf_unset xrepo.brief  # org-only key, no repo override exists; unused

"${PF[@]}" config set instructions --org wwwyo --yes --file - <<'PULLFROG_ORG_INSTRUCTIONS'
すべての出力（返答・コメント・レビュー本文）は日本語で書くこと。

レビューの各指摘には、重要度に応じて以下のいずれかのラベルを必ず付けること:

- P0: 最優先。リリースを止めるような致命的な問題
- P1: 緊急。早急に修正すべき重要な問題
- P2: 通常。いずれ修正すべき一般的な問題
- P3: 低優先度。影響の小さい問題

レビュー・再レビュー・指摘解消の再確認では、毎回、現在の PR の承認可否を判定すること。新規コード差分や新規指摘がない場合も、既存指摘の解消状況と最新の QA 証跡を確認し、レビュー判定を投稿する。「追加の指摘がない」ことを理由に、結果コメントだけで終了しないこと。

再レビューでは、各指摘について現在の thread の状態と回答の理由・根拠を確認すること。コード差分による修正で解消されたものに加え、仕様上不要・誤検知・合理的な設計判断など、妥当な理由と根拠を示して resolve された thread も解消済みとして扱う。コード差分の追加を解消の必須条件にしない。ただし、根拠のない resolve は解消とみなさない。
解消済みの指摘を再提起するのは、既存の回答で解決していない具体的な欠陥または新しい証拠がある場合に限り、その内容を明示すること。同じ主張の繰り返しで承認を妨げない。

P3 は承認を妨げない。未解決の P0・P1・P2 の指摘や判断に必要な証跡の不足があれば承認しない。P0・P1・P2 の指摘がすべて解消され、承認可能と確認できた場合は、設定に従って承認判定を出し、`pullfrog-approval` check に反映すること。GitHub の Approve 投稿を無効にしている場合も、approval verdict の判定は省略しないこと。
PULLFROG_ORG_INSTRUCTIONS
