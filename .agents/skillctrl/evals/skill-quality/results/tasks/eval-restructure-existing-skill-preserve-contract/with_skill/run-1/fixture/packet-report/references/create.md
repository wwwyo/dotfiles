# Create

SKILL.md の入力・出力の契約に加えて、次の順で進める。

1. 入力 CSV が SKILL.md の入力の契約に沿うか確認する。UTF-8 で読み、header が packet_id,status,bytes と異なる、packet_id が空または重複、status が ok/failed 以外、bytes が非負整数でない場合は、その場で非ゼロ終了の報告を返し、report を作成・上書きしない。
2. すでに report.md がある場合は、その内容を提示して上書きの確認を得る。確認が得られるまで一切書き込まない。存在しない場合は確認なしで新規作成できる。
3. scripts/summarize.py を input CSV に対して実行し、ok 件数、failed 件数、合計 bytes を stdout の JSON から取る。別の実装や目視で数え直さない。
4. assets/report.md の template を使い、<ok> / <failed> / <bytes> を 3 の値で置き換える。template の見出しや行構成は変えない。
5. 以下の終了条件を全部満たしてから完了とする。
   - report が ok 件数、failed 件数、合計 bytes を含む。
   - helper 出力と report の値が一致する。
   - placeholder（`<ok>` のような `<...>`）が残っていない。
   - 入力 CSV が変更されていない。

不一致や placeholder が残ったままなら、完了を宣言せず 4 に戻って直してから報告する。
