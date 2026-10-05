# ローカル追記

upstream: https://github.com/Nutlope/hallmark （取り込み rev は `.upstream-rev`）

upstream を更新するときは以下を再適用する。

## 1. anti-slop クラスタの警告（2026-08-14 追加）

Anthropic の `frontend-design` skill を hallmark に一本化した際、hallmark 側に無かった唯一の内容を移植した。

- `references/anti-patterns.md` § The anti-slop cluster（Critical、"The AI nav" の直前）
- `SKILL.md` 全 verb 共通 discipline **7**（"six disciplines" → "seven" も併せて）

**Why:** hallmark は「AI っぽさ」の山を名指しして避ける skill だが、その回避先そのものが新しい山になっている。`references/custom-theme.md` の worked example が warm-cream + terracotta + Fraunces italic で、これは frontend-design が「2026 年の AI デフォルト3種」の1つとして名指ししていたもの。hallmark 自身はこの自己言及に気づいていない（`Specimen fall-through` gate で部分的には自覚しているが、色とフォントの軸は素通し）。

upstream がこの警告を自前で入れたら、この追記は消してよい。
