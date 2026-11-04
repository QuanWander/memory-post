# -*- coding: utf-8 -*-
"""隐私过滤：发说说之前，先把不该出现的东西挡住。"""

from __future__ import annotations

import re
from dataclasses import dataclass

PHONE_RE = re.compile(r"(?<!\d)1[3-9]\d{9}(?!\d)")
ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
URL_RE = re.compile(r"https?://|www\.", re.IGNORECASE)
AT_RE = re.compile(r"@\S+")
# 6 位以上纯数字：QQ 号、学号、工号，正常说说里很少需要
LONG_NUMBER_RE = re.compile(r"(?<!\d)\d{6,}(?!\d)")
QQ_CONTEXT_RE = re.compile(r"(?:QQ|qq|群号|扣扣)\s*[:：]?\s*[1-9]\d{4,11}")


@dataclass
class Finding:
    kind: str
    text: str

    def __str__(self) -> str:  # pragma: no cover
        return f"{self.kind}:{self.text}"


class PrivacyGuard:
    def __init__(self, entities: list[str] | None = None, deny_words: list[str] | None = None):
        self.entities = [e.strip() for e in (entities or []) if e and e.strip()]
        self.deny_words = [w.strip() for w in (deny_words or []) if w and w.strip()]
        # 长的先匹配，避免短词先命中
        self.entities.sort(key=len, reverse=True)
        self.deny_words.sort(key=len, reverse=True)

    def scan(self, text: str) -> list[Finding]:
        body = text or ""
        findings: list[Finding] = []
        for regex, kind in (
            (PHONE_RE, "phone"),
            (ID_RE, "id_card"),
            (EMAIL_RE, "email"),
            (URL_RE, "url"),
            (AT_RE, "at"),
            (QQ_CONTEXT_RE, "qq"),
            (LONG_NUMBER_RE, "long_number"),
        ):
            for match in regex.finditer(body):
                findings.append(Finding(kind, match.group(0)))
        for entity in self.entities:
            if entity and entity in body:
                findings.append(Finding("entity", entity))
        for word in self.deny_words:
            if word and word in body:
                findings.append(Finding("deny_word", word))
        return findings

    def is_clean(self, text: str) -> bool:
        return not self.scan(text)


def normalize(text: str) -> str:
    body = (text or "").replace("\u200b", "").replace("\ufeff", "")
    body = re.sub(r"\s+", " ", body)
    return body.strip()
