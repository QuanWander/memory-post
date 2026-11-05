# -*- coding: utf-8 -*-
"""模型系列解析的测试。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost.composer import choose_latest_model


class ModelTest(unittest.TestCase):
    def test_flash_alias(self):
        models = [
            {"id": "deepseek-flash", "name": "DeepSeek-V4.1-Flash"},
            {"id": "deepseek-v5-flash", "name": "DeepSeek-V5-Flash"},
        ]
        self.assertEqual(choose_latest_model(models, "flash"), "deepseek-flash")

    def test_pro_latest(self):
        models = [
            {"id": "deepseek-v4-pro", "name": "DeepSeek-V4-Pro"},
            {"id": "deepseek-v5-pro", "name": "DeepSeek-V5-Pro"},
        ]
        self.assertEqual(choose_latest_model(models, "pro"), "deepseek-v5-pro")

    def test_ignore_embedding(self):
        models = [
            {"id": "deepseek-v4-pro", "name": "Pro"},
            {"id": "deepseek-embedding-pro", "name": "Embedding"},
        ]
        self.assertEqual(choose_latest_model(models, "pro"), "deepseek-v4-pro")

    def test_empty(self):
        self.assertEqual(choose_latest_model([], "pro"), "")


if __name__ == "__main__":
    unittest.main(verbosity=2)
