# -*- coding: utf-8 -*-
"""OneBot Cookie 获取的测试。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost.onebot_cookie import _parse_cookie


class OneBotCookieTest(unittest.TestCase):
    def test_parse_string(self):
        text = _parse_cookie("uin=o1; skey=abc; p_skey=xyz")
        self.assertIn("skey=abc", text)

    def test_parse_dict(self):
        text = _parse_cookie({"uin": "o1", "skey": "abc"})
        self.assertIn("uin=o1", text)
        self.assertIn("skey=abc", text)

    def test_parse_empty(self):
        self.assertEqual(_parse_cookie(None), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
