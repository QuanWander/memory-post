# -*- coding: utf-8 -*-
"""演示模式：不需要配置、不写 state，让用户先看到效果。"""

from __future__ import annotations

DEMO_MEMORIES = [
    "他今天绕小区走了七圈半，腿有点酸，但风是凉的。",
    "他答应周末把洗衣机的生料带缠上。",
    "他中午在食堂吃了一荤一素，说味道不错。",
]

DEMO_EXAMPLES = [
    {
        "label": "具体动作",
        "text": "楼道灯坏了两天，今晚有人搬了把椅子垫脚换灯泡，我趴在门上看，没出声。",
    },
    {
        "label": "借物喻人",
        "text": "阳台那盆薄荷被风吹歪了，我扶正，第二天又歪回去。",
    },
    {
        "label": "留白",
        "text": "水烧到一半壶自己跳了，我蹲那儿等它再响，等了半天才想起来插头松了。",
    },
]


def examples() -> list[dict]:
    return [dict(item) for item in DEMO_EXAMPLES]
