# CodeRabbit

`wwwyo/coderabbit`（public repo）の `.coderabbit.yaml` を central config として使っている。アカウント配下に `coderabbit` という名前の repo を作ると、repo 個別の `.coderabbit.yaml` を持たない repo の既定値として効く。挙動がおかしいときはまずここを見る。

- **優先順位**（docs の順位表、高い順）: workspace/org の global overrides（UI） > repo の `.coderabbit.yaml` > central repo の `.coderabbit.yaml` > repo UI settings > org UI settings > schema defaults
- **前提**: CodeRabbit の GitHub App installation が `wwwyo/coderabbit` を読めること（All repositories か、scope に同 repo を含める）
- **反映は即時ではない**: central repo の作成・設定変更直後は伝播遅延があり、最初の PR は新 config 未反映で skip されることがある。動作検証は2本目以降の PR で見る
- **config ソースの判別**: PR の CodeRabbit コメント内の `Configuration used: Repository: ...` 表記で、使われた config が central か repo 個別か分かる。`@coderabbitai configuration` を PR に投げると merge 済みの実効 config と各値の出所が出る
- **`inheritance`**: `true` にすると repo 側 yaml の「ファイルごと優先」が key 単位のマージに変わる。ただし各レベル自身が持つフラグなので、repo 個別 yaml がある repo では repo 側にも `inheritance: true` を書かないと central と merge されない
