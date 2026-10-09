# Langfuse telemetry opt-in

ステップ 3 で Langfuse 収集 yes と答えた場合のみ実施。4 agent 全部をこの repo で有効化する。前提: `LANGFUSE_PUBLIC_KEY` / `SECRET_KEY` / `BASE_URL` が mise の global env に登録済み、かつ各マシンで `claude plugin install langfuse-observability@langfuse-observability`・`codex plugin marketplace add langfuse/codex-observability-plugin && codex plugin add tracing@codex-observability-plugin` 済みであること（詳細は `~/src/github.com/wwwyo/dotfiles/.agents/skills/dev-env/references/langfuse-telemetry.md` — この skill は新規 repo 内で実行されるため絶対 path で書く）。

- **Claude Code**: `.claude/settings.local.json` を生成し local scope で plugin を有効化（user settings で default off にしてあるので local が優先して反転する。収集は個人設定なので tracked な `settings.json` ではなく gitignored な local に書く）:
  ```json
  {
    "enabledPlugins": {
      "langfuse-observability@langfuse-observability": true
    }
  }
  ```
- **Codex**: `.codex/langfuse.json` に `{"enabled": true}` を書く（plugin が `process.cwd()` で解決する repo opt-in。env 変数は使わない — 子プロセス経由で未 opt-in repo に漏れるため。global gitignore 済みなので commit されない）。**git root ではなく session の cwd を見る**ので、subdir から `codex` を起動すると root の opt-in を拾わず無効のまま。codex は repo root から起動する運用を前提にする（subdir 起動が常態ならその dir にもファイルを置く）
- **pi**: `pi install -l --approve "npm:@langfuse/pi-observability-plugin@0.1.2"` を実行（project trust が要る）。`.pi/settings.json` に package が宣言され `.pi/npm/` に install される — 両方 global gitignore 済みなので commit されない。新しいマシン・checkout では同コマンドを再実行する:
  ```json
  {
    "packages": ["npm:@langfuse/pi-observability-plugin@0.1.2"]
  }
  ```
- **Devin**: `mise.local.toml`（mise 公式の local override ファイル。global gitignore 済みなのでどの repo でも commit されない）に以下を書く。opt-in は個人設定なので repo の public/private に関わらず tracked な `mise.toml` には入れない（他 3 agent が gitignored な local file に書くのと同じ扱い）。exporter の gate で、codex plugin の gate 変数 `TRACE_TO_LANGFUSE` と意図的に別名 — env を引き継いだ codex が未 opt-in repo で有効化されないようにするため:
  ```toml
  [env]
  DEVIN_TRACE_TO_LANGFUSE = "true"
  ```

  `mise.local.toml` は `mise trust` 対象なので、生成後に `mise trust` で明示的に信頼し、`mise env | grep DEVIN_TRACE` で export を確認する。既存の `mise.local.toml` がある場合は、**既存 `[env]` テーブルの配下にキーを追記する** — 末尾に `[env]` を再掲すると TOML の重複テーブルで parse error になり、その時点でファイル全体が読めなくなる

このステップが置く file は全部 gitignore 済みなので worktree には載らない。repo ルートに `orca.yaml` を生成して push する（worktree 側 checkout から読まれる）:

```yaml
scripts:
  setup: '[ ! -x "$HOME/src/github.com/wwwyo/dotfiles/.agents/skills/project-setup/tools/sync-local-worktree-files.sh" ] || "$HOME/src/github.com/wwwyo/dotfiles/.agents/skills/project-setup/tools/sync-local-worktree-files.sh"'
```

既存 setup コマンドがある repo は `{ [ ! -x ... ] || ...; }; bun install` のように、local 設定のコピーを install より前に置く。コピーに失敗しても依存 install は継続し、同期結果はログとファイルの存在で別途確認する。`setupAgentStartupPolicy=start-immediately` では setup と Agent が並行に起動するため、この順序だけでは Agent 起動前のコピー完了は保証しない。setup 全体の完了待ち（`wait-for-setup`）は必須にしない。

Orca の repo 設定は `orca repo show --repo path:<repo-root> --json` の `result.repo.hookSettings` を確認する。`commandSourcePolicy` が未設定なら local script がある場合は `local-only`、なければ `shared-only` に解決される。明示的な `local-only` では local setup が空でも `orca.yaml` は使われない（[解決規則の詳細](../../dev-env/references/orca.md)）。共有 setup を使う repo は Project Settings → Worktree Hooks の詳細設定で `orca.yaml のみ` を選ぶ。CLI に setter がなければ bundled computer-use で操作し、ユーザーから修正を依頼済みなら改めて許可を求めない。未登録の repo は初回 commit 後に `orca repo add --path <repo-root> --json` で登録し、handoff 前に同じ確認を行う。

完了確認は main のファイル存在だけで終えない。収集対象の新規 Orca worktree で 4 agent の opt-in と `.pi/npm/` の install を確認し、実 session の Langfuse 受信を照合する。guard による helper 不在の skip や setup の終了コードだけを成功の根拠にしない。収集を必要としない automation の `--setup skip` は不備として扱わない。実 session の照合はその agent を起動できることが前提 — `claude` が未ログインの環境では Claude 分の live 検証は成立しないので、「検証できなかった agent」を明示して未完として残す（成功扱いにしない）。
