# -*- coding: utf-8 -*-
"""配置与调度的测试。"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mempost import config as cfgmod
from mempost.scheduler import next_run


class ConfigTest(unittest.TestCase):
    def test_merge(self):
        merged = cfgmod._merge(cfgmod.DEFAULT, {"privacy": {"min_chars": 5}})
        self.assertEqual(merged["privacy"]["min_chars"], 5)
        self.assertEqual(merged["privacy"]["max_chars"], 80)

    def test_resolve_relative(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = {"memory_file": "data/memory.json"}
            path = Path(tmp) / "config.json"
            self.assertEqual(cfgmod.resolve(cfg, "memory_file", path), str((Path(tmp) / "data" / "memory.json").resolve()))

    def test_resolve_absolute(self):
        self.assertEqual(cfgmod.resolve({"memory_file": r"C:\x\m.json"}, "memory_file", "c.json"), r"C:\x\m.json")

    def test_save_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "config.json"
            cfg = cfgmod.load(path)
            cfg["memory_file"] = "x"
            cfgmod.save(path, cfg)
            self.assertEqual(cfgmod.load(path)["memory_file"], "x")


class SchedulerTest(unittest.TestCase):
    def test_same_day(self):
        now = datetime(2026, 11, 4, 20, 0)
        self.assertEqual(next_run(now, "21:30"), datetime(2026, 11, 4, 21, 30))

    def test_next_day(self):
        now = datetime(2026, 11, 4, 22, 0)
        self.assertEqual(next_run(now, "21:30"), datetime(2026, 11, 5, 21, 30))


if __name__ == "__main__":
    unittest.main(verbosity=2)
