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

- **`devin plugins install` は repo から snapshot を fetch する**。repo への push は
  install 済み copy に届かず、反映には `devin plugins update` が要る。plugin 開発の
  loop は `devin plugins install --local ./<dir>` — machine 限定で folder を live
  link し、edit は次の session に即効する。install は user level の personal
  manifest に記録され、login した全マシンと cloud session の skill/rule/MCP に
  届くが、hooks と custom subagent は local session（CLI / Devin Desktop）でしか
  発火しない。hook は best-effort / fail-open で、load・実行に失敗しても
  session は続く — guardrail には当てにできない
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
- **plugin source の形式**: repo 内の subfolder は `owner/repo#plugins/<dir>` の
  `#` 記法で指す。install 前に提供物 preview（skill/hook/policy）が出て `-y` で
  skip 可。remote install は repo の default branch を fetch するため `plugins/`
  が main に無い間（PR 未 merge 等）は remote 経由では install できない —
  merge 前の検証は `--local` で済ませる

## native evidence で実 model・turn・停止を区別する

2026-10-09、CLI 3000.11.3 の native ATIF-v1.7 と `sessions.db` を読み取りで確認した。狭い取得と復旧操作は [delegate の実行・継続手順](../../delegate/references/devin.md#orca-で起動継続を確認する) に置く。schema は undocumented なので版が変われば必要欄だけを確認する。秘密や会話を含む file の生 dump はしない。

- ATIF の `agent.model_name` は表示名、`steps[].model_name` / `steps[].extra.generation_model` は step の実 UID を記録する。Orca の `unsupported` は native evidence が無いことを意味しない。user step の後の agent step で開始を確認できるが、成功終了や現在の process 状態は示さない。
- transcript は常に稼働中の最新 turn を反映するとは限らない。初見 Max worker は DB 登録/生成が進んでも transcript が未作成だった。CLI help は `--export [PATH]` を after each turn の export と記載するが、自動 transcript の作成条件・保持期間や明示 export の形式/障害時更新は未検証。不在/mtime 停滞だけで停止・model 不適用と扱わない。
- 稼働中の補助根拠は `sessions.db` を SQLite URI `mode=ro` で開き、session ID を bind して `message_nodes.chat_message` の必要 metadata だけを抽出する。`sessions.model` は Max worker で空文字だったため実行 model の根拠にしない。assistant の `metadata.generation_model` / `started_generation_at`、実 user input の `metadata.is_user_input` / `created_at` を使う。
- DB は chain 再記録で同じ `message_id` が複数 row に載る。`row_id` と DB row の `created_at` は過去会話の再記録でも進むため turn watermark にしない。全 row から `message_id` で重複を除き、同 ID の最新 metadata を使い、生成/入力の metadata 時刻で増分を見る。`generation_model=compactor` は主 worker の model 変更として数えない。
- CLI log は `~/.local/share/devin/cli/logs/`。対象 session と時刻を確認し、logger・event・HTTP status・EOF・retry 回数だけを取る。exec の command/会話が error 文を引用するため、単純な `rg error` の件数は通信失敗数ではない。

この日の Medium worker は Connect HTTP 応答本文の `unexpected EOF during chunk size line` (`is_timeout=false`, `is_decode=true`) が繰り返され、`affogato::agent::control_loop` が `attempts=3` で2回 turn 停止。途中に `inference::retry` の HTTP 502、ACP に unavailable / retryable=true の応答があり、同 session の次 user/agent steps で継続を確認できた。これが示すのは推論 transport の失敗と CLI retry 枯渇であり、認証失敗・context 超過・モデル能力不足の証拠ではない。サーバー/中継/ローカル回線のどこが切断したかは未特定。認証/doctor 成功と持続的な推論接続の健全性は分ける。
