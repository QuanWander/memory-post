# -*- coding: utf-8 -*-
"""隐私过滤与文本检查的测试。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost.lint import lint
from mempost.privacy import PrivacyGuard, normalize


class PrivacyTest(unittest.TestCase):
    def setUp(self):
        self.guard = PrivacyGuard(entities=["示例职校", "王老师", "1000000001"], deny_words=["主人", "学生名单"])

    def test_phone(self):
        self.assertTrue(self.guard.scan("有事打 13812345678"))

    def test_qq_context(self):
        self.assertTrue(self.guard.scan("我 QQ 是 123456789"))

    def test_long_number(self):
        self.assertTrue(self.guard.scan("学号 2026012345"))

    def test_entity(self):
        self.assertTrue(self.guard.scan("今天在示例职校监考"))

    def test_deny_word(self):
        self.assertTrue(self.guard.scan("主人今天买了个洗衣机"))

    def test_clean(self):
        self.assertFalse(self.guard.scan("今天食堂的粉很烫，吹了半天才吃上"))

    def test_normalize(self):
        self.assertEqual(normalize("  a\u200b b  "), "a b")


class LintTest(unittest.TestCase):
    def setUp(self):
        self.guard = PrivacyGuard(entities=["示例职校"], deny_words=["主人"])

    def test_ok(self):
        issues = lint("今天食堂的粉很烫，吹了半天才吃上", self.guard)
        self.assertFalse([i for i in issues if i.code != "too_short"])

    def test_too_short(self):
        self.assertIn("too_short", [i.code for i in lint("嗯", self.guard)])

    def test_too_long(self):
        text = "今天" + "很长的句子" * 20
        self.assertIn("too_long", [i.code for i in lint(text, self.guard)])

    def test_markdown(self):
        text = "**今天**食堂的粉很烫，吹了半天才吃上"
        self.assertIn("markdown", [i.code for i in lint(text, self.guard)])

    def test_link(self):
        text = "今天食堂的粉很烫，链接 https://example.com 别点"
        self.assertIn("link", [i.code for i in lint(text, self.guard)])

    def test_privacy(self):
        text = "今天示例职校的粉很烫，吹了半天才吃上"
        self.assertIn("privacy_entity", [i.code for i in lint(text, self.guard)])

    def test_duplicate(self):
        text = "今天食堂的粉很烫，吹了半天才吃上"
        issues = lint(text, self.guard, recent=["今天食堂的粉很烫，吹了半天才吃上"])
        self.assertIn("duplicate", [i.code for i in issues])


if __name__ == "__main__":
    unittest.main(verbosity=2)
