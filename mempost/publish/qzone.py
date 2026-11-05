# -*- coding: utf-8 -*-
"""发布适配器：qzone_ultra 的本地 daemon。

daemon 默认在 127.0.0.1:18999，请求头 X-Qzone-Secret，
secret 与端口从插件状态文件 state.json 的 runtime 里读。
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


class QzoneError(RuntimeError):
    pass


class QzoneDaemon:
    def __init__(self, cfg: dict):
        pub = cfg.get("publish") or {}
        self.base = str(pub.get("daemon_url") or "http://127.0.0.1:18999").rstrip("/")
        self.header = str(pub.get("secret_header") or "X-Qzone-Secret")
        self.timeout = float(pub.get("timeout") or 20)
        self.secret = ""
        state_path = str(pub.get("qzone_state_file") or "")
        if state_path and Path(state_path).exists():
            try:
                state = json.loads(Path(state_path).read_text(encoding="utf-8"))
                runtime = state.get("runtime") or {}
                self.secret = str(runtime.get("secret") or "")
                port = runtime.get("daemon_port")
                if port:
                    self.base = f"http://127.0.0.1:{int(port)}"
            except (ValueError, UnicodeDecodeError):
                pass

    def _request(self, path: str, body: dict | None = None, method: str = "POST", query: dict | None = None) -> dict:
        url = self.base + path
        if query:
            url += "?" + urllib.parse.urlencode(query)
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {self.header: self.secret, "Content-Type": "application/json"}
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise QzoneError(f"HTTP {exc.code}: {detail}") from exc
        except Exception as exc:  # noqa: BLE001
            raise QzoneError(f"请求失败：{exc}") from exc
        if isinstance(payload, dict) and payload.get("ok") is False:
            raise QzoneError(str(payload.get("error") or payload)[:300])
        return payload

    def publish(self, content: str, media: list | None = None) -> dict:
        payload = self._request("/post", {"content": content, "media": media or []})
        data = payload.get("data") if isinstance(payload, dict) else None
        fid = ""
        if isinstance(data, dict):
            fid = str(data.get("fid") or data.get("tid") or "")
        return {"ok": True, "adapter": "qzone_daemon", "fid": fid, "raw": payload}

    def feeds(self, limit: int = 10, hostuin: int = 0) -> list[dict]:
        payload = self._request("/feeds", method="GET", query={"limit": limit, "hostuin": hostuin})
        data = payload.get("data") if isinstance(payload, dict) else None
        if isinstance(data, dict):
            data = data.get("feeds") or data.get("items")
        return data if isinstance(data, list) else []

    def detail(self, fid: str, hostuin: int = 0) -> dict:
        payload = self._request("/detail", method="GET", query={"fid": fid, "hostuin": hostuin})
        data = payload.get("data") if isinstance(payload, dict) else None
        return data if isinstance(data, dict) else {}

    def reply(self, *, hostuin: int, fid: str, commentid: str, comment_uin: int, content: str) -> dict:
        return self._request(
            "/reply",
            {
                "hostuin": hostuin,
                "fid": fid,
                "commentid": commentid,
                "comment_uin": comment_uin,
                "content": content,
            },
        )
