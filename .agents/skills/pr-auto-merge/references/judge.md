# LLM judge — QA と Blast Radius による merge 判定

常に hold の path を除く全 merge 候補を判定する。PR 本文の `Blast Radius` と
`QA` を差分・CI・必要な利用箇所と照合し、リスク判定の根拠が確かかを確認する。
verdict は head SHA と判定時の本文・base・check 結果に紐付けて記録する。

```bash
# 1. 判定材料を取る（diff・files・PR 本文・head の check 群・現在 head SHA）
python3 ~/.agents/skills/pr-auto-merge/tools/pr_triage.py judge-input \
  --repo <r> --number <n>

# 2. sha と context_hash は judge-input の値をそのまま使う
python3 ~/.agents/skills/pr-auto-merge/tools/pr_triage.py judge-result \
  --repo <r> --number <n> --sha <sha> --context-hash <context_hash> \
  --verdict ok|ng|repair --reason "1行の理由"
```

- verdict は **head SHA と判定材料に紐付く**。本文・base・check 結果が変わっても無効で、次 tick の
  gate が再度 `judge` action を出す
- **ok を出しても merge は自分では発行しない** — judge は lane への推薦で
  あって発行権は持たない。verdict が ok でも、merge は次以降の tick で
  script が残りの hard gate（CI・pullfrog-approval 等）を全部通してから
  発行する
- ng でも PR は close しない（hold が続くだけ。判断材料を report に書く）。
  依存更新への対応が具体的に必要なら `repair` を記録し、次 tick の script dispatch に渡す。
- **file 分類を先に適用し、diff サイズを条件にしない**。`judge-input` は
  lockfile を除いた全差分を返す。大きい場合はファイル単位で読む。
- **依存・tool の lockfile は無視する**。`ignored_files` の内容・間接依存の更新・
  差分量を ng の理由にしない。manifest とそれ以外の file を見る。
  GitHub Actions の `*.lock.yml` は実行する workflow なので除外しない。
- verdict は head SHA・判定材料の `context_hash`・`policy_version` に紐付く。判定規則を変更するときは
  `tools/pr_triage.py` の `JUDGE_POLICY_VERSION` も更新する。旧 verdict は
  再利用せず、同じ head でも次 tick の plan で再判定する。head の変更時も再判定する。

## QA と Blast Radius

PR の自己申告をそのまま採用せず、影響の深刻さ・検証状況・復旧可能性から
高 / 中 / 低が妥当か判断する。QA の結果が現在の head の影響範囲を覆っているか、
記載された根拠と実際の差分・実行結果が一致しているかを確認する。

- **高**: hold（`ng`）。検証済みでも自動 merge しない。
- **中**: 影響に対応する検証が済んでいれば `ok`。未検証や根拠不足なら hold（`ng`）。
- **低**: `ok`。QA 未実施でも、低と判断できる理由があればよい。

記載がない場合も、差分と確認できる検証結果から判断する。特に bot PR には
このセクションがないことがある。低とする根拠や、中の検証結果を確認できなければ
hold にする。テストファイルの追加や CI green だけを、影響範囲の検証完了とは扱わない。
`ok` は merge 候補への推薦であり、CI・review 等の通常の gate は script が確認する。

## 変更内容の確認

plan の action にある `whitelist_hint` で判定の軸が決まる。
以下の個別基準でも、上記の QA・Blast Radius の基準を満たしたときにだけ `ok` とする。

### `bot_dep`（bot の依存 manifest・lockfile・GitHub Actions workflow 更新のみ）

file 一覧が依存 manifest / lockfile / `.github/workflows/`（github-actions
ecosystem の依存置き場）に閉じることを確認し、lockfile を除いた manifest・
workflow を判定する:

- 触っているのが manifest・lockfile・`.github/workflows/` だけ（script の
  path 分類でも確認済みだが lockfile 以外の内容を自分でも見る — workflows
  以外の code・secrets が紛れていたら ng。生成物の `*.lock.yml` は常に
  hold でここには来ない）。ただし `bot_dep_repair` は後述の追従差分を含めて判定する。
- workflow の変更は manifest と同じ軸で見る — action の version bump なら
  release note・breaking・利用箇所を照合し、workflow 定義そのものの
  意味変更（トリガー・権限・手順の差し替え）が紛れていたら ng
- **major という理由・release note の breaking 記述だけで ng にしない**。
  公式 release/migration guide と PR head の設定・利用箇所を照合し、runtime・peer
  dependency の条件も確認する。利用していない削除 API/option は対応不要とする。
- **公式の変更内容が実際の利用箇所に明らかに非該当なら、追加の実行検証は不要**。
  runtime・peer dependency の条件も満たし、追従不要と確認できれば、
  公式資料と PR head の利用箇所を根拠に ok とする。CI が無い・対象 workflow/job が
  未実行・skip というだけで ng にしない。例えば checkout の fork 制限が
  特定 trigger のみを対象とし、その trigger を使っていなければ制限は非該当。
  ただし head の check が fail している場合は（required 以外も対象）、その失敗が
  更新と無関係かを確認してから ok にし、根拠を reason に書く。更新由来なら
  repair、無関係か判断できなければ ng — required が無い repo では赤い check を
  止められるのはこの判定だけ。
- 実行検証は、変更が利用箇所に影響する場合や、公式仕様と設定だけでは互換性を
  判断できない場合に行う。影響する操作を覆う PR head の CI/test/build を確認し、
  既存 CI で不足する場合だけ追加検証する。required check 等の script の hard gate は維持する。
- 対応が必要なら、該当 file・利用 API・必要な追従・検証方法を reason に書いて
  `repair`。次 tick の script が author session に渡す。修正後の新 head は全差分を
  再判定し、必要な CI/test/build が成功すれば ok。互換性を確認できないものは
  残る不明点を示して ng。設計の選択が必要なら具体的な選択肢を本人に返す。
- grouped dependabot PR は manifest の直接更新を全件見る。一部だけ merge はできない
  ので、1件でも要対応なら PR ごと repair、確認不能なら PR ごと ng
- lockfile だけの PR は lockfile の内容判定を省く。影響は上記の基準で判断する。
- この経路は pullfrog-approval 免除の whitelist 枠なので、ここで厳しめに
  見る。迷ったら ng として理由を report に書く

### `bot_dep_repair`（依存更新のために修正された bot PR）

script が元の依存-only PR の `repair` 判定を記録したものだけが対象。
manifest と **追従コード・設定・test を含む全差分** を確認する。
元の機能・挙動を保つための必要な追従だけで、影響箇所の検証と current head の CI が
成功し、上記のリスク基準を満たしていれば ok とする。未修正箇所があれば再度 repair、無関係な変更・未確認の
互換性があれば ng。always-hold path・required check・未解消 review は維持する。
新しい head には旧 head の ok を流用しない。merge は script のみが発行する。

### `risk_review`（通常の変更）

通常コード・docs・tests・設定を含め、全差分の影響を上記の基準で判断する。
nits や codemod という説明も実際の差分と照合する。

### 要判定 path 一般

- **破壊的シグナル**: 不可逆マイグレーション（DROP / DELETE / カラム削
  除）、rollback の無い deploy 設定変更、prod 向けのバージョン固定解除
- **見えない側への影響**: schema 変更が読み取り側・書き込み側を壊さないか、
  tool version bump がその tool の非互換を踏まないか
- **script が分類不能にしたファイル**（未知の拡張子・basename）: 中身が
  無害かどうかここで決める

## 判定の書き方

`--reason` にリスク区分・判定の根拠・QA の充足状況を簡潔に書く
（「中: 検索結果に影響、current head の関連 E2E 成功、revert で復旧可能」等）。judge verdict は
 `pr-watch.jsonl` に省略せずイベントとして残り、report と監査の材料になる。
 参照URL・検証手順・長い根拠は `pr_triage.py log --input <JSON_FILE>` の
 `note` event へ同じ repo/pr/sha とともに記録する。別の Markdown log は作らない。

判断が付かないものは ng。**ng のコストは lane に乗らないだけ**で、
理由を report に残し、本人の判断に回す。誤 ok のコストは
気づかないまま merge されること。
