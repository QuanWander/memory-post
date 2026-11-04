# -*- coding: utf-8 -*-
"""最近说说的相似度，防止连着几天写同一件事。"""

from __future__ import annotations


def _bigrams(text: str) -> set[str]:
    body = "".join(ch for ch in text if not ch.isspace())
    if len(body) < 2:
        return {body} if body else set()
    return {body[i : i + 2] for i in range(len(body) - 1)}


def similarity(a: str, b: str) -> float:
    sa, sb = _bigrams(a), _bigrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def max_similarity(text: str, recent: list[str]) -> float:
    return max((similarity(text, item) for item in recent), default=0.0)
