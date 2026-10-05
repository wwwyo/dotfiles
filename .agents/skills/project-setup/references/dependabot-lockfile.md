#### 12.2 の補足: Dependabot PR の lockfile 未追従を自動修復する CI

Dependabot は workspace 配下の `package.json` だけを更新し、workspace 共有の root lockfile（`bun.lock` 等）を追従させない PR を作ることがある（security update で特に観測。dependabot-core issue [#11602](https://github.com/dependabot/dependabot-core/issues/11602)）。そのままだと CI の `--frozen-lockfile` install が必ず落ちる。

`dependabot.yml` に「lockfile を必ず再生成せよ」という設定項目はなく、`@dependabot` コメントコマンドでも生成物は変えられない。repo 側の CI で自動修復するしかないため、lockfile を commit する JS/TS の package manager（bun / npm / pnpm / yarn）を使う repo では `.github/workflows/dependabot-lockfile.yml` を生成する。

```yaml
name: dependabot-lockfile
# security update など、dependabot が workspace 配下の package.json だけを更新して
# root の bun.lock を追従させない PR を自動修復する。dependabot 起動の pull_request
# workflow は token が read-only になるため、pull_request_target で動かす。
on:
  pull_request_target:
    types: [opened, synchronize]
permissions:
  contents: write
jobs:
  regen-lockfile:
    if: github.actor == 'dependabot[bot]' && github.event.pull_request.head.repo.full_name == github.repository
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7
        with:
          ref: ${{ github.event.pull_request.head.ref }}
      - uses: jdx/mise-action@v4
        with:
          version: <その repo の mise-action に合わせたバージョン>
      # PR の manifest 由来の lifecycle script は実行しない
      - run: bun install --ignore-scripts
      - name: bun.lock が変わったときだけ push する
        run: |
          if git diff --quiet bun.lock; then
            echo 'bun.lock is already in sync'
            exit 0
          fi
          git config user.name 'github-actions[bot]'
          git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
          git add bun.lock
          git commit -m 'build(deps): regenerate bun.lock for workspace bump'
          git push
```

要点:

- **`pull_request_target` が必要**: dependabot が起こした `pull_request` workflow は `GITHUB_TOKEN` が read-only で secret も渡らず push できない。`pull_request_target` は base 側の workflow 定義で実行されるため write token が取れ、かつ実行コードは PR 側に改ざんされない
- **ガード**: `actor == 'dependabot[bot]'` かつ head が同一 repo（fork PR を除外）
- **PR の manifest 由来の lifecycle script は実行しない**: `pull_request_target` は PR head のコードを checkout するので、install 時に `postinstall` 等を走らせない。bun は `bun install --ignore-scripts`、npm なら `npm ci --ignore-scripts` 相当
- **lockfile に差分があるときだけ commit & push**: dependabot が lockfile を正しく含めた PR では no-op になる
- **厳密には防止ではなく自動修復**: PR 直後の `--frozen-lockfile` CI が一度落ちてから、push（synchronize）で再実行されて治る。その一拍の失敗は残る
- **`bun.lock`・`bun install` は対象 repo の package manager に合わせて置き換える**（`package-lock.json` / `pnpm-lock.yaml` / `yarn.lock`）。`mise-action` の `version` や不要な tool の除外（参考実装では `env.MISE_DISABLE_TOOLS` で重い tool を省いている）も repo の実情に合わせる
