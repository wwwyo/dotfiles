---
name: delegate
description: "別 agent への委譲・相談・レビューで harness・model・effort と fallback を選び、起動・再開する共通手順。「Codex に聞いて」「pi でやって」や、別 repo・独立したセッションへの Orca 経由の委譲で使う。通常の分担方法は agent の判断に任せる。"
---
# 別 agent の選択と委譲

## Agent・モデルの共通設定

別の agent session（harness）を起動するときは、役割とデータ区分から次の表で選ぶ。ユーザーが agent を指定した場合はその指定に従う。他の skill に個別のモデル選択ルールを持たせない。


| 役割       | public                                                                                        | personal                                                                           | work                                       |
| -------- | --------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------ |
| Operator | 1. codex:gpt-6.1-sol:high, 2. pi:opencode-go/step-5-preview-free:high                                                    | 同じ                                                                                 | 同じ                                         |
| worker   | 1. pi:opencode-go/muse-spark-1.3-contributor:high, 2. pi:opencode-go/step-5-preview-free:high | 1. pi:opencode-go/mimo-v2.6-flash:high, 2. pi:opencode-go/step-5-preview-free:high | 1. pi:opencode-go/step-5-preview-free:high |
| review   | 1. codex:gpt-6.1-sol:high, 2. pi:opencode-go/muse-spark-1.3-contributor:high                  | 1. codex:gpt-6.1-sol:high, 2. pi:opencode-go/mimo-v2.6-flash:high                  | 同左                                         |


- personal / work: 個人の責任範囲で扱うデータ / 仕事として組織・案件の利用条件に従うデータ。
- pi 本体の既定モデルは MiMo v2.6 Flash・high。役割ごとの選択値は起動時に明示し、既定モデルに任せない。
- Operator はデータ区分を問わず Codex を優先し、pi を使う場合は常に Step 5 Preview Free・high を明示する。
- 候補の順序: 先頭優先。使えない場合に次の候補へ fallback する。
- 記法: `harness:model:effort`。選んだ値を起動時に指定する。
- 例外: automation は固定せず task の要件に合わせて選ぶ（実値は各 `automation.toml` の `provider`）。Pullfrog は public なら `opencode-go/muse-spark-1.3-contributor:high`、private なら `opencode-go/mimo-v2.6-flash:high`。プロダクトの LLM モデル（opencode 等）も対象外
- `opencode-go` の free/contributor 枠は upstream が予告なく削除する（`space-bunny-free` 消失で pin 先の pullfrog が全 repo 全滅した実例）。表の候補・自動化側の pin は差し替え前提で選び、消えたら backend の `pullfrog config set` と SSOT の config script を同じ変更で更新する
- 無料・格安枠の「非学習」「ZDR」表記は保証の粒度が違う — 月次更新の契約脚注、学習許可と引換の contributor 枠、保持日数のみの表記、provider 非開示でホスト地を検証できないものがある。personal/work の区分で選ぶときは表記ではなく裏付け（契約期間・学習可否・ホスト）を確認する

## 起動時の権限モード

別 agent session は常に bypass mode で起動する。新規・再開・fallback、対話・非対話のすべてに適用する。Orca の標準ランチャーとコマンドを直接指定する経路で権限が変わると、委譲先だけ承認待ちで止まるため、起動時に揃える。起動モードの指定であり、harness の既存の deny / ask ルールは変更しない。

`terminal create --command` や CLI を直接呼ぶ場合は、モデル・effort とともに次の指定を付ける。


| harness     | bypass の指定                                                                          |
| ----------- | ----------------------------------------------------------------------------------- |
| Codex       | `--dangerously-bypass-approvals-and-sandbox`                                        |
| pi          | `--no-sandbox`（この環境の `pi-sandbox` extension が提供。読み込み確認は [pi の手順](references/pi.md)） |
| Claude Code | `--dangerously-skip-permissions`                                                    |


`worktree create --agent` は Orca の設定済みランチャーを使う。Orca Settings の Agents 画面に保存された起動引数が bypass になっていることと、インストール済み CLI の `--help` に合うことを確認する。設定を参照できない場合や引数が合わない場合は、`orca-cli` のカスタム起動手順で `terminal create --command` に対応する引数を明示する。他の harness も `--help` で対応する指定を確認し、通常の権限モードへ黙って fallback しない。

## 通常の session を開いて prompt を送る

委譲・相談・レビューは、harness を問わず Orca の terminal に通常の対話 session（TUI）を開き、入力 ready を確認してから prompt を送る。短い依頼でもこの手順を使う。新規・再開・fallback に適用し、`pi -p` / `codex exec` などの one-shot はユーザーが非対話実行を明示した場合だけ使う。pi の `--no-session` も通常の委譲では付けない。

追加指示は起動済みの同じ terminal / session に送る。回答後も session は残し、通常の委譲を print mode の繰り返しで代用しない。process が終了したときだけ、対象 session ID を指定して対話モードで再開する。起動・送信・開始確認の具体的な操作は後述の Orca 手順に従う。

## Harness ごとの手順

共通設定で選んだ harness の reference を読む。ユーザーが harness を指定した場合も同じ入口を使い、モデル・effort・権限モードは本文の共通設定に従う。


| やること                                        | 読む reference                               |
| ------------------------------------------- | ------------------------------------------ |
| Codex へ相談・レビュー・調査を依頼する / 同じ session で対話を続ける | [references/codex.md](references/codex.md) |
| pi の対話 session を起動する / 継続する                 | [references/pi.md](references/pi.md)       |


設定・認証・起動不調の調査は [dev-env](../dev-env/SKILL.md) から対象の reference を読む。Orca の terminal 操作と handoff・監督の使い分けは後述の「起動・連携は Orca 経由」に従う。

## subagent との使い分け

通常の分担は subagent など、agent が適した方法を選ぶ。別 repo での作業や独立したセッションが必要な場合は、この skill で委譲する。ユーザーが方法を指定した場合はその指定に従う。

モデル選択だけが必要な場合も、前述の共通設定を参照する。以下の委譲手順は Orca 経由の委譲に適用する。

委譲が壊れる原因は委譲先の判断ではなく、**渡す prompt に入っていない前提**にある。入っていないと、委譲先は自分で埋めようとして次のどれかをやる。


| 欠けている前提          | 起きること                                                                 |
| ---------------- | --------------------------------------------------------------------- |
| 作業ディレクトリが固定であること | 近くにある別の worktree / repo を見つけて、そこで作業を始める                               |
| 触ってよい範囲          | ディレクトリの中は正しいが、指示していない周辺まで直す。テストだけ直せばよい場面で production コードを refactor する |
| 親の会話は見えていないこと    | エラー文・ファイル名・既に決まったことを探しに行く。見つからなければ推測で埋める                              |
| 完了条件             | 実装せず調査して返す。あるいは「できました」で未検証のまま返す                                       |


どれも差し戻せば直るが、差し戻しは毎回同じ文言になる。**同じ文言を毎回書いているなら、それは prompt の定型に落ちる。**

## 起動・連携は Orca 経由

独立した agent の起動・連携は、依頼の目的に応じて次の skill を読み、その手順で行う。依頼文は後述の定型で整える。

- **監督・結果待ち・完了追跡・並列作業の統合を求められた場合**: [`orchestration`](../orchestration/SKILL.md) を使う。
- **担当を別 repo / agent / worktree へ渡す handoff の場合**: [`orca-cli`](../orca-cli/SKILL.md) の Full Handoffs を使う。引き継ぎ先と送信確認を報告したら親は終了し、完了まで監督しない。

Orca を利用できない場合は、そのエラーを報告し、別経路へ切り替えない。CLI の解決・バージョンに合った手順の取得・起動確認は上記 skill に従う。

同じ checkout で新しい session を開く場合は `terminal create --worktree <selector> --command '<harness の対話起動コマンド>'` を使う。別 checkout が必要な場合は `worktree create --agent <harness>` を使い、保存済みランチャーが選んだ model・effort・bypass に合わなければカスタム起動にする。`terminal create` の command 内の変数は委譲先の shell で展開されるため、親だけで設定した変数に依存せず、選んだ値を引数へ埋め込む。

いずれも `terminal wait --for tui-idle` の `satisfied: true` を確認してから送信する。送信受付と turn 開始を区別し、開始を確認できない場合は同じ prompt を重複送信しない。監督下では orchestration の dispatch / mailbox 手順で依頼を届ける場合も、worker 自体は対話 session で起動する。

## pi への handoff

**pi では `worktree create --prompt` を使わない**（Claude・Codex は可）。pi の TUI は入力 ready 前のキー入力を保持せず、prompt が滞留または消失して静かに失敗する。Orca の send 証明も `provider: "unsupported"` で未送信を検知できない（stablyai/orca#22580）。`orca-cli` の通常の handoff 手順に対し、次の順序を使う。

1. `worktree create --agent pi` で起動する。`--prompt` は付けない。pi には Orca 既定の bypass 引数が無いため、sandbox extension を使う環境では次の 2 コマンドに替える（`--worktree` を省くと呼び出し元の worktree で pi が動く）。`--agent` 無しの create は fallback shell が残るので、`terminal list` で未使用を確認してから閉じる。sandbox の有効・無効の確認は [pi の手順](references/pi.md) に従う。
   ```text
    ORCA worktree create --name <task-name> --no-parent --json
    ORCA terminal create --worktree id:<repoId>::<worktreePath> --command 'pi --no-sandbox --model "$MODEL" --thinking "$EFFORT"' --json
   ```
2. 起動した terminal に対して `terminal wait --for tui-idle --timeout-ms ...` を実行し、`satisfied: true` を確認する。pi は起動描画に数分かかるため、timeout は長めに取る。ready が確認できない間は送信しない。
3. `terminal send --text ... --enter` で依頼文を送る。
4. `terminal read` でターン開始を確認する。`accepted: true` だけで引き継ぎ成功としない。開始が確認できない場合は未確認として報告し、同じ prompt を重複送信しない。

## 必ず入れる4項目

1. **作業ディレクトリ（絶対パス）と、そこから出ないこと**
2. **その中で触ってよい範囲と、触らないもの**。不可逆・外部に見える操作（commit / push / PR 作成・merge・branch 削除）を委譲範囲に含めるかを明示する — 書かなければ作業して返すだけが期待値になる。手順が必須とする付随ファイル（意図ファイル・lock・生成物）も列挙に含める — 委譲先は列挙外を厳格にスコープ外と判断する
3. **self-contained なタスク記述** — 委譲先は親の会話を見ていない。エラー文・テスト名・ファイルパス・既に決まったことは prompt に貼る
4. **検証可能な完了条件**と、その検証を自分で回すこと。**報告形式**（何を返せば親が次へ進めるか）

実装タスクの進め方は [implement](../implement/SKILL.md) に従う。prompt に `implement` skill の実際のパスを渡す。

## テンプレート

```
作業ディレクトリ: <絶対パス>
このディレクトリの中だけで作業する。他の worktree・他の repo には出ない。
触ってよいのは <ファイル / ディレクトリ>（手順が要求する付随ファイル — 意図ファイル・lock・生成物 — があればそれも含める）。<触らないもの> は変更しない。
commit / push / PR 作成 / merge / branch 削除は <委譲する操作を列挙する | すべて親がやる>。

やること:
<タスク。あなたはこの会話を見ていないので、必要なものはここに全部書く>
<エラー文・テスト名・該当ファイルのパスをそのまま貼る>
<既に決まっていること、試して駄目だった方法があれば書く>

完了条件:
- <検証可能な条件。テストが通る / コマンドが期待の出力を返す / 差分が意図どおり>
- 上の条件を自分で実行して確認し、満たすまで直し続ける
- <実装タスクの場合: <implement skill の絶対パス> に従う>

報告:
- 変更したファイル（絶対パス）と、何をどう変えたか
- 完了条件をどう確認したか（実行したコマンドと結果）
- <PR を作成した場合: PR URL と、CI・レビュー・draft/ready の状態>
- できなかったこと・判断を保留したこと
```

## 補足

- **再委譲は設定で封じる。** worker の深さや tool の allowlist を設定で絞れるランタイムでは、そちらが prompt の注意書きより強い。prompt 側には書かない
- **prompt の禁止事項は絶対の境界ではない。** 委譲先 session へのユーザー明示指示は prompt の禁止を上書きしうる。強い境界が必要なら再委譲と同じく設定で絞る
- **委譲した PR を親が merge する運用では、merge 完了の確認まで委譲先に修正 push をさせない。** bot は ready 後も指摘を出し続け、委譲先が対応 push すると親の merge と head が競合する。停止条件を「ready 化まで」と prompt に明記し、以降の指摘対応は親か次の委譲に回す
- **分割と起動は親が担当する。** 子に分割・起動を任せると、子同士の調整が発生して stall の温床になる
- **worktree 内で動かしているときは絶対パスを必ず渡す。** 相対パスや repo 名だけだと、委譲先は main checkout 側を開く
- **モデルは親が決める。** この skill の「Agent・モデルの共通設定」から役割・データ区分で harness・model・effort と fallback 順を選び、起動時に指定する。委譲先に選ばせない
- **委譲元側の setup は委譲前に委譲元が完了する。** repo 作成・初回 push・wiki 登録のような SSOT 登録は「指示に含める」だけでは完了とみなさない — 未完了のまま委譲先が作業を始めると、後で漏れに気づいても差分の切り分けが付かない
- **personal データ区分の委譲は境界を明記する。** 認証操作（ログイン・窓口・署名）は人間に残し、生成物は `.local.` 命名で git 管理外に置くことを brief に書く。login・署名を tool として公開する harness では tool/permission 設定でも閉じる
