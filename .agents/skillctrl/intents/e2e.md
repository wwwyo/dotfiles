# e2e

## 文脈

e2e は PRD の criterion を検証する QA の実行基盤として使う。PR ごとの
変更範囲の QA と、main の広い回帰テストを分けたい。ここは汎用 skill の
管理 repo であり、テスト対象のアプリそのものではない。

## 意図

モデルの既定は OpenCode Go とする。安価な open model を選び、UI 操作に
必要な画像入力・ツール呼び出しを確認する。キーは既存の秘密管理から受け取り、
Vercel のログインや Gateway の設定を通常のセットアップの前提にしない。
安価な Claude の具体例には Haiku 5.5 を使い、接続先に合ったモデル ID と
認証方式を示す。ChatGPT のサブスク認証でこのモデルを呼ぶ案内を置かない。
Go のエンドポイントとクライアント識別・session header を明示する。
モデル名は共通環境変数から取得し、templateの固定fallbackとの二重管理を避ける。

モデル能力の診断と証跡の秘密混入検査は共有 helper に持つ。診断は対象 project の
config のモデルと導入済み SDK を使い、project 固有の import・transport や
helper 側のモデル既定を持たない。SDK payload や秘密値を出力せず、検査不能な
証跡は成功と扱わない。実アプリの QA と画像内容の目視確認は別に必要。

TesterArmy への telemetry と feedback の自動送信を行わない。明示的な
opt-out を初回起動・MCP・CI にも適用し、上流の feedback 指示を復活させない。
モデルへの推論リクエストとローカル保存は telemetry と区別して説明する。

CLI の管理、package のバージョン固定・cooldown、汎用 skill の管理は repo の
共通規約に従う。init の既定値でこの適応を上書きしたり、複数の agent client に
MCP を無差別登録したりしない。導入済みバージョンの guide を確認する。

テスト実行を stateless に保つ。必要なデータを通常のユーザー操作で作成・検証・
削除し、前回の残存データを成功条件にしない。テストアカウント、実行証跡、cache、
長期の QA 知識はそれぞれの役割で保持する。固定操作と正確な assertion を活用し、
agent の判断が必要な箇所に agent step を使う。cache の再生は検証の省略を意味しない。
