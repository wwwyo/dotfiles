# Claude Code

`home/dot_claude/settings.json` → `~/.claude/settings.json`（chezmoi symlink — repo 編集が即反映、Claude の書き戻しも repo に流れるため non-template 化している）。JSON にコメントが書けないので、非自明な設定値の理由をここに残す。

## `env.CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH = "1"`

subagent の入れ子を禁止する。`1` は「main conversation の下に subagent 1 層まで」の意味で、その層はさらに spawn できない。

委譲した subagent が自分でさらに subagent を立て、存在しない相手と「調整」しようとして数分〜十数分 stall する事故が繰り返し起きていた。prompt で毎回「再委譲しない」と書くより、spawn できない状態にするほうが強い。並列化が要るときは親が複数 spawn する（分割は親の責任）。

実測: 未設定では subagent に Agent ツールが渡り孫 subagent の spawn が成功する。`1` を設定すると subagent のツール一覧から Agent が消え、ToolSearch でも出てこない。

個別の agent だけ止めたいときは、その定義の `tools` から `Agent` を外すか `disallowedTools` に入れる。

## `sandbox`

### `network.allowUnixSockets`

- macOS の seatbelt profile では `(allow network-bind/network-outbound (local unix-socket (subpath ...)))` に展開される。**`subpath` なので値はディレクトリを書く**。末尾に `/*` を付けると subpath として一致せず、その entry は事実上無効になる
- `/var/run` は ssh-agent のため。commit の SSH 署名（`gpg.format = ssh`、鍵は passphrase 付き）は agent 経由で秘密鍵を使うが、macOS 標準の agent socket は `/var/run/com.apple.launchd.<ランダム>/Listeners` でログインごとにパスが変わり、個別には固定できない。`git` 単体は `excludedCommands` で sandbox 外だが、`cd ... && git commit` のように他コマンドと連結すると sandbox 内で走り署名に失敗するので、親ディレクトリごと許可している
  - この許可は「socket file への sandbox アクセス」側だけを解決する。`SSH_AUTH_SOCK` 自体を持たない spawn 環境（tool の exec 等）では socket には届いても agent に接続できず署名が落ちる。そちらは `gpg.ssh.program = ~/.config/git/bin/ssh-sign`（`home/dot_config/git/bin/`）が署名時に `launchctl getenv` から復帰させる — 失敗が2系統あるので混同しない
- OS 差分は `.tmpl` 分岐ではなく**和集合**で持つ（Claude の書き戻しを symlink で repo に流すため非 template 化）。`allowMachLookup` は darwin 専用 key で linux では無視される。`/var/run` は linux で不要だが残している: linux の sandbox は bubblewrap で `allowUnixSockets` の path list を評価せず、unix socket の blocking は seccomp が全有/全無で決めるため（実害なし）。逆に settings.local.json で配列を絞る手はない — settings file 間で配列は置換でなく併合される
