# -*- coding: utf-8 -*-
"""v0.3：草稿编辑、写法、无素材判断。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost.composer import ANGLE_MAP, compose
from mempost.privacy import PrivacyGuard
from mempost.service import has_material
from mempost.sources import Memory
from mempost.state import Store


class FakeLLM:
    def __init__(self, text: str):
        self.text = text

    def chat(self, messages, **kwargs):
        return self.text


class DraftTest(unittest.TestCase):
    def test_update_and_replace(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.json")
            draft = store.add_draft("旧句子", used=["记忆一"], angle="action", angle_label="具体动作")
            updated = store.update_draft(draft["id"], text="新句子")
            self.assertEqual(updated["text"], "新句子")
            replaced = store.replace_draft(draft["id"], "换写法", used=["记忆二"], angle="object", angle_label="借物喻人")
            self.assertEqual(replaced["text"], "换写法")
            self.assertEqual(replaced["angle"], "object")
            self.assertEqual(len(store.drafts()), 1)


class AngleTest(unittest.TestCase):
    def test_requested_angle(self):
        cfg = {"privacy": {"min_chars": 18, "max_chars": 80}}
        text = "楼道灯坏了两天，今晚有人搬椅子垫脚换灯泡，我趴在门上看，没出声。"
        result = compose(
            cfg,
            "你是小鲸鱼。",
            {"name": "日常", "desc": "随手写"},
            [],
            "",
            [],
            PrivacyGuard([], []),
            llm=FakeLLM(text),
            angle_id="object",
        )
        self.assertEqual(result.angle_id, "object")
        self.assertEqual(result.angle_label, ANGLE_MAP["object"]["label"])


class MaterialTest(unittest.TestCase):
    def test_blocked_memory_is_not_material(self):
        guard = PrivacyGuard(["示例学校"], [])
        self.assertFalse(has_material([Memory(text="示例学校今天考试")], [], guard))
        self.assertTrue(has_material([Memory(text="今天风很大")], [], guard))


if __name__ == "__main__":
    unittest.main(verbosity=2)
