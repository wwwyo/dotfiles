#!/usr/bin/env bash
# Server-side Pullfrog config for wwwyo/dotfiles — this file is the SSOT.
#
# .github/workflows/pullfrog.yml is a Pullfrog-managed file kept pristine
# (byte-identical across repos, updated by upstream PRs). Repo-level settings
# (model, effort, review/issue/label modes, hooks, ...) live in Pullfrog's
# backend and are invisible to git — this script records and reapplies them.
#
# Apply:  .github/pullfrog.config.sh        (uses gh auth)
# Audit:  mise exec -- pullfrog config list --repo wwwyo/dotfiles
#
# BYOK keys are org-scoped (OPENCODE_API_KEY inherited) — see `pf secret list`.
#
# Pinned models can vanish upstream: opencode-go free/contributor tiers are
# removed without notice (space-bunny-free's deletion broke pullfrog checks on
# every repo at once). Recovery = `pullfrog config set model <new> --repo <r>`
# to fix the backend immediately AND update the pf_set model line below —
# re-running this script otherwise re-pins the dead model.
set -euo pipefail

REPO="wwwyo/dotfiles"
PF=(mise exec -- pullfrog)

pf_set()   { "${PF[@]}" config set   "$1" "$2" --repo "$REPO" --yes; }
pf_unset() { "${PF[@]}" config unset "$1"     --repo "$REPO" --yes; }


pf_set enabled 'true'
pf_set model 'opencode-go/muse-spark-1.3-contributor'
pf_set effort '1'
pf_set progress-comments 'true'
pf_set oss 'true'
pf_set push 'enabled'
pf_set shell 'restricted'
pf_set signed-commits 'false'
pf_set auto-merge 'false'
pf_set mention.enabled 'true'
pf_set mention.non-collaborators 'false'
pf_set review.mode 'agent'
pf_set review.non-collaborators 'false'
pf_set review.re-review 'true'
pf_set review.approve 'false'
pf_set review.drafts 'true'
pf_set review.own-prs 'false'
pf_set review.status-check 'true'
pf_set review.approval-check 'true'
pf_set issue.mode 'none'
pf_set issue.non-collaborators 'true'
pf_set label.enabled 'false'
pf_set address-reviews.enabled 'true'
pf_set fix-ci.own-prs 'true'
pf_set fix-ci.reviewed-prs 'false'

"${PF[@]}" config set hooks.setup --repo "$REPO" --yes --file - <<'PULLFROG_HOOK_SETUP'
# mise toolchain: install mise if absent, install repo tools, expose shims on PATH
# NB: set -e is intentionally AFTER the file guard — `ls` exits non-zero when
# only some of the files exist, and pipefail would turn that into a false negative.
ls mise.toml .mise.toml .config/mise.toml 2>/dev/null | grep -q . || exit 0
set -euo pipefail
command -v mise >/dev/null 2>&1 || curl -fsSL https://mise.run | sh
export PATH="$HOME/.local/bin:$PATH"
mise trust -a 2>/dev/null || true
mise install -y
mkdir -p "$HOME/.local/bin"
ln -sf "$HOME"/.local/share/mise/shims/* "$HOME"/.local/bin/ 2>/dev/null || true
PULLFROG_HOOK_SETUP

"${PF[@]}" config set prompts.review --repo "$REPO" --yes --file - <<'PULLFROG_REVIEW_INSTRUCTIONS'
通常の不具合・回帰レビューを維持したうえで、以下の観点も確認する。この repo では標準手順の「未解決の疑問がある場合だけ specialist を dispatch」という条件を、以下の観点別分担に置き換える。親は差分全体と周辺コードを理解し、差分に関係する各観点をそれぞれ別の read-only の `reviewfrog` subagent に検証させる。親が問題なしと判断できても、該当観点の独立した検証を省略しない。

1. 通常レビュー: 従来の不具合・回帰の判断基準を維持し、挙動に影響する差分について、動作の正しさ、境界条件、回帰、外部 API・consumer との契約を独立して確認する。
2. 可搬性・設定の境界: 別ユーザー・新しいマシン・対応 OS・CI・worktree でも成立するか確認する。ユーザー名入り絶対パス、手元の global 設定や未宣言の tool・認証・環境変数への依存、machine/session 固有の値を共有設定へ取り込む変更、local 値を apply で消す・巻き戻す変更を調べる。設定の正本・template・配備先・consumer を辿り、値の展開方法や OS 分岐を確認する。宣言済みの共通設定や、明示された OS 専用の範囲は欠陥とみなさない。
3. ガバナンス・文書・コメント: AGENTS.md と関連 skill の規約から正本と責務を確認し、同じ手順・規約・設定値を複数箇所で独立管理していないか、参照先・label・anchor が古くなっていないか調べる。手順・運用ナレッジは skills とその references、意思決定の理由・トレードオフ・履歴は ADR、機能の課題・目的・要件は PRD を推奨する。AGENTS.md・README には repo の入口や機構と正本への参照を置き、手順やナレッジの全文を重複させない。コード・設定から直接読める処理や値の逐語説明、冗長なコメントを確認する。非自明な制約・採らなかった案の理由、利用者向けの契約を説明する document コメントは残す。

可搬性に関わる設定・script・配備の変更には観点2、文書・skill・コメントの変更には観点3を適用する。レビュー指示など agent の挙動を変える設定も観点1の対象とする。対象外の観点のために subagent を起動しない。親は各観点を、その差分で支持・反証できる具体的な問いに絞り、複数の独立した問いは一度に dispatch して並列実行する。同一観点に独立した問いが複数あれば分ける。

各 subagent には checkout_pr が返した差分の絶対パス（再レビューでは incrementalDiffPath も）と対象範囲を渡し、Task の description に観点と問いを示す短い名前を付ける。他の reviewer の判断や親の結論を先に与えず、独立して調査させる。subagent は編集・投稿を行わず、根拠を親へ返す。親がすべての結果を検証し、重複・誤検知を除いて一つのレビューと承認判定を投稿する。レビュー本文に、subagent が確認した観点と対象外の観点を短く記す。起動に失敗した観点は検証済みと書かず、標準手順に従って再試行・代替調査し、制限を明示する。

指摘は変更に起因する具体的な箇所・根拠・影響・最小限の改善案を示す。設定の混入や正本の競合は実際の破損・drift の影響で重要度を判断する。文書の置き場の推奨やコメントの短縮だけなら P3 とし、承認を妨げない。既存文書の全面移動、PRD/ADR の形式的な新設、自明なコメントの追加を要求しない。明示された例外や既に合理的な根拠で解消された指摘を尊重し、今回と無関係な既存の問題は指摘しない。
PULLFROG_REVIEW_INSTRUCTIONS

# explicit unsets — keep the backend converged on this file
# `instructions` stays unset so the org default applies (see pullfrog.org.config.sh)
pf_unset instructions
pf_unset env-allowlist
pf_unset hooks.post-checkout
pf_unset hooks.pre-push
pf_unset hooks.stop
pf_unset prompts.build
pf_unset prompts.plan
pf_unset prompts.address-reviews
pf_unset prompts.fix-ci
pf_unset mention.instructions
pf_unset issue.instructions
pf_unset label.instructions
