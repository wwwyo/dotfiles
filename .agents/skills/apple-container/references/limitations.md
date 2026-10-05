Paths in commands are relative to the skill root (the directory containing `SKILL.md`), unless stated otherwise.

## 既知の制限

- ホストへのメモリ返却が部分的: Linux 側で free されたメモリが macOS まで返らないことがある。長時間動かしていると Activity Monitor で大きく見える。多数のメモリ集約型コンテナを動かしたら定期的に再起動する。
- 匿名ボリュームは `--rm` で消えない: 明示的に `container volume rm` する。
- macOS 15 ではコンテナ間通信・マルチネットワーク・`container network` がすべて使えない。
