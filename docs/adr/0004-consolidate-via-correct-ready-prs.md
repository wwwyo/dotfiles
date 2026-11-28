# 学び還元を repo ごとの correct に任せ、PR を ready で出す

Status: superseded（2026-11-28 に session-consolidate の automation をユーザー判断で削除した）

ADR 0003 の session-consolidate は、専用の SKILL.md と consolidator prompt で学習候補を束ね、repo ごとに draft PR を出して人間のレビューを待つ batch だった。2026-11-27 に wwwyo/skills を pstack の粒度に揃えたのに合わせて、次のように変える（ユーザー判断）。

- batch 専用の手順書をやめ、手順の正本を automation の prompt にする。repo ごとの worker は wwwyo/skills の `correct` skill を実行し、学習候補を「繰り返されたミス」の証拠として使う。Langfuse・lock・sentinel・`consolidated` score は既存の helper（`session_consolidate.py`）をそのまま使う
- PR は draft ではなく ready で出し、pr-auto-merge の定期 lane の対象にする。採否の最終判断は、人間のレビュー待ちから merge lane の judge（QA・Blast Radius の基準）に移る
- worker は従来どおり delegate の worker/personal のモデルを明示して起動する（非公開 session の記録を扱うため）
- 1 session の学びを複数 repo に配る `multi_dest` と、誤った割り当ての収束ルールはやめる。session は 1 つの repo に割り当て、宛先が決まらなければ wwwyo/me に回す

理由: 還元の手順を pstack の汎用 skill（correct・opening-a-pr）に寄せ、batch 固有の長い手順書を保守しないため。draft のまま溜まった学び PR は読まれにくく、merge lane の判定で十分に止められる。

ADR 0003 のうち、eval と還元を別 batch に分ける判断・対象 predicate・`consolidated` の値の決め方は引き続き有効。
