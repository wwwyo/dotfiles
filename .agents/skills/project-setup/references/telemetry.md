# Langfuse telemetry opt-in

ステップ 2 で Langfuse 収集 yes と答えた場合のみ実施。3 agent 全部をこの repo で有効化する。前提: `LANGFUSE_PUBLIC_KEY` / `SECRET_KEY` / `BASE_URL` が mise の global env に登録済み、かつ各マシンで `claude plugin install langfuse-observability@langfuse-observability`・`codex plugin marketplace add langfuse/codex-observability-plugin && codex plugin add tracing@codex-observability-plugin` 済みであること（詳細は `~/src/github.com/wwwyo/dotfiles/.agents/skills/dev-env/references/langfuse-telemetry.md` — この skill は新規 repo 内で実行されるため絶対 path で書く）。

repo root で次を実行する。script は以下を置く。

```bash
~/.agents/skills/project-setup/tools/setup.sh telemetry
```

- **Claude Code**: `.claude/settings.local.json` で `langfuse-observability@langfuse-observability` を local scope で有効化する（user settings で default off にしてあるので local が優先して反転する。収集は個人設定なので tracked な `settings.json` ではなく gitignored な local に書く）
- **Codex**: `.codex/langfuse.json` に `{"enabled": true}` を書く（plugin が `process.cwd()` で解決する repo opt-in。env 変数は使わない — 子プロセス経由で未 opt-in repo に漏れるため。global gitignore 済みなので commit されない）。**git root ではなく session の cwd を見る**ので、subdir から `codex` を起動すると root の opt-in を拾わず無効のまま。codex は repo root から起動する運用を前提にする（subdir 起動が常態ならその dir にもファイルを置く）
- **pi**: `pi install -l --approve "git:github.com/wwwyo/pi-observability-plugin@v0.2.0"` を実行する（project trust が要る）。`.pi/settings.json` に package が宣言され `.pi/git/` に install される（`npm:` package なら `.pi/npm/`） — 両方 global gitignore 済みなので commit されない。新しいマシン・checkout では同コマンドを再実行する。upstream の `npm:@langfuse/...` ではなく wwwyo fork を使う（codex と同じ `detail: turn` の compact 記録を持ち、tag で pin される）
- **orca.yaml**: 上記の file は全部 gitignore 済みなので worktree には載らない。`scripts.setup` から [sync-local-worktree-files.sh](../tools/sync-local-worktree-files.sh) を呼ぶ `orca.yaml` を repo root に置き、push する（worktree 側 checkout から読まれる）。既に `orca.yaml` があれば script は書かず `orca_yaml: "skipped"` を返すので、既存の `scripts.setup` に手で組み込む

既存 setup コマンドがある repo は `{ [ ! -x ... ] || ...; }; bun install` のように、local 設定のコピーを install より前に置く。コピーに失敗しても依存 install は継続し、同期結果はログとファイルの存在で別途確認する。`setupAgentStartupPolicy=start-immediately` では setup と Agent が並行に起動するため、この順序だけでは Agent 起動前のコピー完了は保証しない。setup 全体の完了待ち（`wait-for-setup`）は必須にしない。

Orca の repo 設定は `orca repo show --repo path:<repo-root> --json` の `result.repo.hookSettings` を確認する。`commandSourcePolicy` が未設定なら local script がある場合は `local-only`、なければ `shared-only` に解決される。明示的な `local-only` では local setup が空でも `orca.yaml` は使われない（[解決規則の詳細](../../dev-env/references/orca.md)）。共有 setup を使う repo は Project Settings → Worktree Hooks の詳細設定で `orca.yaml のみ` を選ぶ。CLI に setter がなければ bundled computer-use で操作し、ユーザーから修正を依頼済みなら改めて許可を求めない。未登録の repo は初回 commit 後に `orca repo add --path <repo-root> --json` で登録し、handoff 前に同じ確認を行う。

完了確認は main のファイル存在だけで終えない。収集対象の新規 Orca worktree で 3 agent の opt-in と `.pi/git/` の install を確認し、実 session の Langfuse 受信を照合する。guard による helper 不在の skip や setup の終了コードだけを成功の根拠にしない。収集を必要としない automation の `--setup skip` は不備として扱わない。実 session の照合はその agent を起動できることが前提 — この workflow でサポートする認証方式で `claude` の実 session を開始できない場合は Claude 分の live 検証を未完として扱い、「検証できなかった agent」を明示して成功扱いにしない。起動できる場合は live 検証を実施する。
