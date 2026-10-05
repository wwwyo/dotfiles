# OpenCode Go での共通セットアップ

通常の導入ではこの reference を先に読む。ほかの reference にある Vercel
Gateway や unpinned な install の例は、この環境の既定ではない。

## CLI とアプリの依存関係

CLI は dotfiles の mise 設定で管理する。`mise x -- e2e guide setup` で
導入済みバージョンの API を確認する。アプリに `e2e` が入っている場合は
そちらを `mise x -- pnpm exec e2e ...` で使い、config の import と版を揃える。
`npx` / `dlx` で未導入の最新版を暗黙に取得しない。

global の版設定が未反映の段階では、導入済みの CLI を
`E2E_TELEMETRY_DISABLED=1 mise x npm:e2e@0.16.0 -- e2e ...` で起動できる。
worktree から chezmoi apply して常用設定を反映しない。

アプリへの導入では既存の package manager と lockfile を使い、Node 22.12+
を確認する。ブラウザ用に `e2e`、`@e2e-dev/web`、`playwright`、`ai`、
`@ai-sdk/openai-compatible` が必要。直接依存は exact に固定し、transitive
も含めて package manager の cooldown 7 日を適用する。pnpm では
`pnpm-workspace.yaml` の `minimumReleaseAge: 10080` を使う。

2026-10-03 の初回導入では、ユーザーがこのセットアップに限り cooldown の
例外を明示したため、以下の exact version を導入した。global の cooldown は
7 日のまま保持し、通常の更新にもこの例外を適用しない。

| Package | Version | 7 日経過（UTC） |
| --- | --- | --- |
| e2e | 0.16.0 | 2026-10-09 17:18:01 |
| @e2e-dev/web | 0.11.2 | 2026-10-09 17:19:08 |
| playwright | 1.63.0 | 経過済み |
| ai | 7.0.127 | 2026-10-08 19:20:24 |
| @ai-sdk/openai-compatible | 3.0.62 | 2026-10-07 22:57:10 |
| zod | 4.6.5 | 経過済み |

この表は固定時点の確認記録。更新時には registry の公開日時と peer dependencies
を確認し、7 日を経過した最新の互換版を選ぶ。

## Provider と config

[config template](../assets/e2e.config.ts) をアプリの root にコピーし、URL を
実際のテスト対象に合わせる。既存の dev server を使う例なので、起動が必要なら
`setup.md` の `app.command` を参照して、その repo のコマンドを指定する。
`init --yes` は Vercel・skill・MCP 登録を既定にするため、そのまま実行しない。
手動で config とテストを追加すればよい。

- API key: `OPENCODE_API_KEY`。mise + age から runner に渡す。config に平文を書かない。
- Base URL: `https://opencode.ai/zen/go/v1`。`/zen/v1` は別の Zen endpoint。
- Model: global miseの`OPENCODE_E2E_MODEL`（現在`mimo-v2.6-flash`）を必須とする。
  同じ chat/completions protocol の
  モデルに変更できる。Responses / Anthropic protocol のモデルは adapter も変更する。
- Client: `wwwyo-e2e/0.1` と `x-opencode-session` を付ける。config の worker
  session 内では同じ ID を使い、別の worker では別の ID を生成する。

2026-10-03 に Go API への実リクエストで MiMo の画像入力・function call・
JSON schema 付き出力を確認した。e2e runner との組み合わせによる実操作は
ローカルのサンプル画面で作成・編集・削除を 2 回実行して確認済み。
初回の `act` はモデル呼び出し 2 回、2 回目は 2 操作を replay して 0 回だった。
`agent.assert` は両方でモデルを 1 回呼び、固定 assertion と cleanup も成功した。
これは導入確認であり、対象アプリの QA やモデル間の比較評価ではない。
e2e は OpenCode Go の公式 validated client 一覧には載っていない。

2026-10-03 の OpenCode Go Privacy 表では MiMo-V2.6-Flash は学習不使用・
data retention 0 days とされている。モデルの開発元は Xiaomi だが、Go 経由の
実際の推論 provider・処理地域は公開資料で確認できていない。学習不使用の記載を
中国外での処理の保証として扱わない。

GUI agent から起動するときは `mise x -- ...` で env を注入する。age の復号には
通常の shell と同じ `MISE_AGE_KEY` が必要。キーが無ければ既存の secret-env 手順で
Keychain から子プロセスに渡し、キーや環境変数一覧を表示しない。

## Telemetry と保存先

初回の CLI 起動前から `E2E_TELEMETRY_DISABLED=1` を渡す。この環境変数は
匿名 telemetry と `e2e feedback` の送信を無効にする。`e2e telemetry disable`
だけでは明示的な feedback 送信までは無効にならない。CI の job env、MCP の
server env にも設定し、自動 feedback 送信は行わない。

- `.e2e/cache/`: 検証済み `agent.act` 操作の replay JSON。標準は repo-local。
- `.e2e/report.json` / `.e2e/artifacts/`: 結果、画像などの証跡。
- cache はローカルで read-write、CI は既定で read-only。CI に持ち越す場合は
  CI cache 等で明示的に共有する。secret や画面データを含む可能性を確認せず commit しない。
- `agent.assert` / `waitFor` / `extract` は毎回モデルを呼ぶ。replay でも assertion は実行する。
- telemetry off でも推論のための画面情報・画像等は OpenCode Go に送られる。
  Vercel Gateway、クラウドブラウザ、外部 reporter はこの template では使わない。

## 導入の確認

アプリのテストは自分のデータを作成 → 操作・検証 → 削除する。失敗時にも cleanup
できるようにし、cleanup の失敗は記録する。再利用するテストアカウントと、実行ごとの
データを分ける。固定値や安定した locator は `screen` + `expect`、判断が必要な
操作は `agent.act`、意味の評価は `agent.assert` にする。

1. `E2E_TELEMETRY_DISABLED=1 mise x -- e2e --version` で runner を確認する。
2. config と 1 本のテストを作り、`E2E_TELEMETRY_DISABLED=1 mise x -- pnpm exec e2e run tests/<feature>.e2e.ts`。
3. 同じテストをもう一度実行し、report の cache / modelCalls と結果を比較する。
4. cleanup と証跡を確認する。CLI だけの成功を対象アプリの QA 完了として報告しない。

公式資料: [OpenCode Go](https://opencode.ai/docs/go/)、
[e2e telemetry](https://e2e.tester.army/docs/telemetry)。
