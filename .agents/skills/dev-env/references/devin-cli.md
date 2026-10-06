# Devin CLI

CLI 本体の install/upgrade は brew cask（`scripts/Brewfile` の `cask "devin-cli"`、version pin 無しで `brew upgrade` 追従）。この repo が管理するのは設定だけ。

`home/dot_config/devin/` の `private_config.json.tmpl`（permissions・sandbox・hooks）、`mcp_config.json.tmpl`、`AGENTS.md` を `~/.config/devin/` へ配置している（file は chezmoi symlink、`.tmpl` は実ファイル）。`AGENTS.md` は `.codex/AGENTS.md` と同内容だが**実体を分けている**（規約が分かれたとき片方だけ直せるように）。

- **rule の読み込み**: `AGENTS.md` と `CLAUDE.md` を独立に読み、両方あれば両方注入される
  （`read @AGENTS.md` のような参照記法は展開されない）。global rule は
  `~/.config/devin/AGENTS.md` だけが読まれ、`~/AGENTS.md`・`~/.agents/AGENTS.md` は読まれない
- **`read_config_from.claude: false`**。止める範囲は `CLAUDE.md` だけでなく `.claude/skills/`・
  commands・settings の hooks・`~/.claude.json` の MCP・`.claude/rules/` まで全て。`.claude` に
  skill/hook/rule を足したら Devin 側にも同じ手当てが要る（rule は `~/.devin/rules/` か
  `.config/devin/AGENTS.md` へ）
- **置き場**: skills・project subagent・project rule は中立パス（`.agents/`・`AGENTS.md`）で
  完結。global rule・global subagent・hooks・MCP は `~/.config/devin/`（= `home/dot_config/devin/`）以下にしか置けない
- **`config.json` は `private_config.json.tmpl` で実ファイル化している**。CLI が model 切り替え・権限承認・
  トグルのたびに書き戻し、symlink だと repo source が汚れて diff が出続けるため。管理の分け方:
  - **local が正**（描画時に `jq` でローカル file から引き継ぐ）: `agent`・`devin`・`shell`・
    `theme_mode`/`show_*`/`auto_update` 等の scalar pref。承認・切り替えは apply で巻き戻らないし
    repo に diff も出ない
  - **union**（`local ∪ template | unique`）: `permissions.allow`・`sandbox.allowed_domains`。
    session 中の承認済み追記は消えず、repo 側への追加は全マシンに伝播する。repo 側から entry を
    **消しても** local 側に残るので、消したいときは各 local file を編集する
  - **template が正**（apply で必ず効く）: `version`・`read_config_from`・`hooks`・
    `permissions.{deny,ask}`・`sandbox.excluded`。security policy はここで管理する
  local が正の項目を repo 側から変えたいときは local file を直接編集するか、該当 key を消してから
  apply する（fallback が seed になる）。注意: source file を rename/remove すると symlink が
  dangling になり、動作中の CLI が target を `{"version": 1}` の stub 実ファイルで作り直して
  設定が全消えする。source を動かしたら即 `chezmoi apply --force ~/.config/devin/config.json` すること

## CLI 挙動の非自明な点

- **Devin の SessionEnd は transcript を payload で渡さない**（`session_id`・`reason` のみ）。
  Langfuse への送信は `devin-langfuse` plugin（`wwwyo/devin-langfuse-plugin` repo）の
  `plugins/devin-langfuse/hooks/langfuse-export.py` が `~/.local/share/devin/cli/sessions.db` から
  `row_id` 順全件を `message_id` で dedup して組み立てる（parent 辿りは chain 再作成で欠ける）。
  schema は undocumented なので失敗時は静かに exit 0
- **`ACP_BACKEND` が env にあると devin はローカル認証情報を意図的に無視する**。
  IDE/ACP 配下で spawn された shell（agent の exec、IDE 内 terminal 等）には
  `ACP_BACKEND=windsurf` が注入されており、そのまま `devin` を叩くと credentials.toml
  が正しくても `auth status` は "Not logged in"、`-p` は welcome → "Login canceled" で落ちる。
  `env -u ACP_BACKEND` で直る
- **`config.json` の `shell.setup_complete` / `devin.org_id` / `theme_mode` は CLI が
  自動で書き足す欄**。手で消すと welcome 画面が再び出る。schema は undocumented
- **session の transcript は `~/.local/share/devin/cli/transcripts/<session-id>.json`
  に残る**（この環境で観測済み。保持期間や書き出し条件は undocumented）。
  Orca の worktree・terminal scrollback が消えても残るので、「あの session で
  何を話していたか」はこの file を読めば答えられる。session の再開は `devin -r <session-id>`
  （[Devin の実行・診断手順](../../delegate/references/devin.md)を参照）
- **usage メーターは「Sign in with ChatGPT」系のプラン共有とは別系統**。Devin Pro の quota は日次・週次の allowance として計量され（2026-03 に credit 制から移行）、ChatGPT プランはその allowance の付与元に含まれない — 実測でも ChatGPT 側残量と Devin 側残量は別々に動いた。promo モデルは共有対象外の可能性がある — 共有が効かないように見えるときは、週次 quota の残量・promo かどうか・host 側実装の行き渡りを切り分ける
