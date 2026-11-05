# -*- coding: utf-8 -*-
"""回复 QQ 空间评论：拉最近说说 → 找新评论 → 用她的人格回。"""

from __future__ import annotations

import json
from pathlib import Path

from .composer import LLM
from .privacy import PrivacyGuard


def self_uin(cfg: dict) -> int:
    path = str((cfg.get("publish") or {}).get("qzone_state_file") or "")
    if not path or not Path(path).exists():
        return 0
    try:
        state = json.loads(Path(path).read_text(encoding="utf-8"))
        raw = str(((state.get("session") or {}).get("cookies") or {}).get("p_uin") or "")
        return int(raw.lstrip("o"))
    except (ValueError, UnicodeDecodeError, TypeError):
        return 0


def _pick(item: dict, *keys, default=""):
    for key in keys:
        if isinstance(item, dict) and item.get(key) not in (None, ""):
            return item[key]
    return default


def normalize_post(item: dict) -> dict:
    return {
        "fid": str(_pick(item, "fid", "tid", "id")),
        "content": str(_pick(item, "content", "summary", "text")),
        "uin": int(_pick(item, "hostuin", "uin", "owner", default=0) or 0),
        "comment_count": int(_pick(item, "comment_count", "commentCount", "cmtnum", default=0) or 0),
        "comments": item.get("comments") or item.get("commentList") or item.get("comment_list") or [],
    }


def normalize_comment(item: dict, post: dict) -> dict:
    return {
        "fid": post.get("fid", ""),
        "commentid": str(_pick(item, "commentid", "commentId", "tid", "id")),
        "uin": int(_pick(item, "uin", "commentUin", "comment_uin", "userid", default=0) or 0),
        "content": str(_pick(item, "content", "text", "summary")),
        "name": str(_pick(item, "name", "nickname", "nick")),
    }


def new_comments(posts: list[dict], me: int) -> list[dict]:
    out: list[dict] = []
    for post in posts:
        for raw in post.get("comments") or []:
            if not isinstance(raw, dict):
                continue
            comment = normalize_comment(raw, post)
            if not comment["commentid"] or not comment["content"]:
                continue
            if comment["uin"] == me:
                continue
            out.append(comment)
    return out


def build_reply_prompt(persona: str, post_text: str, comment: dict) -> str:
    return f"""你是{persona.strip()[:1000]}

你发了一条 QQ 空间说说：
「{post_text}」

有人评论：
「{comment['content']}」

用你平时说话的方式回一句，要求：
1. 5~40 个字，一条，不换行。
2. 像真人回评论，口语、短，不客套、不总结、不说教。
3. 不要出现主人的名字、学校、QQ、电话、地址、学生等私人信息。
4. 不要链接、@、话题标签、Markdown。
5. 对方只是普通网友，保持距离；不想接就冷淡一点。
只输出回复本身，不要解释。"""


def reply_text(
    cfg: dict,
    persona: str,
    post_text: str,
    comment: dict,
    guard: PrivacyGuard,
    *,
    llm: LLM | None = None,
) -> str:
    client = llm or LLM(cfg)
    last = ""
    for _ in range(2):
        text = client.chat([{"role": "user", "content": build_reply_prompt(persona, post_text, comment)}]).strip()
        text = text.replace("\n", " ").strip("\"'“”")
        if text and not guard.scan(text) and 3 <= len(text) <= 60:
            return text
        last = text
    return last
