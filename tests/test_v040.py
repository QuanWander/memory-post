# -*- coding: utf-8 -*-
"""v0.4：隐私报告与草稿详情。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost.lint import Issue
from mempost.state import Store


class IssueTest(unittest.TestCase):
    def test_sources(self):
        self.assertEqual(Issue("privacy_entity", "x").to_dict()["source"], "entity")
        self.assertEqual(Issue("privacy_phone", "x").to_dict()["source"], "regex")
        self.assertEqual(Issue("privacy_llm", "x").to_dict()["source"], "llm")
        self.assertEqual(Issue("duplicate", "x").to_dict()["source"], "similarity")
        self.assertEqual(Issue("too_short", "x").to_dict()["source"], "length")


class DetailsTest(unittest.TestCase):
    def test_draft_details(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.json")
            details = [{"code": "privacy_entity", "detail": "命中 示例学校", "source": "entity"}]
            draft = store.add_draft("测试", issues=["命中"], details=details)
            self.assertEqual(store.get_draft(draft["id"])["details"], details)


if __name__ == "__main__":
    unittest.main(verbosity=2)
