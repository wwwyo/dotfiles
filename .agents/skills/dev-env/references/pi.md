# pi の設定と落とし穴

`pi --help` と [docs](https://pi.dev/) で分かることは書かない。実測で判明し、間違えると壊れるものだけを残す。

## 構成

設定は dotfiles の `home/dot_pi/agent/` から chezmoi で配置する。通常の設定は file 単位 symlink、settings.json・sandbox.json は local 側の状態を残す実ファイル（template 合成）。

| パス | 中身 |
| --- | --- |
| `.pi/agent/settings.json` | `home/.chezmoitemplates/pi-settings-base.json`（skills パス・`enabledModels`・`extensions`・`packages` の正本）を `private_settings.json.tmpl` が `~` 側の file と合成する。TUI が書き戻す `defaultProvider`/`defaultModel`/`defaultThinkingLevel`/`theme`/`lastChangelogVersion` は local の値を残す — それ以外を TUI や `pi install` から変えても apply で base 値に巻き戻るので、恒久的な変更は base を編集する |
| `.pi/agent/models.json` | openrouter の `data_collection: "deny"` compat + pi catalog 未掲載モデルの先行定義（現 `opencode-go` の `claude-haiku-5-5`。built-in に merge されるだけで provider 定義は壊れない） |
| `home/.chezmoitemplates/pi-sandbox-base.json` | sandbox の共通設定（後述「Orca socket」）。個別の読み取り許可は `~/.pi/agent/sandbox.json` だけで管理 |
| `.pi/agent/extensions/` | TypeScript extension 置き場（現在は空） |
| `~/.pi/agent/AGENTS.md` | `.codex/AGENTS.md` への symlink。global 指示として効く |

skill は `settings.json` の `"skills": ["~/.claude/skills"]` 一本で読ませ、`~/.pi/agent/skills/` は置かない。個別 symlink 方式だと `.agents` 側で skill を消しても pi 側が残り、stale symlink が溜まる（実際に6個溜まっていた）。

`SYSTEM.md` でシステムプロンプトを置換、`APPEND_SYSTEM.md` で追記できる（プロジェクト単位）。現在は未使用。

## 落とし穴

- CI などで隔離起動するときは、`PI_CODING_AGENT_DIR` を新しい一時 directory に向ける。この変数は既定の `~/.pi/agent` を置き換えるため、user の settings・auth・model 定義も引き継がない。必要な `models.json` だけを信頼済み revision から置き、認証は env で渡す。`--no-session` は session 保存、`--no-context-files` は AGENTS/CLAUDE、`--no-skills`・`--no-extensions`・`--no-prompt-templates` は各自動 discovery を止める（extension の明示 `-e` 指定は別）。`--no-approve` は project-local file を無視する指定で、tool call の許可・拒否 gate ではない。これらは sandbox の代わりにはならず、出力の検査と書込み権限の分離は呼び出し側で行う。

- `--no-tools` を付けると skill が読み込まれない。pi の skill は read tool で SKILL.md を開く仕組みなので、tools を切ると skill 機能ごと死ぬ。`--no-skills` と同じ結果になるため「skill が効いていない」と誤診しやすい。skill の検証は必ず tools を有効にして行う

- `models.json` で組み込み provider を再定義しない。`api` は provider 単位の設定なので、`opencode-go` を `api: "openai-completions"` として定義し直すと、本来 `/messages` を使う `claude-haiku-5-5` まで巻き込んで壊れる。DeepSeek 系も tool calling が壊れ、独自トークン形式が生テキストで漏れる。組み込み provider は `OPENCODE_API_KEY` を読み、モデルごとに正しい `api` を持っているので自前定義は不要。一方、`api`/`baseUrl`/`models` を書かず `compat` だけ書く部分定義は built-in と merge されるので安全 — openrouter の `compat.openRouterRouting.data_collection: "deny"`（`.pi/agent/models.json`）はこの形で入っている

- opencode の Zen と Go は別 catalog。運用は `opencode-go`（Go サブスク枠、`zen/go/v1`）のみ — Zen 側（`opencode` provider、`zen/v1`）は従量課金なので使わない。**pi の catalog は `zen/go/v1/models` の実態より遅れる** — Go endpoint で生きている model（`/responses`・`/chat/completions`・`/messages` で 200）が pi catalog 未掲載なら `models.json` の `models` で先行定義する（現在 `claude-haiku-5-5`）。catalog に降りたら消す — 残すと自前の推測値が公式定義を上書きし続ける。`enabledModels` だけの先行登録は no-match warning が出るだけで有効化されない。`zen/go/v1/models` に未掲載でも実際の endpoint では使える場合がある（Haiku 5.5 の `/messages` で確認済み）。Go catalog の model でも workspace の Privacy 設定で「train on request data」を許可しないと 400 になる（`muse-spark-1.3-contributor` 等）

- `auth.json`（machine 固有、link 対象外）の credential は env の `OPENCODE_API_KEY` より優先される。平文ではなく `"key": "!..."` の command credential を置く（pi は `!` 始まりの値を shell 実行して stdout を key にする）。中身は `MISE_AGE_KEY` で `mise x -- printenv OPENCODE_API_KEY` を返す一行 — 解決値が mise の SSOT と同じなので rotate しても env と不整合にならず、env に key が無い非対話 spawn（Orca daemon・`env -i`・pi-acp）でも動く。`/login` で生 key が書き戻されたら同じコマンド形式に戻す

- `~/.pi/agent` の管理ファイルは `home/dot_pi/agent/` 配下の chezmoi file 単位 symlink（`auth.json`・`sessions`・`models-store.json` 等は machine 固有の実ファイル）。settings.json は symlink だと pi の TUI 書き戻しが repo 正本を汚して PR diff に乗るため、合成する実ファイルにしている（上の表）。新しい設定ファイルは `home/dot_pi/agent/` に足して `chezmoi apply` しないと live に効かない

- `settings.json` の `extensions` にある `-builtin:mcp` は、pi v1 の built-in `mcp` extension が package の `pi-mcp-adapter` と `/mcp` 登録で衝突するのを避けるための無効化指定 — adapter 側を使うので builtin は消している。extension 周りで衝突警告が出たらこの行が残っているかを確認する

- Haiku 5.5 の先行定義は model 単位で `api: "anthropic-messages"` と `baseUrl: "https://opencode.ai/zen/go"` を指定する（SDK が `/v1/messages` を足すため `/v1` は付けない）。`compat.forceAdaptiveThinking: true` がないと pi は旧形式の thinking budget を送り 400 になる。`compat.supportsTemperature: false` で非対応の temperature を省く。組み込み provider が `x-opencode-session` を付けるため、provider 全体の再定義は不要。

- `models.json` の `models` は built-in provider に id 単位で upsert merge される（新規 id は追加、既存 id は自前定義で置換）。model-level の `api` が必須 — 迷ったら対象 endpoint の `/responses`・`/chat/completions`・`/messages` で 200 が返る形式を確認する

- `enabledModels` には provider prefix を付ける。モデル ID だけ書くと部分一致で別 provider にまで広がる（`deepseek-v4.1-flash` が openrouter の `deepseek/deepseek-v4.1-flash` にもマッチする）。さらに pi は TUI での選択を `defaultProvider` ごと settings.json に書き戻すため、Ctrl+P で循環しただけで課金先が黙って変わる。`opencode-go/deepseek-v4.1-flash` のように書く

- skill の取得・更新・削除は `skillctrl` で行う。正本は `.agents/skills/` で、pi は同じディレクトリを native discovery する。pi 専用のコピーや symlink は作らない

## `sandbox.json` の Orca socket 許可

- 現在 `enabled: false` — ユーザー指示で恒久無効化している。設定不調で「直す」ために勝手に再有効化しない
- sandbox.json の変更反映に再起動は不要 — `/sandbox-enable` で extension が config を読み直す。enable は `enabled: false` を無視する session 単位の override なので、恒久無効の運用では `/sandbox-enable` → `/sandbox-disable` で戻して終わる。再起動をユーザーに頼む前にこちらを試す
- sandbox は `settings.json` の `packages` に登録した `pi-sandbox` extension が提供する。`--no-sandbox` もこの extension の引数であり、pi 本体の flag ではない。extension を読み込まない隔離起動では同じ引数を付けても解除の証明にならない。読み込み状況は `pi list`、引数の提供は `pi --help` の Extension CLI Flags で確認する
- sandbox 内から git の SSH 署名を通すには、`~/.ssh` を `filesystem.denyRead` の対象外に保ち（公開鍵を読む必要がある）、SSH agent socket の親 dir を `network.allowUnixSockets` に許可する。denyRead の private key は `**/id_rsa`・`**/id_ed25519` のみ — `id_ecdsa` 等の別名鍵は個別に追加する（`**/id_*` に広げると `id_*.pub` まで読めなくなる）。socket に届く code は確認なしの loaded key で署名・認証を要求できるので、untrusted code には socket 自体を許可しない。署名失敗は「pubkey が読めるか」「`ssh-add -l` が通るか」で層を切り分ける（`launchctl getenv SSH_AUTH_SOCK` が空なのは launchd 未登録環境では正常）
- Orca CLI は `~/Library/Application Support/orca/orca-runtime.json` から Unix socket endpoint を読み、現在は `o-<pid>-<suffix>.sock` に接続する。macOS の sandbox runtime は Unix socket を既定で遮断するため、`network.allowUnixSockets` に親 directory を許可する。workspace の `allowWrite` は socket 接続を許可しない
- `allowAllUnixSockets` は全 socket を開くため使わない。endpoint 名は runtime ごとに変わるので Orca の Application Support directory に絞って許可する。runtime は `~` を展開し、macOS では `subpath` で bind/connect の両方を許可するため、値に `/*` は付けない
- `allowBrowserProcess` は Electron RunAsNode の `task_name_for_pid` 診断を消すために有効化している。これは単なるログ抑制ではなく、`mach*`・全 process-info・広い IOKit・共有メモリを許可する強い緩和。ユーザーが明示的に許可した

## 関連

- モデル選択の方針は [delegate](../../delegate/SKILL.md) の「Agent・モデルの共通設定」が正本。ここには provider の設定・API の互換性だけを書く
- key は mise + age 管理。[[secret-env]] を参照
