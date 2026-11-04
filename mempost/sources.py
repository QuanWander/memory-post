# -*- coding: utf-8 -*-
"""记忆来源：master_aware 的 memory.json、大肥鱼日记 markdown。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path


@dataclass
class Memory:
    text: str
    created_at: str = ""


@dataclass
class DiaryEntry:
    day: str
    title: str
    text: str


def load_memories(path: str | Path) -> list[Memory]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return []
    entries = data.get("entries") if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return []
    out: list[Memory] = []
    for item in entries:
        if isinstance(item, dict):
            text = str(item.get("text") or "").strip()
            created = str(item.get("created_at") or "")
        else:
            text = str(item).strip()
            created = ""
        if text:
            out.append(Memory(text=text, created_at=created))
    return out


_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def load_diary(dir_path: str | Path, days: int = 3, today: date | None = None) -> list[DiaryEntry]:
    root = Path(dir_path)
    if not root.exists():
        return []
    files = [p for p in root.glob("*.md") if p.is_file()]
    dated: list[tuple[str, Path]] = []
    for p in files:
        m = _DATE_RE.match(p.name)
        if m:
            dated.append((m.group(1), p))
    dated.sort(key=lambda item: item[0], reverse=True)
    picked = dated[: max(1, days)]
    out: list[DiaryEntry] = []
    for day, p in picked:
        try:
            text = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        title = p.stem.split("_", 1)[-1] if "_" in p.stem else p.stem
        out.append(DiaryEntry(day=day, title=title, text=text))
    return out


def diary_digest(entries: list[DiaryEntry], max_chars: int = 1200) -> str:
    """把日记压成一段给模型看的摘要（取每篇前若干行）。"""
    chunks: list[str] = []
    for entry in entries:
        lines = [ln.strip() for ln in entry.text.splitlines() if ln.strip() and not ln.startswith("#")]
        body = "；".join(lines[:6])
        chunks.append(f"[{entry.day} {entry.title}] {body}")
    text = "\n".join(chunks)
    return text[:max_chars]
