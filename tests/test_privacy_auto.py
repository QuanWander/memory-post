# -*- coding: utf-8 -*-
"""自动隐私判断的测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost.privacy_auto import discover, judge


class FakeLLM:
    def __init__(self, replies):
        self.replies = list(replies)

    def chat(self, messages, **kwargs):
        return self.replies.pop(0)


class PrivacyAutoTest(unittest.TestCase):
    def test_discover(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "entities.json"
            llm = FakeLLM(['["示例职校", "张三"]'])
            items = discover(llm, ["在示例职校监考"], "今天张三来了", cache)
            self.assertEqual(items, ["示例职校", "张三"])
            self.assertTrue(cache.exists())

    def test_discover_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "entities.json"
            discover(FakeLLM(['["示例城"]']), [], "", cache)
            # 第二次不该再调模型（Fake 没有可弹出的回复）
            self.assertEqual(discover(FakeLLM([]), [], "", cache), ["示例城"])

    def test_judge_safe(self):
        self.assertEqual(judge(FakeLLM(['{"safe": true, "hit": []}']), "今天食堂的粉很烫"), [])

    def test_judge_hit(self):
        self.assertEqual(
            judge(FakeLLM(['{"safe": false, "hit": ["示例职校"]}']), "今天在示例职校监考"),
            ["示例职校"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
