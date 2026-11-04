# -*- coding: utf-8 -*-
"""独立发布器的本地测试（不发网络请求）。"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost.publish import qzone_native


class NativeTest(unittest.TestCase):
    def test_cookie_parse(self):
        cfg = {"publish": {"qzone_cookie": "uin=o3768709013; skey=abc; p_skey=xyz"}}
        _, uin = qzone_native.load_cookie(cfg)
        self.assertEqual(uin, 3768709013)

    def test_cookie_missing(self):
        with self.assertRaises(qzone_native.QzoneNativeError):
            qzone_native.load_cookie({"publish": {}})

    def test_extract_comments(self):
        raw = {
            "commentlist": [
                {"commentid": "c1", "uin": 100, "content": "好吃", "name": "阿明"},
                {"commentid": "c2", "uin": 101, "content": "饿了", "name": "小红"},
            ]
        }
        items = qzone_native._extract_comments(raw)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["uin"], 100)
        self.assertEqual(items[1]["name"], "小红")

    def test_publish_fake(self):
        class Fake:
            photos = None

            async def publish_mood(self, content, photos=None):
                self.photos = photos
                return {"data": {"tid": "t1"}}

        fake = Fake()
        old = qzone_native._client
        qzone_native._client = lambda cfg: (fake, 1)
        try:
            result = qzone_native.publish({"publish": {}}, "测试说说", media=["a.png"])
        finally:
            qzone_native._client = old
        self.assertEqual(result["fid"], "t1")
        self.assertEqual(fake.photos, [{"path": "a.png"}])

    def test_extract_nested(self):
        raw = {"data": {"comments": [{"commentid": "x", "commentUin": 7, "content": "嗯"}]}}
        items = qzone_native._extract_comments(raw)
        self.assertEqual(items[0]["commentid"], "x")
        self.assertEqual(items[0]["uin"], 7)


if __name__ == "__main__":
    unittest.main(verbosity=2)
