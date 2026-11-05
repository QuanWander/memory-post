# -*- coding: utf-8 -*-
"""已发 / 草稿的本地记录，原子写入。"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"posts": [], "drafts": []}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {"posts": [], "drafts": []}
        data.setdefault("posts", [])
        data.setdefault("drafts", [])
        return data

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def add_post(self, text: str, *, fid: str = "", status: str = "published", used: list[str] | None = None, variant: str = "", image: str = "") -> dict:
        data = self._load()
        item = {
            "id": uuid.uuid4().hex[:8],
            "text": text,
            "fid": fid,
            "status": status,
            "used": used or [],
            "variant": variant,
            "image": image,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        data["posts"].append(item)
        self._save(data)
        return item

    def add_draft(self, text: str, *, issues: list[str] | None = None, details: list[dict] | None = None, used: list[str] | None = None, variant: str = "", image: str = "", angle: str = "", angle_label: str = "") -> dict:
        data = self._load()
        item = {
            "id": uuid.uuid4().hex[:8],
            "text": text,
            "issues": issues or [],
            "details": details or [],
            "used": used or [],
            "variant": variant,
            "image": image,
            "angle": angle,
            "angle_label": angle_label,
            "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        data["drafts"].append(item)
        self._save(data)
        return item

    def update_draft(self, draft_id: str, **fields) -> dict | None:
        data = self._load()
        for item in data.get("drafts") or []:
            if str(item.get("id")) == str(draft_id):
                item.update({k: v for k, v in fields.items() if v is not None})
                item["updated_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
                self._save(data)
                return item
        return None

    def replace_draft(self, draft_id: str, text: str, *, used: list[str] | None = None, angle: str = "", angle_label: str = "", issues: list[str] | None = None, details: list[dict] | None = None, image: str = "") -> dict | None:
        return self.update_draft(
            draft_id,
            text=text,
            used=used or [],
            angle=angle,
            angle_label=angle_label,
            issues=issues or [],
            details=details or [],
            image=image,
        )

    def get_draft(self, draft_id: str) -> dict | None:
        for item in self._load().get("drafts") or []:
            if str(item.get("id")) == draft_id:
                return item
        return None

    def remove_draft(self, draft_id: str) -> bool:
        data = self._load()
        before = len(data.get("drafts") or [])
        data["drafts"] = [x for x in data.get("drafts") or [] if str(x.get("id")) != draft_id]
        if len(data["drafts"]) == before:
            return False
        self._save(data)
        return True

    def baseline_done(self) -> bool:
        return bool(self._load().get("watch_baseline_at"))

    def mark_baseline_done(self) -> None:
        data = self._load()
        data["watch_baseline_at"] = time.time()
        self._save(data)

    def seen_ids(self) -> set[str]:
        data = self._load()
        return set(data.get("seen") or [])

    def mark_seen(self, comment_key: str) -> None:
        self.mark_seen_many([comment_key])

    def mark_seen_many(self, comment_keys: list[str]) -> None:
        if not comment_keys:
            return
        data = self._load()
        seen = list(data.get("seen") or [])
        for key in comment_keys:
            if key not in seen:
                seen.append(key)
        data["seen"] = seen[-2000:]
        self._save(data)

    def comment_reply_times(self) -> list[float]:
        data = self._load()
        return [float(x) for x in data.get("comment_reply_times") or []]

    def mark_comment_reply(self, comment_key: str) -> None:
        self.record_comment_replies([comment_key])

    def record_comment_replies(self, comment_keys: list[str]) -> None:
        if not comment_keys:
            return
        data = self._load()
        times = list(data.get("comment_reply_times") or [])
        replied = list(data.get("replied") or [])
        for key in comment_keys:
            times.append(time.time())
            if key not in replied:
                replied.append(key)
        data["comment_reply_times"] = times[-500:]
        data["replied"] = replied[-1000:]
        self._save(data)

    def recent_texts(self, limit: int = 7, include_drafts: bool = False) -> list[str]:
        data = self._load()
        posts = [str(p.get("text") or "") for p in data["posts"][-limit:]]
        if include_drafts:
            posts += [str(d.get("text") or "") for d in data["drafts"][-limit:]]
        return posts[-limit:]

    def replied_ids(self) -> set[str]:
        data = self._load()
        return set(data.get("replied") or [])

    def mark_replied(self, comment_id: str) -> None:
        data = self._load()
        replied = list(data.get("replied") or [])
        if comment_id not in replied:
            replied.append(comment_id)
        data["replied"] = replied[-500:]
        self._save(data)

    def posts(self) -> list[dict]:
        return self._load()["posts"]

    def drafts(self) -> list[dict]:
        return self._load()["drafts"]
