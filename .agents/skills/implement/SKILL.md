---
name: implement
description: "PRDまたは実装タスクを実装する。「実装して」「このPRDを実装」「機能追加」「不具合を修正」で使う。実装後は自身でpr skillへ進み、draft PR後のsubagentのQAとself reviewを並行する。"
user-invocable: true
---

# Implement

開発フローは prd → implement → pr → pr-auto-merge。このskillは実装・self reviewとテスト方針を担当し、E2E/APIのQAはdraft PR作成後にpr skillで進める。部分タスクを分担した場合、PR作成は全体を進めるagentが担当する。

## 記述方針

コードには How、テストコードには What、コミットログには Why、コードコメントには Why not を書く。コードコメントに自明なことは書かない。document コメントは JSDoc / GoDoc など言語標準の記法を使う。

## 流れ

1. **PRDまたは実装タスクを受け取る。** 今回の目的・範囲・期待する振る舞いを確認する。PRDがあれば着手時に `status: in-progress` にする。
2. **実装する。** 対象repoの規約と既存コードを踏まえて進める。実装方法は細かく指定しない。
3. **実装完了後に、自身でPRへ進む。** [pr](../pr/SKILL.md) でdraft PRを作成し、previewなど対象環境でsubagentのE2E/APIテストを進める。その間に実装担当はself reviewし、[ce-simplify-code](../ce-simplify-code/SKILL.md) でコードも見直す。
4. **対話して修正し、再テストする。** 仕様に書かれていない点やQAで見つかった疑問は、実装担当とQA担当のコミュニケーションで確認・整理する。ユーザーの判断が必要な点はユーザーに確認する。製品・テストを必要に応じて修正し、self reviewと修正が終わったコードで再テストして、pr skillのreadyまで進める。

PRD全体の実装が完了し、必要なテストが成功したら `status: done` にし、日本語版があればstatusを揃える。文書など実操作の対象がない変更は、その理由と実施した確認をPRに記録する。

## テスト方針

- 優先度は **E2E → APIテスト → unit test**。対象の公開入口に合わせて選び、既存テストを再利用する。
- E2Eは今回の変更に関連する箇所だけ、必要最小限で実行する。mainでフルE2Eを実行しており、実行コストも高いため。
- 基本はブラックボックステスト。利用者から観測できる入力と結果を確認する。
- **unit testは最小限**。対象は複雑な計算やドメインルール。
  - UIのunit/component test（componentのrender・snapshot、UI用hookなど）は書かなくてよい。UIの振る舞いはE2Eで確認する。
  - APIテストで確認できる振る舞いを、handler・service・repositoryの各レイヤーで重複してunit testしない。
  - privateな関数やmockを使ったテストは行わない。
- E2E/APIテストは対象repoのe2eを使う。まだなければ `e2e init` を実行する。
- 共有 skill（`~/.agents/skills/` 側）を repo に複製しない。環境依存の設定（model・API key・runner flag）は repo 側の runner 設定に書き、skill 本体は共有のまま参照する — 複製すると update で upstream から取り残される
