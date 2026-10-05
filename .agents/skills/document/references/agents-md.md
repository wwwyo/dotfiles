# AGENTS.md ガイドライン

repo の起動時 index。agent が無条件で読むファイルなので、構造と参照先だけを持ち、詳細な知見・手順は置かない。

## 構成

テンプレートは `assets/agents-md.md`。

- Story — 書き方と要否の判定は `prd` skill の `references/story-format.md` に従う。プロダクトの story が無い段階（ライブラリ・ツール・PoC 等）なら節ごと省いてよい
- ディレクトリ構造 — repo の構造と文書の配置規約。`{docs|.agent}/prd/<topic>/{prd|dd}.md` の構造を描く。`docs/` は共有・tracked、`.agent/` は個人メモ・gitignore。選んだ方を描き、PRD と必要な場合の DD は同じ topic 配下にまとめる。置き場の規約は `prd` skill を参照する
- セットアップ — mise + 起動・ビルド・テスト・lint コマンド
- 技術スタック — 言語・FW・主要ライブラリ
- Skills — `.agents/skills/` や `docs/` への参照を「いつ load するか」の trigger として 1 行ずつ

## index としての規約

- 詳細（知見・ハマりどころ・手順書）を本文に溜めない。置き場は `.agents/skills/<topic>/` または `docs/` に作り、AGENTS.md には load trigger の 1 行だけ書く
- skill を新設・追記して自動発火しないものは、ここに trigger を足す。description の発火語で自動発火する skill には index 不要
- 構造（dir・コマンド・スタック）が変わったら AGENTS.md も同時に更新する。起動時 index の腐敗は全作業に効く

## CLAUDE.md

```markdown
read @AGENTS.md
```

この1行のみ。AGENTS.md が正本で、CLAUDE.md はそれを読まない agent（Claude Code 等）への転送役。Devin は両方読むので内容を重複させない。
