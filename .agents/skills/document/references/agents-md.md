# AGENTS.md ガイドライン

AGENTS.md は、agent が起動時に読む repo の案内である。
構造と参照先を中心に書き、詳細な知見や手順は参照先に置く。
文章は [共通方針](../SKILL.md#簡潔で明確に書く) に従う。

## 構成

テンプレートは `assets/agents-md.md`。

- Story — 書き方と要否の判定は `prd` skill の `references/story-format.md` に従う。プロダクトの story が無い段階（ライブラリ・ツール・PoC 等）なら節ごと省いてよい
- ディレクトリ構造 — repo と文書の配置を示す。置き場は `prd` skill に従う。
- セットアップ — mise + 起動・ビルド・テスト・lint コマンド
- 技術スタック — 言語・フレームワーク・主要ライブラリ
- Skills — `.agents/skills/` や `docs/` への参照を「いつ load するか」の trigger として 1 行ずつ

文書の配置は `{docs|.agent}/prd/<topic>/{prd|dd}.md` で示す。
`docs/` は共有文書として Git で管理する。`.agent/` は個人メモとして Git の管理対象から外す。
選んだ方を描き、PRD と必要な DD を同じ topic 配下にまとめる。

## index としての規約

- 詳細（知見・ハマりどころ・手順書）を本文に溜めない。置き場は `.agents/skills/<topic>/` または `docs/` に作り、AGENTS.md には load trigger の 1 行だけ書く
- skill を新設・追記して自動発火しないものは、ここに trigger を足す。description の発火語で自動発火する skill には index 不要
- ディレクトリ・コマンド・技術スタックが変わったら、AGENTS.md も同時に更新する。

## CLAUDE.md

```markdown
read @AGENTS.md
```

この1行のみ。AGENTS.md が正本で、CLAUDE.md はそれを読まない agent（Claude Code 等）への転送役。Devin は両方読むので内容を重複させない。
