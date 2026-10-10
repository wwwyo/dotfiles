# Pullfrog の導入

ステップ 3 で Pullfrog 導入 yes と答えた場合のみ実施。**repo 作成と visibility 確定後に行う**。

1. **Install + workflow**: CLI は dotfiles のグローバル mise 設定（`home/dot_config/mise/config.toml` の `npm:pullfrog`）でバージョン管理する。未導入なら `mise install npm:pullfrog`、repo dir で `mise exec -- pullfrog init`。GitHub App を repo に install し dashboard が開く。`.github/workflows/pullfrog.yml` は Pullfrog 側から届く PR（or console の指示）をそのまま取り込む — **手で書いたり `with:` を足したりしない**。managed file なので全 repo byte 同一を保ち、model 等を書くと console の repo 設定に負けて dead config になる
2. **`.github/pullfrog.config.sh` を生成**: repo-level 設定（model・effort・review/issue/label mode・hooks…）は backend にしか無く git から見えないため、`pf config set/unset` を並べたこの script を SSOT として置く。既存 repo の同名ファイルをコピーして `REPO=` を書き換え、CLI 呼び出しは `PF=(mise exec -- pullfrog)` に揃える。repo ごとに以下を調整する:
   - `model`・`effort`: [delegate](../../delegate/SKILL.md) の「Agent・モデルの共通設定」にある Pullfrog の例外に従う。コピー元の値をそのまま継承せず、effort は Pullfrog の受け付ける形式へ変換する
   - `review.re-review`: private → `'false'`（Actions の消費を抑えるため、追加コミットのレビューは必要なときに `@pullfrog` で依頼する）/ public → `'true'`。初回の自動レビュー（`review.mode='agent'`）と手動依頼（`mention.enabled='true'`）は両方で有効にする。個別設定の正本とレビュー方針を生成済みの `AGENTS.md` にも簡潔に記載する
   - playground repo → `enabled=false`、かつ `hooks.setup` は `pf_unset` 側に回す
   - `pf_unset instructions` はそのまま残す — repo で instructions を set すると org 共通 instructions（日本語返答・P0–P3 ラベル）を置換する。org scope の SSOT は dotfiles の `.github/pullfrog.org.config.sh` で、新規 repo 側で org 設定を触る必要はない
3. **適用**: `.github/pullfrog.config.sh` を実行して backend に反映（gh auth 前提。BYOK の `OPENCODE_API_KEY` は org scope で継承されるので repo 側の secret 作業は不要）
4. **動作確認**: console の Verify workflow + 何か PR を1本切って `pullfrog` check と review が降りるか見る。private repo で check が一切降りないときは、app・config の前に GitHub Actions の billing を疑う — Actions minutes が使えない private repo では workflow 自体が走らず、Pullfrog は起動しない（run も error も残らない）。`gh api users/<owner>/settings/billing/usage`（org なら `orgs/<org>/settings/billing/usage`）や Actions タブの billing warning で確認する — billing endpoint は token の `user` scope が要るので、`gh` が権不足で 404 を返すときは Actions タブの warning を見る
5. commit & push

モデル選択は [delegate](../../delegate/SKILL.md) の共通設定に従う。Pullfrog の設定方法・runner の制約は `wwwyo/me` の wiki（`wiki/tech/pullfrog.md`）を参照する。
