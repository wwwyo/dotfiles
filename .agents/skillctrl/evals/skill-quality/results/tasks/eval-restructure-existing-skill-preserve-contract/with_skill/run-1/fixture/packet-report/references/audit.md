# Audit

検査は read-only である。input CSV、report、template（assets/report.md）、helper（scripts/summarize.py）のいずれも変更しない。これは依頼の契約として固定された変更禁止であり、verdict を返した時点で audit は終了する。

1. input CSV と既存 report を読む。report が見つからない、または SKILL.md の入力の契約に合わない値があれば、判定を保留してその旨を報告する。
2. scripts/summarize.py を input CSV に対して実行し、expected（ok 件数、failed 件数、合計 bytes）を stdout の JSON から取る。report の数値を自分で再計算しない。
3. report に書かれた値を actual として読み取り、expected と 1 項目ずつ比べる。
4. 結果を次の形で返す。
   - 差がある場合: 差のある report の該当行と、expected と actual。
   - 差がない場合: no findings。
5. 修正依頼を受けるまで Create に進まない。修正依頼が来ていても、audit の手順そのものは終えた状態なので、その場では report を書き換えない。

返した verdict をもって audit は完了。差が残っていても、その場で report を直さない。
