"""comment の「session が存在しない」判定が 404 全般を握らないことの回帰テスト。

SESSION 行を持たない session (turn obs が無く generation だけ) は comments API が
404 を返すため skip して evaluated_until だけ書く。判定を広げると base URL や
path の誤りでも同じ経路に落ち、全 session の記録が無音で消える。
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import session_eval as se  # noqa: E402

SID = "01a17d2b-dc1a-7792-9c45-cb562a4fee19"
NOT_FOUND = json.dumps({
    "message": f"Reference object, SESSION: {SID} not found. "
               "Skipping comment creation."})


def err(msg):
    return se.ApiError(msg)


class CommentMissingSessionTest(unittest.TestCase):
    def test_langfuse_not_found_for_sid_is_skippable(self):
        e = err(f"POST /api/public/comments -> 404: {NOT_FOUND}")
        self.assertTrue(se._comment_missing_session(e, SID))

    def test_404_for_other_sid_is_not_skippable(self):
        # 別 session の 404 を握ると取り違えが無音化する
        e = err(f"POST /api/public/comments -> 404: {NOT_FOUND}")
        self.assertFalse(se._comment_missing_session(e, "01a18000-0000-7000-8000-000000000000"))

    def test_bare_404_is_not_skippable(self):
        # path 誤り・base URL 誤りでも 404 は返るので fail-loud のままにする
        for msg in (
            "POST /api/public/comments -> 404: Not Found",
            "POST /api/public/comments -> 404: {}".format(
                json.dumps({"message": "not found"})),
            f"POST /api/public/comments -> 404: {SID}",
            f"POST /api/public/comments -> 500: {NOT_FOUND}",
            f"POST /api/public/comments -> 400: {NOT_FOUND}",
        ):
            with self.subTest(msg=msg):
                self.assertFalse(se._comment_missing_session(err(msg), SID))

# 実 API に触れる経路 (404 を返させて archive が作られるか) は
# tests/session-eval.test.sh の冒頭方針どおり対象外 — 手で 1 回確認した:
#   python3 session_eval.py comment --session-id <存在しない sid> \
#     --content-file <file>  -> {"ok": true, "skipped": "session_not_found",
#                               "archived": ".../skipped/<sid>-<ts>.md"}


if __name__ == "__main__":
    unittest.main()
