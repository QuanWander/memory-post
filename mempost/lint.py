# -*- coding: utf-8 -*-
"""发布前的文本检查。"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .dedupe import max_similarity
from .privacy import PrivacyGuard

AI_PHRASES = (
    "作为AI",
    "作为一个",
    "总之",
    "综上所述",
    "首先",
    "其次",
    "希望对",
    "希望这个",
    "值得注意的是",
    "在这个",
)
MARKDOWN_RE = re.compile(r"(\*\*|__|^#|\n#|^\s*[-*]\s|^\s*\d+\.\s)", re.MULTILINE)


@dataclass
class Issue:
    code: str
    detail: str

    def __str__(self) -> str:
        return f"[{self.code}] {self.detail}"


def lint(
    text: str,
    guard: PrivacyGuard,
    *,
    min_chars: int = 18,
    max_chars: int = 80,
    recent: list[str] | None = None,
    similarity_threshold: float = 0.55,
) -> list[Issue]:
    issues: list[Issue] = []
    body = (text or "").strip()
    if not body:
        return [Issue("empty", "内容为空")]

    if "\n" in body or "\r" in body:
        issues.append(Issue("newline", "说说里不要换行"))
    length = len(body)
    if length < min_chars:
        issues.append(Issue("too_short", f"只有 {length} 字，少于 {min_chars}"))
    if length > max_chars:
        issues.append(Issue("too_long", f"{length} 字，超过 {max_chars}"))

    if MARKDOWN_RE.search(body):
        issues.append(Issue("markdown", "含 Markdown 标记"))
    if "http://" in body or "https://" in body or "www." in body:
        issues.append(Issue("link", "含链接"))
    if "@" in body:
        issues.append(Issue("at", "含 @"))
    for phrase in AI_PHRASES:
        if phrase in body:
            issues.append(Issue("ai_tone", f"含 AI 腔：{phrase}"))

    for finding in guard.scan(body):
        issues.append(Issue(f"privacy_{finding.kind}", f"命中 {finding.text}"))

    if recent:
        score = max_similarity(body, recent)
        if score >= similarity_threshold:
            issues.append(Issue("duplicate", f"和最近说说相似度 {score:.2f}"))

    return issues
