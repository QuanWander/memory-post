# -*- coding: utf-8 -*-
"""记忆源、状态与生成的测试。"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost.composer import compose
from mempost.config import DEFAULT
from mempost.privacy import PrivacyGuard
from mempost.sources import diary_digest, load_diary, load_memories
from mempost.state import Store


class SourcesTest(unittest.TestCase):
    def test_memory(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "memory.json"
            p.write_text(json.dumps({"entries": [{"text": "买了洗衣机"}, {"text": ""}]}, ensure_ascii=False), encoding="utf-8")
            items = load_memories(p)
            self.assertEqual([m.text for m in items], ["买了洗衣机"])

    def test_memory_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "memory.json"
            p.write_text("{broken", encoding="utf-8")
            self.assertEqual(load_memories(p), [])

    def test_diary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "2026-11-02_私聊.md").write_text("# 标题\n今天吃了粉\n", encoding="utf-8")
            (root / "2026-11-01_日记.md").write_text("# 标题\n昨天买了洗衣机\n", encoding="utf-8")
            entries = load_diary(root, days=2)
            self.assertEqual(len(entries), 2)
            self.assertTrue(entries[0].day >= entries[1].day)
            self.assertIn("今天吃了粉", diary_digest(entries))


class StateTest(unittest.TestCase):
    def test_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.json")
            store.add_post("今天食堂的粉很烫", fid="abc")
            store.add_draft("草稿内容")
            self.assertEqual(len(store.posts()), 1)
            self.assertEqual(len(store.drafts()), 1)
            self.assertEqual(store.recent_texts(), ["今天食堂的粉很烫"])


class FakeLLM:
    def __init__(self, texts):
        self.texts = list(texts)

    def chat(self, messages, **kwargs):
        return self.texts.pop(0)


class ComposerTest(unittest.TestCase):
    def test_compose(self):
        cfg = dict(DEFAULT)
        cfg["privacy"] = dict(DEFAULT["privacy"])
        cfg["privacy"]["min_chars"] = 5
        cfg["privacy"]["max_chars"] = 50
        guard = PrivacyGuard(entities=["示例职校"], deny_words=["主人"])
        from mempost.sources import Memory

        result = compose(
            cfg,
            persona="你是小鲸鱼。",
            variant={"name": "小鲸鱼", "desc": "蓝白配色"},
            memories=[Memory("买了洗衣机"), Memory("示例职校今天监考")],
            diary_text="",
            recent_posts=[],
            guard=guard,
            llm=FakeLLM(["“洗衣机转起来的时候，我蹲在旁边看了半天。”"]),
        )
        self.assertNotIn("“", result.text)
        self.assertNotIn("示例职校", result.used_memories)

    def test_retry_on_privacy(self):
        cfg = dict(DEFAULT)
        cfg["privacy"] = dict(DEFAULT["privacy"])
        cfg["privacy"]["min_chars"] = 5
        cfg["privacy"]["max_chars"] = 50
        guard = PrivacyGuard(entities=["示例职校"], deny_words=[])
        from mempost.sources import Memory

        result = compose(
            cfg,
            persona="你是小鲸鱼。",
            variant={"name": "小鲸鱼", "desc": "蓝白配色"},
            memories=[Memory("买了洗衣机")],
            diary_text="",
            recent_posts=[],
            guard=guard,
            llm=FakeLLM(["今天在示例职校监考站了一天", "洗衣机转起来的时候我蹲在旁边看"]),
        )
        self.assertNotIn("示例职校", result.text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
