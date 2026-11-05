# -*- coding: utf-8 -*-
"""独立发布器：直接用 QQ 空间 Cookie，不依赖 qzone_ultra / AstrBot。

Cookie 来源优先级：
1. publish.qzone_cookie（浏览器复制的一整串）
2. publish.qzone_state_file（qzone_ultra 的 state.json）
3. 环境变量 QZONE_COOKIE
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from pathlib import Path
from typing import Any

from .._vendor.qzone_bridge.parser import (
    extract_feed_entry,
    extract_raw_feeds,
    normalize_feed_page,
    normalize_uin,
    parse_cookie_text,
)


class QzoneNativeError(RuntimeError):
    pass


_COOKIE_CACHE: dict[str, Any] = {"key": "", "cookie": "", "uin": 0, "ts": 0.0}


def clear_cookie_cache() -> None:
    _COOKIE_CACHE.update({"key": "", "cookie": "", "uin": 0, "ts": 0.0})


def _state_cookie(state_path: str) -> tuple[str, int]:
    if not state_path:
        return "", 0
    path = Path(state_path)
    if not path.exists():
        return "", 0
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return "", 0
    cookies = ((state.get("session") or {}).get("cookies") or {})
    if not isinstance(cookies, dict):
        return "", 0
    text = "; ".join(f"{k}={v}" for k, v in cookies.items() if v)
    uin = int(((state.get("session") or {}).get("uin") or 0))
    return text, uin


def load_cookie(cfg: dict) -> tuple[str, int]:
    pub = cfg.get("publish") or {}
    raw = str(pub.get("qzone_cookie") or "").strip()
    uin = 0
    fetched_onebot = False
    base = str(pub.get("onebot_base_url") or "")
    if not raw and base:
        token = str(pub.get("onebot_token") or "")
        domain = str(pub.get("onebot_domain") or "user.qzone.qq.com")
        cache_key = f"{base}|{token}|{domain}"
        ttl = float(pub.get("cookie_cache_seconds") or 600)
        if _COOKIE_CACHE["key"] == cache_key and _COOKIE_CACHE["cookie"] and time.time() - _COOKIE_CACHE["ts"] < ttl:
            raw = _COOKIE_CACHE["cookie"]
            uin = int(_COOKIE_CACHE["uin"])
        else:
            try:
                from ..onebot_cookie import fetch_cookie

                raw = fetch_cookie(base, token, domain)
                fetched_onebot = True
            except Exception:  # noqa: BLE001
                raw = ""
    if not raw:
        raw, uin = _state_cookie(str(pub.get("qzone_state_file") or ""))
    if not raw:
        raw = os.environ.get("QZONE_COOKIE", "").strip()
    if not raw:
        raise QzoneNativeError("没有 Cookie：填 publish.qzone_cookie、配 onebot_token，或设置 QZONE_COOKIE")
    cookies = parse_cookie_text(raw)
    if not cookies:
        raise QzoneNativeError("Cookie 解析失败，检查是不是一整串 key=value; key=value")
    uin = normalize_uin(cookies, override=uin or None)
    if not uin:
        raise QzoneNativeError("Cookie 里找不到 uin / p_uin")
    if fetched_onebot:
        _COOKIE_CACHE.update({"key": cache_key, "cookie": raw, "uin": uin, "ts": time.time()})
    return raw, uin


def _client(cfg: dict) -> tuple[Any, int]:
    try:
        from .._vendor.qzone_bridge.client import QzoneClient
        from .._vendor.qzone_bridge.models import SessionState
    except ImportError as exc:
        raise QzoneNativeError('qzone_native 需要 httpx：pip install "memory-post[qzone]"') from exc
    raw, uin = load_cookie(cfg)
    cookies = parse_cookie_text(raw)
    session = SessionState(uin=uin, cookies=cookies, source="memory-post")
    timeout = float((cfg.get("publish") or {}).get("timeout") or 20)
    return QzoneClient(session, timeout=timeout), uin


def _run(coro):
    return asyncio.run(coro)


def publish(cfg: dict, content: str, *, media: list | None = None) -> dict:
    client, uin = _client(cfg)
    photos = [{"path": item} if isinstance(item, str) else item for item in (media or [])]
    payload = _run(client.publish_mood(content, photos=photos or None))
    fid = ""
    if isinstance(payload, dict):
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        fid = str(data.get("tid") or data.get("fid") or "")
    return {"ok": True, "adapter": "qzone_native", "fid": fid, "raw": payload}


def _extract_comments(node: Any) -> list[dict]:
    """从任意层级的 JSON 里找评论列表。"""
    found: list[dict] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if "comment" in str(key).lower() and isinstance(value, list):
                for item in value:
                    if isinstance(item, dict) and (item.get("content") or item.get("comment")):
                        found.append(
                            {
                                "commentid": str(item.get("commentid") or item.get("commentId") or item.get("tid") or item.get("id") or ""),
                                "uin": int(item.get("uin") or item.get("commentUin") or item.get("comment_uin") or 0),
                                "content": str(item.get("content") or item.get("comment") or ""),
                                "name": str(item.get("name") or item.get("nickname") or ""),
                            }
                        )
            else:
                found.extend(_extract_comments(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_extract_comments(item))
    return found


def feeds(cfg: dict, limit: int = 5) -> list[dict]:
    client, uin = _client(cfg)
    raw = _run(client.get_feeds(uin))
    page = normalize_feed_page(raw)
    items = extract_raw_feeds(page)
    out: list[dict] = []
    for item in items[:limit]:
        entry = extract_feed_entry(item, default_hostuin=uin)
        comments = _extract_comments(item)
        out.append(
            {
                "fid": entry.fid,
                "content": entry.summary,
                "uin": entry.hostuin,
                "comments": comments,
                "comment_count": entry.comment_count,
                "created_at": entry.created_at,
                "raw": item,
            }
        )
    return out


def detail(cfg: dict, fid: str) -> dict:
    client, uin = _client(cfg)
    raw = _run(client.detail(uin, fid))
    return {"fid": fid, "comments": _extract_comments(raw), "raw": raw}


def delete(cfg: dict, fid: str, *, created_at: int = 0) -> dict:
    client, _ = _client(cfg)
    return _run(client.delete_post(fid, created_at=created_at))


def reply(cfg: dict, *, hostuin: int, fid: str, commentid: str, comment_uin: int, content: str) -> dict:
    client, _ = _client(cfg)
    return _run(client.reply_comment(hostuin, fid, commentid, comment_uin, content))
