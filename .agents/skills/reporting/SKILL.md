---
name: reporting
description: "ある作業（PR / diff / セッションでの変更）や調査・リサーチ結果を、読み手が短時間で理解できる単体 HTML にまとめる。UI 変更・設定変更・データ移行・障害調査・技術調査・コード構造の変更いずれも対象。「レポートにまとめて」「変更点をまとめたノート」「共有用の html」「before/after で説明」「作業レポート」「reporting」「調査結果を共有」「何を変えたか説明する資料」などのリクエスト時に使用。"
user-invocable: true
---

# Reporting

作業や調査結果を共有用の単体HTMLにまとめる。材料・読者・レポート構成をこのskillで決め、語彙・図解・HTML描画・表示確認は [learnの共有成果物の制作](../learn/SKILL.md#共有成果物の制作) を使う。

共有だけの依頼ではHTMLを作って渡す。本人の理解確認は学習も依頼された場合、動画は明示的に依頼された場合だけ行う。

## 1. 対象・読者・型を決める

- 対象: PR / branch diff / セッション内の変更 / 調査結果。指示から特定できなければ現在のbranch diffを使う
- 読者: エンジニア / 非エンジニア。指示や共有先から判断できなければ一度だけ確認する
- 型: UI変更 / [非UIの変更](references/change.md) / [障害調査](references/incident.md) / [リサーチ](references/research.md)。複数の型が混ざる場合はpanel単位で切り替える

非エンジニアには画面や結果を中心に見せ、文脈が共有済みの経緯や不要なPR番号・commit・作成者・作成日を本文に足さない。エンジニアには必要な影響範囲とdiffへのリンクを足してよい。researchの出典と本文の `[n]` 参照は読者に関わらず残す。

## 2. 材料を集める

PRはrepoを固定した `gh pr diff <PR URL>`、branchは `git diff main...HEAD`、セッションは実際の変更と検証結果を読む。incident・researchは調査結果や調査ノートを材料にする。UI変更なら対象routeを列挙する。

diff・出力・調査で確認した事実を本文にする。推定は「（推定）」、未確認や未実施はその状態を明記する。ローカルの確認を本番反映やユーザー本人の確認として扱わない。

## 3. UI変更のbefore/afterを撮る

beforeはmainまたはデプロイ済み、afterはbranch。同じURL・viewport・表示条件で撮る。beforeを取得できなければその不足を明記し、画像を捏造しない。

1. [orca-cli](../orca-cli/SKILL.md) のversion-matched browser guideを読む
2. このskillの [tools/anno-example.md](tools/anno-example.md) に従って [tools/anno.js](tools/anno.js) で変更箇所へ注釈を入れる。selector・テキストで対象を指定する
3. Orca内蔵browserで注釈付き画像を撮る。原稿では画像の上に「反映前」「反映後」のキャプションを置き、必要なら番号と本文を対応させる
4. `cwebp` が利用できればWebPへ圧縮する。learnの共有成果物の制作に従い、画像をdata URIとして原稿に埋め込む

位置の移動・要素の削除・導線の追加など、読者が認識できる変更を載せる。注釈のない画像や、読者が認識できない微細な差分を載せない。

## 4. learnの原稿を書いて描画する

先に [learn/SKILL.md](../learn/SKILL.md) の「共有成果物の制作」と第2〜5節を読む。拡張Markdownだけを書き、HTML・CSS・SVGを手書きしない。独自テンプレートやHTMLの後加工も使わない。

- リードまたは最初のpanelに結論を置く。各 `##` panelは画面・領域・事象・sub-questionのいずれかに絞る
- 見出しで「何を変えたか・何がわかったか」を伝える。事実の列挙は1項目につき1事実、因果の説明は短い段落にする
- 読者が辿る順に並べる。UIは画面順、非UIは処理順、incidentは症状→原因→対処、researchは読者が知りたい順。作業・レビュー・調査の時系列で分けない
- before/afterや選択肢はMarkdown表にする。関係・流れを示す図はlearnの部品から選ぶ。ファイル一覧の転記や装飾だけの図を足さない
- 型ごとのreferenceを読む。長いレポートは `template: doc` で目次付きにし、短い一覧は `template: sheet` にする

CLIのパスはreportingと同じ親dirにあるlearnから解決する。次は両skillが `.agents/skills/` 配下にある場合の例:

```bash
learn_dir="$(cd .agents/skills/learn && pwd)"
mise exec -- node "$learn_dir/scripts/am.mjs" render report.md --no-open
```

別repoから呼ぶ場合は、読み込んだlearnの実際のdirで置き換える。出力先を指定されたら `--out <絶対パス>` を付ける。指定がなければCLIの既定出力先を使う。

## 5. 検証して渡す

learnの第7節「成果物の検証」に従い、Orca内蔵browserでHTMLの表示・図・表・操作を確認する。レポートとして次も点検する:

- 読者に合う語彙と粒度か。見出し・順序で結果と因果が伝わるか
- UI画像に注釈があり、before/afterの条件とキャプションが対応するか
- 画像がdata URIとして埋め込まれ、外部ファイルへの依存を残していないか
- 出典・推定・未確認・未実施を保っているか。researchに「わからなかったこと」とSourcesがあるか

結論と生成HTMLのパスを渡す。未検証の部分は明記する。公開リンクへのアップロードはユーザーの公開指示がある場合だけ行う。
