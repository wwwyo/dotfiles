# design-md スキル

手書きでカスタマイズ済み。upstream 更新の対象外（root の `skills-lock.json` に非記載）。

## Example Prompt

```text
このプロダクトのデザインシステムを起こして、design.md を作って。
```

## Skill Structure

```text
design-md/
├── SKILL.md           — Core instructions & workflow
├── examples/          — design.md の実例（日本語UI）
├── tools/             — design-md-check.py / page-check.py 等、design.md の決定論チェック（正本）
└── README.md          — This file
```

## How it Works

1. Divergence: デフォルトは 0 から設計する — `prototype` で大枠の UI/UX（構図・密度・雰囲気）の違う案を3〜4つ出して人間が1つ選ぶ。prototype の値は抽出しない（方向の選択だけに使う）
2. Design: 選ばれた方向を brief に、tokens・font・icon library・logo 規約を一から設計する。logo は幾何学（黄金比を含む比率候補）で組んだ symbol 候補 → 人間の選択 → wordmark 候補 → 人間の選択 → tracking / ペア別 kerning の調整パネル、の順で進め、字幅・字間・光学的バランスは数値揃えでなく作者自身が実サイズと拡大表示で目視確認する。prototype を re-skin して人間に合意を取った後 `hallmark` で監査する。対象が日本語UIならフォールバックチェーン・行間・字間・禁則処理・OpenType機能も設計に含める
3. Extraction mode: ライブURL・ローカルのコード・Figma を明示指定されたときだけ、既存プロダクトから実数値を抽出して同じ design.md に落とす（目測禁止・出所を Notes に記録）
4. Synthesis: 対象 repo の root に `design.md`（System + Tokens + Components + Icons + Logo + Motion + Exports）を生成する。既存の design.md がある場合は上書きせず、format が持つ節だけを更新する。語彙は shadcn/ui 規約の `-foreground` ペア
5. Validate: `tools/design-md-check.py`（この skill 同梱 — consumer はコピーせずここを参照して実行する）で検証し、error 0 を確認してから提示
6. 出力先: repo root 固定。product-design skill や Hallmark など複数の reader が同じ正本を読むため — 配置規約は [skill-structure/templates/product-design.md](../skill-structure/templates/product-design.md) の「値の層」節を参照
