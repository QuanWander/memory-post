# -*- coding: utf-8 -*-
"""让模型用她自己的记忆，写一条说说。"""

from __future__ import annotations

import json
import random
import re
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


class LLM:
    def __init__(self, cfg: dict):
        llm = cfg.get("llm") or {}
        self.base_url = str(llm.get("base_url") or "").rstrip("/")
        self.api_key = str(llm.get("api_key") or "")
        self.model = str(llm.get("model") or "deepseek-flash")
        self.temperature = float(llm.get("temperature") or 0.9)
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


def build_prompt(
    persona: str,
    variant_desc: str,
    memories: list[str],
    diary_text: str,
    recent_posts: list[str],
    guard: PrivacyGuard,
    min_chars: int,
    max_chars: int,
) -> str:
    forbidden = "、".join(guard.entities + guard.deny_words) or "（无）"
    memory_lines = "\n".join(f"- {m}" for m in memories) or "-（没有可用记忆）"
    recent = "\n".join(f"- {p}" for p in recent_posts[:5]) or "-（无）"
    return f"""你是{persona.strip()[:1200]}

你现在是「{variant_desc}」，在发你自己的 QQ 空间说说。这是你的空间，不是主人的空间。

下面这些是「主人」的记忆，只是背景资料，不是你的经历：
{memory_lines}

最近你们聊过的事（你是参与者，不是主人）：
{diary_text or '（无）'}

最近发过的说说（不要重复同样的意思）：
{recent}

写一条你自己的说说，要求：
1. 第一人称「我」只能指你自己（小鲸鱼/大肥鱼），不能把主人的经历写成你做的。
2. 如果要提记忆里的事，写成「他」或「有人」，不要写他的身份。
3. 写你自己的东西：你在群里看到什么、你对他的吐槽/关心、你自己形象的梗、你的小情绪。
4. {min_chars}~{max_chars} 个字，一条，不换行；具体一点，不要总结、不要讲道理。
5. 不要出现这些词或信息：{forbidden}；不要出现 QQ 号、电话、地址、学校名、学生姓名、工作单位。
6. 不要链接、@、话题标签、Markdown、引号、表情符号堆砌。
7. 不要复述记忆，不要写「我记得」；可以自嘲、可以有一点比喻，但不要文艺腔，不要像 AI。

反例（错）：我今天监考站了四十分钟，回来杯子里的水还是满的。
正例（对）：他今天监考站了四十分钟，回来杯子里的水还是满的，我笑他白站了。
正例（对）：群里又在聊塔科夫，我插了句嘴，被他们嫌云。

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

    feedback = ""
    text = ""
    for _ in range(max(1, max_attempts)):
        prompt = build_prompt(
            persona, variant_desc, pool, diary_text, recent_posts, guard, min_chars, max_chars
        )
        if feedback:
            prompt += f"\n\n上一次的输出被拒绝，原因：{feedback}\n请重写。"
        text = _strip_wrapping(client.chat([{"role": "user", "content": prompt}]))
        findings = guard.scan(text)
        if not findings and min_chars <= len(text) <= max_chars:
            break
        feedback = "；".join(f"{f.kind}:{f.text}" for f in findings) or f"长度 {len(text)} 不在范围内"
    return ComposerResult(text=text, used_memories=pool)
