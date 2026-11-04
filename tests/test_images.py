# -*- coding: utf-8 -*-
"""图片 provider 的测试（不发网络请求）。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost.images import _pick_image, _suffix, build_prompt, generate, resolve_base


class ImagesTest(unittest.TestCase):
    def test_none(self):
        self.assertEqual(generate("x", {"images": {"provider": "none"}}, "."), "")

    def test_unknown(self):
        with self.assertRaises(RuntimeError):
            generate("x", {"images": {"provider": "nope"}}, ".")

    def test_presets(self):
        self.assertIn("ark.cn-beijing", resolve_base({"images": {"provider": "doubao"}}))
        self.assertIn("dashscope", resolve_base({"images": {"provider": "qwen"}}))
        self.assertEqual(resolve_base({"images": {"provider": "doubao", "base_url": "http://x"}}), "http://x")

    def test_pick_image(self):
        self.assertEqual(_pick_image({"data": [{"b64_json": "x"}]}), ("x", "b64"))
        self.assertEqual(_pick_image({"data": [{"url": "http://a"}]}), ("http://a", "url"))
        self.assertEqual(_pick_image({"choices": [{"message": {"images": ["http://b"]}}]}), ("http://b", "url"))

    def test_suffix(self):
        self.assertEqual(_suffix(b"\x89PNG\r\n"), ".png")
        self.assertEqual(_suffix(b"\xff\xd8\xff"), ".jpg")
        self.assertEqual(_suffix(b"RIFF0000WEBP"), ".webp")

    def test_prompt(self):
        text = build_prompt("自拍", "小鲸鱼：蓝白配色")
        self.assertIn("小鲸鱼", text)
        self.assertIn("自拍", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
