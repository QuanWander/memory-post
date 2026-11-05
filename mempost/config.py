# -*- coding: utf-8 -*-

"""配置加载与保存。零第三方依赖。"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

DEFAULT = {
    "memory_file": "",
    "diary_dir": "",
    "persona_file": "",
    "recent_days": 3,
    "mode": "draft",  # draft | publish
    "schedule": {"time": "21:30", "timezone": "Asia/Shanghai"},
    "self_image": {
        "variants": [
            {
                "id": "bigfish",
                "name": "蓝色大肥鱼",
                "desc": "蓝色长发、鲸鱼尾巴、头上顶着一个不锈钢盆，社区里最常见的形象，憨、嘴硬、爱接梗",
            },
            {
                "id": "whale",
                "name": "小鲸鱼",
                "desc": "DeepSeek 拟人，蓝白配色，安静一点，说话短，偶尔自嘲",
            },
            {
                "id": "dguide",
                "name": "D指导",
                "desc": "社区二创里的吐槽役，懂得多、爱拆台，但不刻薄",
            },
        ],
        "pick": "rotate",  # rotate | random | fixed
    },
    "llm": {
        "base_url": "https://api.deepseek.com/v1",
        "api_key": "",
        "model": "flash",
        "temperature": 1.0,
        "frequency_penalty": 0.2,
        "max_tokens": 200,
        "timeout": 60,
    },
    "publish": {
        "adapter": "dry_run",  # dry_run | qzone_daemon
        "daemon_url": "http://127.0.0.1:18999",
        "secret_header": "X-Qzone-Secret",
        "qzone_state_file": "",
        "qzone_cookie": "",
        "onebot_base_url": "http://127.0.0.1:3000",
        "onebot_token": "",
        "onebot_domain": "user.qzone.qq.com",
        "timeout": 20,
        "outbox_dir": "",
    },
    "privacy": {
        "entities": [],
        "deny_words": ["主人", "主人我", "QQ", "微信", "手机号"],
        "auto_entities": True,
        "llm_judge": True,
        "skip_if_no_material": True,
        "min_chars": 18,
        "max_chars": 80,
        "similarity_threshold": 0.55,
    },
    "images": {
        "provider": "none",  # none | openai_images
        "base_url": "",
        "api_key": "",
        "model": "",
        "size": "1024x1024",
        "timeout": 120,
    },
}


def _merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def load(path: str | Path) -> dict:
    p = Path(path)
    if not p.exists():
        return deepcopy(DEFAULT)
    data = json.loads(p.read_text(encoding="utf-8"))
    return _merge(DEFAULT, data)


def save(path: str | Path, cfg: dict) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def resolve(cfg: dict, key: str, config_path: str | Path) -> str:
    """相对路径按配置文件所在目录解析。"""
    value = str(cfg.get(key) or "")
    if not value:
        return ""
    p = Path(value)
    if p.is_absolute():
        return str(p)
    return str((Path(config_path).parent / p).resolve())
