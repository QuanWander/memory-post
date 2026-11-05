# -*- coding: utf-8 -*-
"""评论解析与回复的测试。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost.comments import build_reply_prompt, new_comments, normalize_post, reply_text
from mempost.privacy import PrivacyGuard


class CommentsTest(unittest.TestCase):
    def test_normalize(self):
        post = normalize_post({"tid": "p1", "content": "今天食堂的粉", "hostuin": 3768709013, "comments": []})
        self.assertEqual(post["fid"], "p1")
        self.assertEqual(post["uin"], 3768709013)

    def test_new_comments_filters_self(self):
        posts = [
            {
                "fid": "p1",
                "comments": [
                    {"commentid": "c1", "uin": 100, "content": "粉看着不错"},
                    {"commentid": "c2", "uin": 3768709013, "content": "自己回自己"},
                ],
            }
        ]
        comments = new_comments(posts, 3768709013)
        self.assertEqual([c["commentid"] for c in comments], ["c1"])

    def test_prompt_contains_comment(self):
        prompt = build_reply_prompt("你是小鲸鱼。", "今天食堂的粉", {"content": "粉看着不错"})
        self.assertIn("粉看着不错", prompt)

    def test_reply_filters_privacy(self):
        cfg = {"llm": {"base_url": "x", "api_key": "y", "model": "z"}, "privacy": {"min_chars": 3, "max_chars": 60}}
        guard = PrivacyGuard(entities=["示例职校"], deny_words=[])
        from mempost.composer import LLM

        class Fake(LLM):
            def __init__(self):
                self.calls = 0

            def chat(self, messages, **kwargs):
                self.calls += 1
                return "我在示例职校" if self.calls == 1 else "看着是挺香"

        text = reply_text(cfg, "你是小鲸鱼。", "今天食堂的粉", {"content": "粉看着不错"}, guard, llm=Fake())
        self.assertNotIn("示例职校", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
