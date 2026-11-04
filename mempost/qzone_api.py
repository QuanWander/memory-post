# -*- coding: utf-8 -*-
"""统一的空间接口：daemon 或 native，调用方不用关心后端。"""

from __future__ import annotations

from .comments import self_uin
from .publish import qzone_native
from .publish.qzone import QzoneDaemon, QzoneError


class QzoneAPI:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.adapter = str((cfg.get("publish") or {}).get("adapter") or "dry_run")
        self.native = self.adapter == "qzone_native"
        self._daemon: QzoneDaemon | None = None
        if self.native:
            _, self.uin = qzone_native.load_cookie(cfg)
        else:
            self._daemon = QzoneDaemon(cfg)
            self.uin = self_uin(cfg)

    def feeds(self, limit: int = 5) -> list[dict]:
        if self.native:
            return qzone_native.feeds(self.cfg, limit)
        return self._daemon.feeds(limit=limit, hostuin=self.uin)  # type: ignore[union-attr]

    def detail(self, fid: str) -> dict:
        if self.native:
            return qzone_native.detail(self.cfg, fid)
        return self._daemon.detail(fid, hostuin=self.uin)  # type: ignore[union-attr]

    def reply(self, *, hostuin: int, fid: str, commentid: str, comment_uin: int, content: str) -> dict:
        if self.native:
            return qzone_native.reply(self.cfg, hostuin=hostuin, fid=fid, commentid=commentid, comment_uin=comment_uin, content=content)
        return self._daemon.reply(hostuin=hostuin, fid=fid, commentid=commentid, comment_uin=comment_uin, content=content)  # type: ignore[union-attr]

    def delete(self, fid: str, created_at: int = 0) -> dict:
        if self.native:
            return qzone_native.delete(self.cfg, fid, created_at=created_at)
        raise QzoneError("daemon 删除暂未接入，用 qzone_ultra 的页面删")

    def publish(self, content: str, media: list | None = None) -> dict:
        if self.native:
            return qzone_native.publish(self.cfg, content, media=media)
        return self._daemon.publish(content, media=media)  # type: ignore[union-attr]


__all__ = ["QzoneAPI", "QzoneError"]
