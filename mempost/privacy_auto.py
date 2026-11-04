# -*- coding: utf-8 -*-
"""让模型自己判断隐私，不用手填一长串屏蔽词。

两层：
1. discover：从记忆/日记里自动找可能敏感的名字、学校、地名，缓存起来
2. judge：每条说说发布前，让模型判断有没有可识别主人的信息
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from .composer import LLM, LLMError

DISCOVER_PROMPT = """下面是一个人的记忆和日记片段。请找出其中「一旦出现在公开说说里，就可能被别人认出是谁」的词：
人名、学校名、单位名、具体住址、城市/小区、学生姓名、电话、QQ、学号、工号、车牌、具体行程。

只输出 JSON 数组，每项是一个短词，最多 30 个；没有就输出 []。
不要输出解释，不要输出句子，不要把「主人」「他」这种泛称算进去。
不要输出项目名、软件名、插件名、商品名、价格、日期、时间、游戏名。

记忆：
{memories}

日记片段：
{diary}
"""

JUDGE_PROMPT = """判断这条准备发到 QQ 空间的说说，是否包含「能识别出主人是谁」的个人信息。

包括：真实姓名、学校/单位、具体住址、城市+小区、电话、QQ、学号、学生姓名、车牌、当天具体行程。
不包括：泛称（他、有人、家里）、普通生活细节（吃饭、天气、游戏）、不指向具体人的情绪。

只输出 JSON：{{"safe": true/false, "hit": ["命中的词"]}}
不要解释。

说说：
{text}
"""


def _parse_json(text: str):
    body = (text or "").strip()
    body = re.sub(r"^```(?:json)?|```$", "", body, flags=re.MULTILINE).strip()
    try:
        return json.loads(body)
    except ValueError:
        match = re.search(r"\[.*\]|\{.*\}", body, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except ValueError:
            return None


def _looks_personal(text: str) -> bool:
    """过滤掉项目名、价格、日期这类明显不是个人信息的候选。"""
    if len(text) <= 1:
        return False
    if re.search(r"\d", text) and re.search(r"年|月|日|元|块|点|:|：", text):
        return False
    if re.fullmatch(r"[A-Za-z0-9_.\-]+", text):
        return False
    if any(word in text for word in ("插件", "项目", "模型", "版本", "游戏", "洗衣机", "Agent", "agent")):
        return False
    return True


def discover(
    llm: LLM,
    memories: list[str],
    diary_text: str,
    cache_path: str | Path,
    *,
    ttl_days: int = 7,
    force: bool = False,
) -> list[str]:
    path = Path(cache_path)
    if not force and path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            updated = float(data.get("updated_at") or 0)
            if time.time() - updated < ttl_days * 86400:
                return [str(x) for x in data.get("entities") or [] if str(x).strip()]
        except (ValueError, UnicodeDecodeError):
            pass

    prompt = DISCOVER_PROMPT.format(
        memories="\n".join(f"- {m}" for m in memories[:40]) or "（无）",
        diary=diary_text[:2000] or "（无）",
    )
    try:
        raw = llm.chat([{"role": "user", "content": prompt}], temperature=0.2, max_tokens=300)
    except LLMError:
        return []
    data = _parse_json(raw)
    if not isinstance(data, list):
        return []
    entities = []
    for item in data:
        text = str(item).strip()
        if 0 < len(text) <= 20 and _looks_personal(text) and text not in entities:
            entities.append(text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"updated_at": time.time(), "entities": entities}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return entities


def judge(llm: LLM, text: str, hints: list[str] | None = None) -> list[str]:
    prompt = JUDGE_PROMPT.format(text=text)
    if hints:
        prompt += "\n已知可能敏感的候选词（仅参考，不要因为出现就判定不安全）：" + "、".join(hints[:30])
    try:
        raw = llm.chat(
            [{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=120,
        )
    except LLMError:
        return []
    data = _parse_json(raw)
    if not isinstance(data, dict):
        return []
    if bool(data.get("safe", True)):
        return []
    hits = data.get("hit") or []
    if isinstance(hits, str):
        hits = [hits]
    return [str(x) for x in hits if str(x).strip()]
