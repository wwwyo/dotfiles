---
name: pr
description: "実装済みの変更からPRを作成する。「PRを作りたい」「プルリクエストを作成」「PR作って」「draft PRを出したい」で使用。実装を進めたagent自身がgh CLIでdraftを作成し、previewなどでsubagentのE2E/APIテストを行い、CI・レビューコメント監視を経てreadyにする。"
user-invocable: true
---
# PR

PRを`gh`で作成するスキル。[implement](../implement/SKILL.md) で実装したagent自身がdraftとして作成し、previewなどでのQA・self reviewとCI・レビューの確認後にreadyにする。assigneeは自分、タイトルはプロジェクト規約に従い、bodyの形式は対象repoのPRテンプレートを優先する。

このready条件はPR作成agentが判定する。定期merge laneの判定は[pr-auto-merge](../pr-auto-merge/SKILL.md)の独立した規約に従う。

## ワークフロー

ステップ1〜6を上から順番に実施する。step 6 は wwwyo/* の repo の場合のみ実施する。step 5 (CI・レビューコメント監視) まで通し、QA対象の検証が失敗・未実施ならdraftのまま理由を報告する。step 3 (PR作成) までしか実行していない場合は未完了とみなす。

### 1. タイトル決定

Conventional Commits形式でタイトルを生成する: `<type>(<scope>): <description>`

### 2. Body作成

まず対象repoのPRテンプレート（例: `.github/PULL_REQUEST_TEMPLATE.md`、repo rootや`docs/`の`pull_request_template.md`、`PULL_REQUEST_TEMPLATE/`配下）を確認する。テンプレートがあれば、その見出し・順序・記入項目を優先する。複数ある場合はrepoの規約と変更内容に合うものを使う。

repoにPRテンプレートがない場合は、以下のテンプレートに沿ってbodyを構成し、見出しレベルを守る。

```markdown
## Blast Radius

{高 / 中 / 低} — {影響の深刻さ・検証状況・復旧可能性を根拠に、簡潔に説明する}

## What

{このPRで扱う内容の簡潔な説明（1-2文）}

## Background

{Epic / 機能全体の why: 解決したい課題と、どう解決するかの方向性}
{その Epic の中で本 PR が何を担うか（1 文）}

{関連DDがあれば: Related: [DDタイトル](<DD URL>)}
{関連Figmaがあれば: Related: [Figma: 画面名](<Figma URL>)}
{in-repo ドキュメントがあれば: Related: [ドキュメント名](<GitHub blob URL>)}
{関連issueがあれば: Related: #<number>}

## QA

{テスト・実操作など、どうやって品質保証したかの概要説明}

## Summary

{変更の詳細を箇条書きで列挙。粒度は粗めに、レビューの足がかりになる単位で記載する}
```

#### 全セクション共通の原則

- public な情報源から辿れる内容だけで構成する（最重要）: 本文の事実・経緯・参照は、レビュアーが辿れる公開情報（コード・commit・GitHub の issue/PR・DD・Figma・公開ドキュメント）に裏付けされていること。裏付けのない情報は本文で完結する 1 文要約に展開するか、書かない。
- 振る舞い・意図で書き、実装の内部事情を繰り返さない: 図 / ツリー / コードが既に示す構造・命名・自明な処理や、実装内部の識別子（変数 / field / hook / 型 名）は言語化しない。識別子を出すのは、それ自体が論点のとき（再利用する共有 / public な API など）に限る。説明は非自明な why / 制約 / 共有関係に絞る。

#### セクション別の書き方

以下はこのskillの既定テンプレートを使う場合の書き方。repoのPRテンプレートを使う場合は、その形式に合わせて関連する内容を対応する項目に記載する。

- Blast Radius: 本文の最初に置く。影響の深刻さ・検証状況・復旧可能性から高／中／低を判断し、根拠を簡潔に書く。
- What: 構造を新規追加・再編する PR では、各レイヤー / モジュールの責務と依存が一目でわかる図を 1 つ載せる（dir ツリー or `handler→service→module→repository` のような依存図 — 構造を最も素直に表せる方）。図の起点に path を明記し（repo root から、monorepo なら module root からの相対 path）、注釈は図から読めない why（責務分担・共有関係・暫定で後に置換 など）だけに留める。網羅的な責務一覧表は作らない。
- Background: why を 2 階層で。①Epic / 機能全体の why（解決したい課題と方向性。例: 「〜という課題がある → 〜の仕組みで解決する」）、②本 PR の位置づけ（Epic の中で本 PR が何を担うか 1 文。例: 「本 PR ではそのうち〜を実装する」）。アプローチの詳細（それは What）や scope の除外話（含めない範囲・後続 PR に委ねる事項・暫定実装の理由）は入れない。詳細は DD / issue に委ね `Related: ...` 行で補う。
- QA: テスト・実操作など、どうやって品質保証したかを書く。現在のPR headで確認した結果を記載する。QA対象外なら「QA未実施」と理由を記載し、同じ内容をPRにコメントする。
- Summary: 差分の逐語訳にせず、変更の塊ごとにまとめる（ファイル単位の列挙や些末な変更は書かない）。
- 上記以外のセクション（`## Migration`, `## Breaking Changes` など）は変更内容に応じて自由に追加してよい。

### 3. PR作成

まず stacked PR かどうかを判定する（現在のブランチが他の未マージ PR の上に積まれている、または1つの変更を複数層に分ける場合）。stacked ならこの step は `gh stack` に任せ、手順は `gh-stack` skill に従う — 素の `gh pr create` で先に作ると base が default branch を向いてしまう。

stackedでもstep 5の終了条件を満たす前はdraftを維持する。`gh stack submit --open` は使わず、ready化はstep 6で行う。

stacked でなければ、未 push なら `git push -u origin <branch>` してから `gh` で draft PR を作る。

```bash
gh pr create --draft --assignee @me --title "<title>" --body-file <本文ファイル>
```

`gh stack` が無い環境の fallback: `--base` で親ブランチを指定し、親 merge 後は新しい main へ rebase して `git log <main>..HEAD` と diff から親 PR の変更が消えたことを確認する。

- ブランチ削除は `gh` 経由で行う。`git push origin --delete` で消すと子 PR が retarget されず close される。
- merge は `gh pr merge --squash`（デフォルト squash merge 前提）。切り替え先の main が別 worktree で checkout 済みだと、PR の merge 後にローカルブランチ削除だけ失敗する。`gh pr view` で merge 済みを確認し、リモートブランチは明示的に削除する。現在の worktree が使うローカルブランチは無理に削除しない。

PR 作成後、出力された PR URL を `orca tab create --url <PR URL>` で Orca のブラウザタブで開く。

### 4. QA

PRDがない場合はユーザーの依頼内容を要件とし、PRDの不在だけを理由にdraftを維持しない。

draft PR作成後、対象repoのe2eで関連するE2E/APIテストをsubagentで実行する。まだなければ `e2e init` を実行する。previewを使う場合はデプロイ完了を待つ。

QA担当は関連実装を読まず、要件と実際のUI/APIの振る舞いから検証する。実装担当は並行してimplementのself reviewを進める。仕様にない点や疑問は両者のコミュニケーションで解消し、必要に応じて製品・テストを修正する。self reviewと修正が終わったコードで再テストする。テストの優先度・unit testの扱いは [implementのテスト方針](../implement/SKILL.md#テスト方針) に従う。

文書など実操作の対象がない変更は、QA未実施と理由を記録する。QAの結果はrepoのPRテンプレートの検証項目（既定テンプレートでは `## QA`）にまとめる。検証項目がなければ、repoの形式に合わせて追記する。

### 5. CI・レビューコメント監視

PR作成後、CI の完了とレビューコメントの到着を監視する。**差分検知ではなく状態評価**: 5分ごとに終了条件を満たしたかを評価し、満たしたら監視終了。評価の単位はagentに備わった確認機構か `gh pr checks --required` + `gh pr view --json statusCheckRollup,reviews,comments,mergeable,reviewDecision`（未 resolve の thread は `gh api graphql`）で、変化検知スクリプトに頼らない。

**監視は「完了で自分を起こせる」機構で回す。** 素の background 実行は終了を通知しない環境があり、終了に気づけず監視が死ぬ。subagent に載せる等、終了時に呼び出し側へ通知が来る経路で実行する。subagent 内部では、監視 script を background で起動してその出力を **blocking read**（出力 or 終了 or timeout まで返らない read）で受け取る繰り返しにする — sleep やポーリング間隔を LLM 側で自前管理すると受動的に凍りうる。

新しいコメント・CI fail・コンフリクトを見つけたら対応してループ継続、終了条件を満たしたら監視を終えてユーザーにPRの状態を報告する。製品やテストの修正はimplementの流れで自身が行う。修正・追加commit・rebaseでheadが変わった場合はQA対象の判断を見直す。QA対象ならstep 4で新しいheadを再検証し、PR bodyの検証項目を更新する。過去headの成功はreadyの根拠にしない。

CI・レビューが既に完了し、以下の終了条件を全て満たしている場合は、この step を即座に評価して終えてよい。

コメント対応ポリシー:

- AIレビューボット（copilot, claude, codex, coderabbit, pullfrogなど。過去に別の bot が付けた指摘も含む）のコメントには自動で返信・対応してよい
- 人間のレビュアーのコメントには返信しない。ユーザーに対応が必要な旨を報告するのみ
  - 例外としてユーザ本人(wwwyo)へは返信して良い
- AIレビューボットのコメントに返信したら、コード編集の有無に関係なく該当するすべてのレビューthreadをresolveする（`gh api` のGraphQLで `resolveReviewThread` を呼ぶ）。

監視の終了条件:

- QA対象ならstep 4で対象要件の検証が現在のPR headで成功している。QA対象外なら現在のdiffにもその判断が適用でき、理由がPR bodyに記録されている
- required な check が全て pass している（`gh pr checks --required` が exit 0）。required checkが設定されていない場合の`no required checks reported`は失敗として扱わず、`statusCheckRollup`で実際のCI結果を確認する。レビュー以外のnon-requiredなadvisory checkは終了をブロックしない
- 開始されたレビューが全て終了している。required / non-requiredを問わず、レビューが待機中・進行中ならdraftを維持する
- コンフリクトしていない（`mergeable` が CONFLICTING でない）
- 未対応のレビューコメントがない（AIボットのコメントは対応済み、人間のコメントはユーザーに報告済み）
- 上記を全て満たした場合、監視を終えてユーザーにPRの状態を報告する

### 6. (wwwyo/* のみ) ready にする

対象repoが `wwwyo/*` の場合、step 5の終了条件を満たした後、`gh pr view <PRのURL> --json headRefOid,isDraft` で現在のheadを再確認する。QA対象ならheadが検証済みのSHAと一致することを確認し、不一致ならstep 4で再検証してstep 5に戻る。QA対象外なら最新diffとPR bodyの理由を再確認する。条件を満たしたら `gh pr ready <PRのURL>` でdraftを解除し、`isDraft: false` と確認済みheadからSHAが変わっていないことを再確認する。変わっていたら `gh pr ready <PRのURL> --undo` でdraftに戻し、新しいheadでstep 4・5を確認し直す。個人repoは人間レビュアーを介さないため、条件を満たしたdraftはreadyまで進める。業務repoではこのstepをskipし、draftのまま人間のレビューに委ねる。

## 注意点

- `gh` コマンドは sandbox 外で実行する（TLS証明書検証の制約回避）。
- `gh` で PR を参照するときは番号だけでなく URL（または `-R owner/repo`）で対象 repo を固定する。番号だけだと cwd の repo を暗黙に見に行き、worktree 削除後などに別 repo へ静かに誤爆する。
- AIレビューボットの指摘をコードに採用する前に、その変更がユーザーが過去に明示的に外した・却下した判断の再導入でないか確認する（git log・直近の会話・PR 履歴）。bot指摘の逐語適用で同じ設計判断を二度入れて二度外される事故が起きている。同一論点にP2（通常。いずれ修正すべき一般的な問題）以下の指摘が何度も出る場合はこのループの兆候とみなし、コードを再度変更せず、却下理由を返信するかユーザーに判断を委ねる
- bot の指摘本文・修正案（条件分岐の追加を含む）は事実として扱わず、採否の前に upstream の実コード・vendor の公式ドキュメントで検証する。指摘はレビュー時点の状態への言及なので、前提が対応時点でも成立するか（依存 PR が merge 済み・対象 file が移動済み等）も合わせて確認し、前提が消えた指摘は stale として扱う。実機で反証できた指摘は、重要度ラベルに関わらず根拠を添えて不採用にしてよい
- レビュー指摘が極端なエッジケースへの対処なら採用しない。現実的に起こり得ないシナリオのためにコードを複雑化する方が害が大きい — 対応しない場合は理由を添えて返信する
- 完了報告の前に `git status` が clean かつ untracked 0 であることを確認する — 生成物の commit 忘れ・別 worktree への置き忘れをここで止める
- dotfiles の変更を merge したら、完了報告の前に canonical checkout（`~/src/github.com/wwwyo/dotfiles`）を pull して `~` 側への反映を確認する（dir link 配下は merge 時点で即届くが、chezmoi apply が要る file もある）
