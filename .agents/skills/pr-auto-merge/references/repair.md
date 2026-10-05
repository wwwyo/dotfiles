# tick の修正対応 — author session 向け

script の dispatch が送った該当 PR だけを調べる。レビュー指摘の妥当性を
判断し、競合・依存更新の CI 失敗・major 更新への追従は以下の範囲で調査・修正する。
merge は author session で発行せず、修正後の次 tick で script に返す。

## 共通手順

- PR の head・base・状態を取得する。OPEN でなければ作業しない。
- Orca の該当 worktree を使う。別の作業があるなら `orca worktree create`
  で分離する。repo の AGENTS.md と delegate skill の設定に従う。
- push・コメント直前に state と head を再取得する。OPEN でなくなった、
  または他の session が head を更新した場合は push せず再確認する。
  通常 push を使い、他の変更を上書きする force push はしない。
- 変更は必要な最小限にする。ローカル検証の結果と未確認事項を区別して
  PR に原因・変更・理由を書く。ローカル green を hosted CI green としない。
- 判断や人間の対応が必要なら、修正せず PR に理由を書く。重複 PR の
  比較・統合・close、全 open PR の横断レビューはこの手順に含めない。

## 機械的な競合解消

1. `mergeable` を取り直す。bot の自動 rebase 等で解消済みなら何もしない。
2. **その PR の base** を取り込む。stacked PR の base は親ブランチであり、
   main 固定にしない。stack は親から処理する。
3. 位置ずれや同じ変更の重なりなど、意図を選ばずに解消できるものだけを
   修正する。production コードもこの条件なら対象。lockfile・生成物は
   repo の正規コマンドで再生成する。競合の一方が upstream 管理 skill の
   改変を含む場合は「原本へ戻す」で閉じず、ローカル差分が
   `.agents/skillctrl/intents/<name>.md` の意図でカバーされているかで
   分岐する — 意図内ならローカル側を保持して機械的解消、意図に無い
   upstream の欠陥なら upstream へ修正を返す、曖昧なら item 4 の hold。
   原本は root の `skills-lock.json`（alias/merge は `.agents/skillctrl/upstreams.json`）
   の `sourceUrl` + `skillPath` から git で照合できる。skill の tree を変えたら `skillctrl record <name>` で
   hash を再記録する（放置すると `Skill lock status` CI が fail する）。
4. 両側が同じ箇所を違う意図で変え、残す側で挙動・主張が変わる場合は
   hold。片側の変更・情報を捨てて通さない。ページの統合が必要な競合も hold。
   hold のコメントには (a) 機械的解消可能と判定した file と根拠（対象 PR の
   base に同等内容が landing 済みかの確認方法）、(b) 要判断 file ごとの消失
   リスクと移設先候補、(c) 解消後に残る差分の見通しと close の可否、を書く
   — 作者が判断材料を集め直さなくて済む形にする。
5. `git diff <base>...HEAD` を読み、想定外の差分がないことを確認する。
   repo の必要な検証を実行して push し、解消内容をコメントする。
6. この回は merge せず、次 tick の CI・レビュー・path 分類の再検証に返す。

## major 更新への追従

judge が `repair` とした依存更新も対象。CI が green でも、移行対象の API/option を
実際に使用していれば対応する。reason の file・API・根拠を公式 migration guide と
照合し、元の挙動を維持する最小限の移行を実装する。削除 API の代替や設定の移動、
必要な runtime/peer dependency の整合も対象。影響箇所を検証し、CI と同じコマンドを
通して通常 push する。新たな依存を加える場合は exact pin と repo の cooldown を守る。
不要な新機能の導入、設計・挙動の選択を含む場合は選択肢と未確認事項を示して hold。
対応済みの新 head は全差分の judge・CI・review 再検証に返す。author は merge しない。
code 修正の QA と always-hold file 分類も確認する。

## 依存更新に伴う CI 修正

対象は bot が依存 manifest・lockfile だけを更新した PR の失敗。
失敗ログを取得し、依存更新による機械的な追従で直せるか切り分ける。
pending・check 未起動を失敗と決めつけず、待たずに次 tick に返す。

### cooldown

`blocked by minimum-release-age` 等は時間以外で解消しない。
rerun、cooldown の解除・除外、version の変更をしない。registry 等の
publish 時刻 + repo の cooldown 期間で解除日時を計算し、PR に記載する。
緊急性があっても例外を作らず本人に判断を返す。

### frozen lockfile

`lockfile had changes, but lockfile is frozen` は、workspace の manifest
bump に共有 lockfile が追従していない可能性がある。repo のルートで
通常の install（例: `bun install`）を実行し、lockfile を再生成する。
CI の frozen install を含む同じコマンドで検証する。CI 自体の frozen
設定や supply chain 対策を緩めて通さない。

### 依存ペアの不整合

`react` だけ上がって `react-dom` が追従しない bump では lockfile の版が割れ、
`Incompatible React versions` が import 時に投げられる。`react` と `react-dom`
は lockfile で同じ版に揃え（`@types/*` は peer が React major に合う版でよい）、
遅れている側を更新して lockfile を再生成する。この揃え直しは
`### version への追従` 手順 3「依存 version を変えない」の例外。manifest が
hold segment 配下なら揃えても lane 上は hold のまま — 規約外 merge の要否は
[SKILL.md](../SKILL.md) の always-hold path の注記に従う。

### version への追従

許可するのは型・シグネチャへの annotation の追従、rename された export
の参照修正、削除された API の同等な後継への置換。振る舞いの選択、
新機能への移行、bump 前から赤い既存不具合の修正は対象外。

1. PR の head で CI と同じコマンドを実行して再現する。
2. エラーに出た依存名を原因と決めず、疑わしい依存を一つずつ一時的に
   元へ戻して切り分ける。bump 前から赤いならその根拠を書いて hold。
3. 最小限の追従だけを修正する。依存 version を変えない（`### 依存ペアの
   不整合` で react / react-dom を揃える場合はこの限りでない）。キャストや
   検証の無効化でエラーを隠さない。切り分け用変更は戻す。
4. CI と同じ typecheck / test / build をローカルで通して push。
   grouped PR は全依存の追従を検証する。
5. 原因・変更・検証結果を PR にコメントし、次 tick に返す。hosted CI
   green になっても merge の条件を緩めず script の判定に従う。

課金・利用上限・外部サービス障害等の根拠があれば、人間対応の理由を
PR に書いて hold。失敗ログだけで根拠なく billing と断定しない。
