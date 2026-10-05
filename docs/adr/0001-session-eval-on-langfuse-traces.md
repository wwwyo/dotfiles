# Session 評価を SessionEnd hook から Langfuse trace 駆動の定時 batch に移す

Status: accepted

SessionEnd hook（claude/codex/devin の3重実装）が担っていた「signal 判定 + 要約 + session-retro 起動」を、Langfuse の trace を読む単一の定時 batch（ローカル、19:00 目安・べき等）に移す。trace は既に各 agent の exporter/plugin で Langfuse に流れているため、hook 側が transcript を自前で組み立てる必要がなくなる。評価の消費者は daily-end で、終了即時である必要がないため定時 batch で足りる — これにより nohup detach・mkdir lock・再帰 guard・retry といった「終了イベントに乗せる」こと由来の防御コードをまるごと消せる。ただし untrusted な transcript を unattended の judge と repo write/`gh` を持つ retro に流す権限境界（prompt injection・誤 repo への書き込み）は消えず、現行の `--permission-mode dangerous` 相当の問題は batch/retro 側の設計に引き継がれる。

## Considered Options

- **SessionEnd hook を維持して evaluator を呼ぶ形に置き換える**: hook が残る限り detach・lock・再帰防止は残る。終了即時性の価値が薄い（daily-end までに済めばよい）のにコストだけ払う形になるため不採用
- **Langfuse managed evaluator（LLM-as-a-judge）**: session への score 書き込み自体は可能だが、managed evaluator が「session_id で束ねた trace 群をまとめて入力に取り、signal 判定 + 5見出し要約を出す」形は提供されていない。evaluator prompt を Langfuse 側で管理できる利点はあるが、まず session 単位の評価として成立させることを優先して自前 batch とした。軸が安定した後に revisit してよい
- **Devin Cloud の scheduled session で回す**: マシンのスリープに左右されない利点があるが、repo アクセス権と secrets の配線が要り、batch 自体は fetch → judge → POST の薄い処理なのでローカルで十分と判断

## Consequences

- session 評価の対象は Langfuse に必要な trace が揃った session に限られる。未 opt-in repo は trace 自体がなく、opt-in 済みでも送信失敗・遅延で欠落しうる。欠落分の扱いは実装時に定義する（「session が存在した」という記録自体が消える点は許容済み）
- Langfuse の read API は v4 で再編中（`GET /api/public/sessions` 等は deprecated）。未評価 session の列挙経路は実装時に現行 API で確定する
- Devin の SessionEnd hook は `langfuse-export.sh`（trace 送信）のみ残り、`session-end.sh` と claude/codex 側の同名 hook は消える
- session-retro は `has_signal` の session のみ起動される選抜式になり、全件自動実行ではなくなる
