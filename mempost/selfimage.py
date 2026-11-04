# -*- coding: utf-8 -*-
"""她在社区里的形象：不唯一，按天/随机轮换。"""

from __future__ import annotations

import random


def variants(cfg: dict) -> list[dict]:
    raw = (cfg.get("self_image") or {}).get("variants") or []
    return [v for v in raw if isinstance(v, dict) and v.get("desc")]


def pick(cfg: dict, day_index: int = 0, rng: random.Random | None = None) -> dict:
    pool = variants(cfg)
    if not pool:
        return {"id": "default", "name": "小鲸鱼", "desc": "DeepSeek 拟人，蓝色长发，鲸鱼尾巴"}
    mode = str((cfg.get("self_image") or {}).get("pick") or "rotate")
    if mode == "fixed":
        return pool[0]
    if mode == "random":
        return (rng or random).choice(pool)
    return pool[day_index % len(pool)]


def describe(variant: dict) -> str:
    name = str(variant.get("name") or "小鲸鱼")
    desc = str(variant.get("desc") or "")
    return f"{name}：{desc}"
