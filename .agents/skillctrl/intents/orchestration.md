# orchestration

## 文脈

Orca worker の監督と、通常操作・所有権の引き渡しでは必要な手順が異なる。

## 意図

description は dispatch・質問応答・完了待ち・結果統合を示す。通常操作と全権引き渡しは orca-cli へ示し、実際の Orca runtime を使う規約は維持する。
