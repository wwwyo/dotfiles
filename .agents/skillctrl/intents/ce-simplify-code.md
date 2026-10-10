# ce-simplify-code

## 文脈

この環境のレビューは subagent の独立コンテキストで行う前提で運用している。実装した agent 自身が同じコンテキストでレビューすると独立性が失われる。upstream は subagent primitive が無い・失敗した場合に inline / 順次実行へ切り替える設計になっている。

## 意図

レビュー pass の実行は platform 自身の subagent primitive（Claude Code の Agent/Task、Codex の spawn_agent、pi の pi-subagents extension の subagent）への dispatch のみに限定する。Orca 経由の別 session 起動や delegate skill のモデル選択表には依存しない。primitive が無い・dispatch が回復不能な場合でも自分で inline に代替実行せず、失敗を報告して止まる。
