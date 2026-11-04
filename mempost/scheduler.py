# -*- coding: utf-8 -*-
"""每天定时跑一次。不依赖第三方调度库。"""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from pathlib import Path


def next_run(now: datetime, hhmm: str) -> datetime:
    hour, minute = (int(x) for x in hhmm.split(":"))
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return target


def run_daily(callback, hhmm: str, *, stamp_file: str | Path, poll_seconds: int = 30) -> None:
    """阻塞循环；同一天只跑一次（用 stamp 文件记录）。"""
    stamp = Path(stamp_file)
    while True:
        now = datetime.now()
        today = now.strftime("%Y-%m-%d")
        done = stamp.read_text(encoding="utf-8").strip() if stamp.exists() else ""
        hh, mm = (int(x) for x in hhmm.split(":"))
        if done != today and (now.hour, now.minute) >= (hh, mm):
            try:
                callback()
            except Exception as exc:  # noqa: BLE001
                print(f"[scheduler] 本次失败：{exc}")
            else:
                stamp.parent.mkdir(parents=True, exist_ok=True)
                stamp.write_text(today + "\n", encoding="utf-8")
        target = next_run(datetime.now(), hhmm)
        time.sleep(min(max(1.0, (target - datetime.now()).total_seconds()), poll_seconds))
