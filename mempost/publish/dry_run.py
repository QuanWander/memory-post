# -*- coding: utf-8 -*-
"""发布适配器：dry-run（写文件，不发）。"""

from __future__ import annotations

import time
from pathlib import Path


def publish(content: str, *, outbox: str | Path) -> dict:
    folder = Path(outbox)
    folder.mkdir(parents=True, exist_ok=True)
    name = time.strftime("%Y%m%d-%H%M%S") + ".txt"
    path = folder / name
    path.write_text(content + "\n", encoding="utf-8")
    return {"ok": True, "adapter": "dry_run", "path": str(path), "fid": ""}
