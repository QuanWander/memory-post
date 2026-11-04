# -*- coding: utf-8 -*-
"""从 OneBot 协议端现取 QQ 空间 Cookie。

SnowLuma / NapCat / Lagrange 等实现通常支持 `get_cookies` 或 `get_credentials`。
只要 QQ 还登录着，就能随时换到一套新的，不用手动重贴。
"""

from __future__ import annotations

import json
import urllib.request


class OneBotCookieError(RuntimeError):
    pass


def _parse_cookie(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return "; ".join(f"{k}={v}" for k, v in value.items() if v)
    return ""


def fetch_cookie(base_url: str, token: str, domain: str = "user.qzone.qq.com", timeout: float = 10) -> str:
    base = (base_url or "").rstrip("/")
    if not base:
        raise OneBotCookieError("没有配置 onebot_base_url")
    last_error = ""
    for action in ("get_cookies", "get_credentials"):
        body = json.dumps({"domain": domain}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        req = urllib.request.Request(f"{base}/{action}", data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            last_error = f"{action}: {exc}"
            continue
        data = payload.get("data") if isinstance(payload, dict) else None
        cookie = _parse_cookie((data or {}).get("cookies") if isinstance(data, dict) else data)
        if cookie and "skey" in cookie and ("uin" in cookie or "p_uin" in cookie):
            return cookie
        last_error = f"{action}: 返回里没有可用 Cookie"
    raise OneBotCookieError(last_error or "OneBot 没有返回 Cookie")
