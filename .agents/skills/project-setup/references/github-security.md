Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

#### 12.1. 公開範囲に応じたセキュリティ設定

初回 push 後、GitHub 上の visibility に応じて実行する。`gh-secure` はグローバル導入済みを前提とする（[導入手順](../../../../README.md#github-cli-拡張)）。

以下の `<owner>/<repo>` はステップ 12 で作成した repo に置き換える。

```bash
mise exec -- gh repo view <owner>/<repo> --json visibility --jq .visibility

# PUBLIC の場合
mise exec -- gh secure --repo <owner>/<repo> --yes vulnerability-reporting secret-scanning dependabot code-scanning

# PRIVATE の場合
mise exec -- gh secure --repo <owner>/<repo> --yes dependabot

mise exec -- gh secure status --repo <owner>/<repo>
```
