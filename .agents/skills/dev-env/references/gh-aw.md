# gh-aw（GitHub Agentic Workflows）

`.github/workflows/*.md` が正本で、`*.lock.yml` は compiler の生成物。編集は `.md` に対して行い、両方を同じ変更に含める。

- **private repo を checkout する job は permissions に `contents: read` の明示が要る**。書かないと `actions/checkout` が `repository not found` で失敗する（生成物が default permission を前提にするため、job が権限を絞ると checkout に権限が残らない）
- **変更の検証は CI 再実行まで完了とみなさない**。ローカルの compile 成功は生成物の整合だけを示し、workflow が実際に動くかは Actions 上でしか分からない
