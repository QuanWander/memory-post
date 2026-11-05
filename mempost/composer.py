# -*- coding: utf-8 -*-
"""让模型用她自己的记忆，写一条说说。"""

from __future__ import annotations

import json
import random
import re
import time
import urllib.request
from dataclasses import dataclass

from .privacy import PrivacyGuard
from .sources import Memory


@dataclass
class ComposerResult:
    text: str
    used_memories: list[str]


class LLMError(RuntimeError):
    pass


_MODEL_CACHE: dict[str, tuple[float, str]] = {}


def _version_key(text: str) -> tuple[int, ...]:
    nums = re.findall(r"\d+(?:\.\d+)?", text or "")
    return tuple(int(float(n)) for n in nums) if nums else (0,)


def choose_latest_model(models: list[dict], family: str) -> str:
    """从 /models 里挑该系列最新的模型 id；有别名优先用别名。"""
    family = family.lower()
    rows = [m for m in models if isinstance(m, dict) and family in str(m.get("id", "")).lower()]
    rows = [m for m in rows if not any(x in str(m.get("id", "")).lower() for x in ("embedding", "rerank"))]
    if not rows:
        return ""
    alias = f"deepseek-{family}"
    for m in rows:
        if str(m.get("id", "")).lower() == alias:
            return alias
    rows.sort(key=lambda m: _version_key(f"{m.get('id','')} {m.get('name','')}"), reverse=True)
    return str(rows[0].get("id") or "")


def resolve_model(base_url: str, api_key: str, model: str, timeout: float = 10) -> str:
    """把 flash / pro 解析成当前最新模型；解析不了就用原名。"""
    family = ""
    low = (model or "").lower()
    if "flash" in low:
        family = "flash"
    elif "pro" in low:
        family = "pro"
    if not family or "deepseek" not in (base_url or "").lower():
        return model
    cache_key = f"{base_url}|{family}"
    cached = _MODEL_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < 3600:
        return cached[1]
    try:
        req = urllib.request.Request(
            base_url.rstrip("/") + "/models",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        chosen = choose_latest_model(data.get("data") or [], family)
    except Exception:  # noqa: BLE001
        chosen = ""
    if not chosen:
        chosen = "deepseek-flash" if family == "flash" else "deepseek-v4-pro"
    _MODEL_CACHE[cache_key] = (time.time(), chosen)
    return chosen


class LLM:
    def __init__(self, cfg: dict):
        llm = cfg.get("llm") or {}
        self.base_url = str(llm.get("base_url") or "").rstrip("/")
        self.api_key = str(llm.get("api_key") or "")
        self.model = resolve_model(self.base_url, self.api_key, str(llm.get("model") or "flash"))
        self.temperature = float(llm.get("temperature") or 1.0)
        self.frequency_penalty = float(llm.get("frequency_penalty") if llm.get("frequency_penalty") is not None else 0.2)
        self.max_tokens = int(llm.get("max_tokens") or 400)
        self.timeout = float(llm.get("timeout") or 60)

    def chat(self, messages: list[dict], *, temperature: float | None = None, max_tokens: int | None = None) -> str:
        if not self.base_url or not self.api_key:
            raise LLMError("没有配置 llm.base_url / llm.api_key")
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature if temperature is not None else self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            "frequency_penalty": self.frequency_penalty,
        }
        # DeepSeek 默认开思考模式，会把 max_tokens 全花在 reasoning 上导致 content 为空
        if "deepseek" in self.base_url:
            payload["thinking"] = {"type": "disabled"}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/chat/completions",
            data=body,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"LLM 请求失败：{exc}") from exc
        try:
            return str(data["choices"][0]["message"].get("content") or "")
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError(f"LLM 返回格式异常：{data}") from exc


def _strip_wrapping(text: str) -> str:
    body = (text or "").strip()
    body = re.sub(r"^[\"'“”‘’]+|[\"'“”‘’]+$", "", body).strip()
    if body.startswith("说说："):
        body = body[3:].strip()
    return body.replace("\n", " ").strip()


def _memory_pool(memories: list[Memory], guard: PrivacyGuard, limit: int = 6) -> list[str]:
    safe: list[str] = []
    for mem in memories:
        if guard.scan(mem.text):
            continue
        if len(mem.text) > 80:
            continue
        safe.append(mem.text)
    random.shuffle(safe)
    return safe[:limit]


ANGLES = [
    "用一个具体动作或一件东西撑住整条，不解释它的意义",
    "从一句别人说的话切入，只写你的反应，不写前因后果",
    "写一个几秒钟的时间切片：一个动作、一个声音、一个停顿",
    "写一件你本来不打算管、最后还是管了的小事",
    "写一个反差：嘴上说不在乎，手上很诚实",
    "只写你观察到的他的一个细节，不评价、不总结",
    "写一个没头没尾的瞬间，让读者自己拼",
    "借物喻人：只写一个物件和它被怎么对待，让读者想到某个人或某种关系，不要点破",
    "以景写情：用光线、温度、声音、天气承载情绪，不直接说心情",
    "以小见大：写一件很小的事，最后一句轻轻带出一个更大的东西，但不讲道理",
    "化用：自然带出一个成语、诗句或典故的意象，不标出处、不掉书袋",
    "留白：写到一半停住，不解释，让读者自己补",
]


def _recent_lines(recent_posts: list[str]) -> str:
    return "\n".join(f"- {p}" for p in recent_posts[:6]) or "-（无）"


def build_prompt(
    persona: str,
    variant_desc: str,
    memories: list[str],
    diary_text: str,
    recent_posts: list[str],
    guard: PrivacyGuard,
    min_chars: int,
    max_chars: int,
    angle: str = "",
) -> str:
    forbidden = "、".join(guard.entities + guard.deny_words) or "（无）"
    memory_lines = "\n".join(f"- {m}" for m in memories) or "-（没有可用记忆）"
    recent = _recent_lines(recent_posts)
    angle_line = f"\n这次只按这个写法写：{angle}。不要写成别的结构。\n" if angle else ""
    return f"""你是{persona.strip()[:1200]}

你现在是「{variant_desc}」，在发你自己的 QQ 空间说说。这是你的空间，不是主人的空间。

下面这些是「主人」的记忆，只是背景资料，不是你的经历：
{memory_lines}

最近你们聊过的事（你是参与者，不是主人）：
{diary_text or '（无）'}

最近发过的说说和草稿（意思、意象、开头都不要重复，尤其不要再用「盆」「不锈钢盆」）：
{recent}
{angle_line}
写一条你自己的说说，要求：
1. 第一人称「我」只能指你自己（小鲸鱼/大肥鱼），不能把主人的经历写成你做的。
2. 如果要提记忆里的事，写成「他」或「有人」，不要写他的身份。
3. {min_chars}~{max_chars} 个字，一条，不换行。
4. 用一个具体的动作、声音、温度或物件撑住整条；不要先概括再解释。
5. 句子长短交错，允许两三个短句；可以有一个不解释的停顿。
6. 不要每篇都用同一个开头（「今天」「刚刚」「群里」「他今天」），不要固定收尾。
7. 不要硬凹金句、不要强行升华、不要堆形容词；文采来自准确和留白。
8. 文采不是华丽的词。可以借物喻人、以景写情、以小见大、化用成语或诗句；但不要掉书袋、不要文言腔、不要编造诗句或名人名言。
9. 不要出现这些词或信息：{forbidden}；不要出现 QQ 号、电话、地址、学校名、学生姓名、工作单位。
10. 不要链接、@、话题标签、Markdown、引号、表情符号堆砌；不要写「我记得」。

反例（别这样写）：
- 今天就……吧，其实……，说到底……
- 生活总是……，我们都要……
- 今天也是……的一天呢。
- 把主人的经历写成「我今天……」

正例（可以这样写）：
- 楼道灯坏了两天，今晚有人搬了把椅子垫脚换灯泡，我趴在门上看，没出声。
- 他给我看冰箱里半颗包菜，说够吃三顿；我信了，晚上他又点了外卖。
- 阳台那盆薄荷被风吹歪了，我扶正，第二天又歪回去。
- 他把我随口说的胃疼记在备忘录里，排在买菜后面。
- 群里又在聊塔科夫，我插了句嘴，被他们嫌云。

只输出说说本身，不要解释。"""


def compose(
    cfg: dict,
    persona: str,
    variant: dict,
    memories: list[Memory],
    diary_text: str,
    recent_posts: list[str],
    guard: PrivacyGuard,
    *,
    llm: LLM | None = None,
    max_attempts: int = 2,
) -> ComposerResult:
    client = llm or LLM(cfg)
    privacy = cfg.get("privacy") or {}
    min_chars = int(privacy.get("min_chars") or 18)
    max_chars = int(privacy.get("max_chars") or 80)
    pool = _memory_pool(memories, guard)
    variant_desc = f"{variant.get('name')}：{variant.get('desc')}"
    angle = random.choice(ANGLES)

    feedback = ""
    text = ""
    for _ in range(max(1, max_attempts)):
        prompt = build_prompt(
            persona, variant_desc, pool, diary_text, recent_posts, guard, min_chars, max_chars, angle
        )
        if feedback:
            prompt += f"\n\n上一次的输出被拒绝，原因：{feedback}\n请重写。"
        text = _strip_wrapping(client.chat([{"role": "user", "content": prompt}]))
        findings = guard.scan(text)
        if not findings and min_chars <= len(text) <= max_chars:
            break
        feedback = "；".join(f"{f.kind}:{f.text}" for f in findings) or f"长度 {len(text)} 不在范围内"
    return ComposerResult(text=text, used_memories=pool)
