# pi の設定と落とし穴

`pi --help` と [docs](https://pi.dev/) で分かることは書かない。実測で判明し、間違えると壊れるものだけを残す。

## 構成

設定は dotfiles の `home/dot_pi/agent/` から chezmoi で配置する。通常の設定は file 単位 symlink、settings.json は local 側の状態を残す実ファイル（template 合成）。


| パス                                            | 中身                                                                                                                                                                                                                                                                                                                                                |
| --------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `.pi/agent/settings.json`                     | `home/.chezmoitemplates/pi-settings-base.json`（skills パス・`enabledModels`・`extensions`・`packages` の正本）を `private_settings.json.tmpl` が `~` 側の file と合成する。TUI が書き戻す `defaultProvider`/`defaultModel`/`defaultThinkingLevel`/`theme`/`lastChangelogVersion` は local の値を残す — それ以外を TUI や `pi install` から変えても apply で base 値に巻き戻るので、恒久的な変更は base を編集する |
| `.pi/agent/models.json`                       | openrouter の `data_collection: "deny"` compat（`compat` だけの部分定義は built-in と merge されて安全）と、pi catalog 未掲載の opencode-go model の先行定義。catalog に載ったら先行定義は削除する                                                                                                                                                                                                    |
| `.pi/agent/extensions/`                       | TypeScript extension 置き場（現在は空）                                                                                                                                                                                                                                                                                                                    |
| `~/.pi/agent/AGENTS.md`                       | `.codex/AGENTS.md` への symlink。global 指示として効く                                                                                                                                                                                                                                                                                                      |


skill は `settings.json` の `"skills": ["~/.claude/skills"]` 一本で読ませ、`~/.pi/agent/skills/` は置かない。個別 symlink 方式だと `.agents` 側で skill を消しても pi 側が残り、stale symlink が溜まる（実際に6個溜まっていた）。

`SYSTEM.md` でシステムプロンプトを置換、`APPEND_SYSTEM.md` で追記できる（プロジェクト単位）。現在は未使用。

## 落とし穴

- CI などで隔離起動するときは、`PI_CODING_AGENT_DIR` を新しい一時 directory に向ける。この変数は既定の `~/.pi/agent` を置き換えるため、user の settings・auth・model 定義も引き継がない。必要な `models.json` だけを信頼済み revision から置き、認証は env で渡す。`--no-session` は session 保存、`--no-context-files` は AGENTS/CLAUDE、`--no-skills`・`--no-extensions`・`--no-prompt-templates` は各自動 discovery を止める（extension の明示 `-e` 指定は別）。`--no-approve` は project-local file を無視する指定で、tool call の許可・拒否 gate ではない。これらは sandbox の代わりにはならず、出力の検査と書込み権限の分離は呼び出し側で行う。
- `--no-tools` を付けると skill が読み込まれない。pi の skill は read tool で SKILL.md を開く仕組みなので、tools を切ると skill 機能ごと死ぬ。`--no-skills` と同じ結果になるため「skill が効いていない」と誤診しやすい。skill の検証は必ず tools を有効にして行う
- `models.json` で組み込み provider を再定義しない。`api` は provider 単位の設定なので、`opencode-go` を `api: "openai-completions"` として定義し直すと、本来 `/messages` を使う anthropic-messages 系 model まで巻き込んで壊れる。組み込み provider は `OPENCODE_API_KEY` を読み、モデルごとに正しい `api` を持っているので自前定義は不要。`opencode-go/deepseek-v4.1-flash` の tool calling・画像入力は組み込み定義のまま通る。
- opencode の Zen と Go は別 catalog。運用は `opencode-go`（Go サブスク枠、`zen/go/v1`）のみ — Zen 側（`opencode` provider、`zen/v1`）は従量課金なので使わない。**pi の catalog は `zen/go/v1/models` の実態より遅れる** — Go endpoint で生きている model（`/responses`・`/chat/completions`・`/messages` で 200）が pi catalog 未掲載なら `models.json` の `models` で先行定義する。`enabledModels` だけの先行登録は no-match warning が出るだけで有効化されない。`zen/go/v1/models` に未掲載でも実際の endpoint では使える場合がある。Go catalog の model でも workspace の Privacy 設定で「train on request data」を許可しないと 400 になる（`muse-spark-1.3-contributor` 等）
- Go privacy 表は既定モデル選定の前提。MiMo-V2.6-Flash は学習不使用・data retention 0 days、DeepSeek V4.1 Flash も同じ値で ZDR は**月次更新の契約**。どちらの 0 days でも Go 経由の実際の推論 provider・処理地域は非公開なので、非学習を中国外での処理の保証として扱わない

- **既定モデルの切替先は3経路**。`home/.chezmoitemplates/pi-settings-base.json` の `defaultModel`（新規マシン・apply 後の正本）、delegate の役割テーブル（起動時の明示指定。`pr_triage.py` はこの表を parse して worker の起動モデルを決めるので table が SSOT）、Orca Settings → Agents の launcher args（GUI 起動・手動更新。command は shim を単体で置き `x -- pi` を入れない — 理由は [orca](orca.md) の launcher の落とし穴）。**既存マシンは `private_settings.json.tmpl` の合成で local の `defaultModel` が base を上書きするため、`chezmoi apply` だけでは既定が切り替わらない** — TUI でモデルを選ぶ（settings.json に書き戻される）か `~/.pi/agent/settings.json` を直接更新する。launcher args・稼働中の reuse session も設定変更では切り替わらないので個別に確認する

- Go サブスクで使えるかは catalog 掲載ではなく endpoint が決める — catalog 未掲載でも生きている model がある一方、`claude-sonnet-*`/`claude-opus-*` 系は endpoint が `Model is unavailable` で拒否するので `enabledModels` に足しても動かない。`enabledModels` に Anthropic の上位 model が並ばないのは漏れではなくこの境界のため。upstream が枠から model を消す例は [delegate](../../delegate/SKILL.md) に集約する
- prompt editor の Vim mode は `@wwwyo/pi-vim` package（base の `packages` に `npm:@wwwyo/pi-vim@0.14.2` で exact pin）が提供する。設定 flag ではないので、vim モードが効かなくなったら `packages` 行が残っているかを見る。pin を緩めると後方互換のない更新がそのまま入る。upstream は unscoped の `pi-vim`（github.com/lajarre/pi-vim）で、`@wwwyo/pi-vim` は同じ source を自 scope に publish したもの — 名前は違うが中身は同一なので、`pi list` でどちらの名前が入っているかを見る（旧 pin の `pi-vim` を指す状態では自 scope 側の publish に切り替わらない）
- `packages` の `npm:pi-subagents` は **0.75.0 以上が必須**（現 pin `@0.83.0`、base の `packages` が正本）。Pi 1.0.0 で `@earendil-works/pi-agent-core` の `./node` subpath が消え、0.74.0 以前の background child は `Background children require the host npm package ... does not provide @earendil-works/pi-agent-core/node` で**全件起動失敗**する（0.75.0 が「host が宣言しない subpath の alias は作らない」optional 化で修正）。親の `subagent` 自体は成功し child だけが即死するので、pin を戻すと batch が静かに全滅する。切り分けは package の `resolveHostPeerAliases(<pi package root>)` を node で直接呼び `missing` が空かを見る（0.72.0 は 1 件）。package 更新は稼働中の pi に反映されない — 再起動か `/reload` が要る。**`/new` では反映されない**: `/reload` は process 内の extension factory cache を捨てて package を再解決・再 install するが、`/new` は session とサービスを作り直すだけで cache を破棄せず、同じ path の旧 factory を使い回す。**`subagent` tool は最初から見えるとは限らない** — 0.74.0 以降は model が tool を途中追加できるかで変わり（既定の DeepSeek V4.1 Flash は最初から `subagent` が見えるので `subagents_enable` は出ない。見えない model では `subagents_enable` で有効化）、config の `toolActivation`（既定 `auto`）で固定できる。skill や batch の手順に `subagents_enable` を前提で書かない
- **0.77.0 は pi 1.x で background child 全滅**（`... does not provide @earendil-works/chord, @earendil-works/chord/context`）。`runner-aliases.js` の pre-chord 判定が `^0\.(\d+)\.\d+$` の決め打ちで、host version `1.3.0` が「chord 必須期」と誤判定され、chord を同梱しない pi 1.2.0+ で必ず missing になる。**0.78.0 が host manifest の `dependencies` を見る方式に修正**。同期（`async: false`）はこの alias map を使わないので通る — async だけ落ちる症状はこの bug を疑う
- **`npm update` / `npm install` を `~/.pi/agent/npm` で直接叩かない**。peer の host package（`@earendil-works/pi-coding-agent@0.80.10` 等）を物理導入して extension の module mapping を壊し、`extraneous` も生える（`npm audit` の指摘が増えるのはこの混入が主）。pi の installer は peer を抑制するので、掃除は `node_modules` と `package-lock.json` を消して `pi install` で再構築する。`pi update --extensions` は settings の pin 変更を反映しない（`Updated packages` と出ても何も変わらない）— pin を上げたら `pi install npm:<pkg>@<version>` で reconcile する
- `pi-subagents` の 0.65.1–0.81.0 は undici advisory を抱える（0.82.0 で undici 8.12.3）。security 修正なので cooldown を待たずに上げてよい区分。
- `auth.json`（machine 固有、link 対象外）の credential は env の `OPENCODE_API_KEY` より優先される。平文ではなく `"key": "!..."` の command credential を置く（pi は `!` 始まりの値を shell 実行して stdout を key にする）。中身は `MISE_AGE_KEY` で `mise x -- printenv OPENCODE_API_KEY` を返す一行 — 解決値が mise の SSOT と同じなので rotate しても env と不整合にならず、env に key が無い非対話 spawn（Orca daemon・`env -i`・pi-acp）でも動く。`/login` で生 key が書き戻されたら同じコマンド形式に戻す
- `~/.pi/agent` の管理ファイルは `home/dot_pi/agent/` 配下の chezmoi file 単位 symlink（`auth.json`・`sessions`・`models-store.json` 等は machine 固有の実ファイル）。settings.json は symlink だと pi の TUI 書き戻しが repo 正本を汚して PR diff に乗るため、合成する実ファイルにしている（上の表）。新しい設定ファイルは `home/dot_pi/agent/` に足して `chezmoi apply` しないと live に効かない
- MCP は pi v1 の built-in `mcp` extension を使う（third-party の `pi-mcp-adapter` package は 2026-10 に削除した）。server 定義は `~/.pi/agent/mcp.json` で、chezmoi の正本は `home/dot_pi/agent/mcp.json`。`~/.agents/mcp.json` は同じ file への相対 symlink で、MCP 設定の generic な置き場として残している（adapter は `~/.agents/mcp.json` を import していた — 別 client も同じ置き場を読む）
- built-in `mcp` を使うので `settings.json` の `extensions` に `-builtin:mcp` を**入れない**。この行が残っていると MCP ごと無効になる（adapter 時代の名残）。server の確認は `pi mcp list`、追加・変更は `pi mcp add` / `~/.pi/agent/mcp.json` への直接 edit → `/reload`
- anthropic-messages 系 model を先行定義する場合（旧 `claude-haiku-5-5` の実測）: model 単位で `api: "anthropic-messages"` と `baseUrl: "https://opencode.ai/zen/go"` を指定する（SDK が `/v1/messages` を足すため `/v1` は付けない）。`compat.forceAdaptiveThinking: true` がないと pi は旧形式の thinking budget を送り 400 になる。`compat.supportsTemperature: false` で非対応の temperature を省く。組み込み provider が `x-opencode-session` を付けるため、provider 全体の再定義は不要。
- `models.json` の `models` は built-in provider に id 単位で upsert merge される（新規 id は追加、既存 id は自前定義で置換）。model-level の `api` が必須 — 迷ったら対象 endpoint の `/responses`・`/chat/completions`・`/messages` で 200 が返る形式を確認する。curl で直接叩く確認は `x-opencode-session` header が無いと `MissingSessionID` で弾かれる（pi 経由では付く）
- `enabledModels` には provider prefix を付ける。モデル ID だけ書くと部分一致で別 provider にまで広がる（`deepseek-v4.1-flash` が openrouter の `deepseek/deepseek-v4.1-flash` にもマッチする）。さらに pi は TUI での選択を `defaultProvider` ごと settings.json に書き戻すため、Ctrl+P で循環しただけで課金先が黙って変わる。`opencode-go/deepseek-v4.1-flash` のように書く
- skill の取得・更新・削除は `skillctrl` で行う。正本は `.agents/skills/` で、pi は同じディレクトリを native discovery する。pi 専用のコピーや symlink は作らない

## sandbox は使っていない（`pi-sandbox` を外した）

2026-10-27 に `pi-sandbox` package と `~/.pi/agent/sandbox.json`・chezmoi 側の template を削除した。理由:

- 以前から `enabled: false` で恒久無効運用だった（設定不調で「直す」ために勝手に再有効化しない、という指示は維持）
- 有効化していなくても extension は import される。依存の `@carderne/sandbox-runtime` は Anthropic の `srt` の**個人フォーク**（維持者 1 人・上流から 285 commit 遅れ・`.git` の hooks/config 保護を外す patch 入り）で、`zod < 4.6.6` の HIGH advisory を抱える。上流 0.0.81 も `zod ^3.25.0` のままで、version up では消えない（必要なら sandbox-runtime 側の zod 4 移行を待つ）

再導入するときの前提（外す前に実測した事実）:

- **config を置かないと `enabled: true` になる**（`DEFAULT_CONFIG.enabled = true`）。無効で使うなら `{"enabled": false}` を必ず置く
- **既存環境の移行**: base から外しただけでは `~/.pi/agent/npm` に `pi-sandbox` と依存（`@carderne/sandbox-runtime` など）が残ることがある（pi の install は追加・更新しかしない）。取り込み後に `pi list` と `cd ~/.pi/agent/npm && npm audit` を見て、残っていれば `npm uninstall pi-sandbox --prefix ~/.pi/agent/npm` で消す（完了後は 2 package・0 件になる）
- **Orca の launcher args は chezmoi も `sync_automations.py` も更新しない**（live の GUI profile state に保存される）。既存環境では Settings → Agents を開き、pi の args から `--no-sandbox` を削除して保存する。残すと `Error: Unknown option: --no-sandbox` で pi が起動しない
- `--no-sandbox` は extension が提供する引数で、pi 本体の flag ではない。付けたまま extension を外すと `Error: Unknown option: --no-sandbox` で**起動しない**（delegate・session-consolidate・pr_triage の起動 command からも消した）
- sandbox-init 時に `rg` を要求する（無いと `Sandbox dependencies not available: ripgrep (rg) not found`）
- Orca CLI を sandbox 内から使うには `network.allowUnixSockets` に `~/Library/Application Support/orca` を許可する（Orca は `orca-runtime.json` の `o-<pid>-<suffix>.sock` に接続する）。`allowAllUnixSockets` は使わない
- git の SSH 署名を通すには `~/.ssh` を `filesystem.denyRead` の対象外にし、ssh-agent socket の親 dir を許可する（private key は `**/id_rsa`・`**/id_ed25519` のみ deny）
- `allowBrowserProcess` は Electron の `task_name_for_pid` 診断を消す代わりに `mach*`・全 process-info・IOKit・共有メモリを開ける強い緩和なので、必要性を確認してから入れる

## 関連

- モデル選択の方針は [delegate](../../delegate/SKILL.md) の「Agent・モデルの共通設定」が正本。ここには provider の設定・API の互換性だけを書く
- key は mise + age 管理。[[secret-env]] を参照