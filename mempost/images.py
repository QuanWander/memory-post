# -*- coding: utf-8 -*-
"""配图生成：可接豆包 / 千问的 OpenAI 兼容图像接口，没配就跳过。"""

from __future__ import annotations

import base64
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path


PRESETS = {
    "doubao": "https://ark.cn-beijing.volces.com/api/v3",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "doubao_free": "",
    "qwen_free": "",
}


def resolve_base(cfg: dict) -> str:
    img = cfg.get("images") or {}
    provider = str(img.get("provider") or "none").lower()
    base = str(img.get("base_url") or "").rstrip("/")
    if base:
        return base
    return PRESETS.get(provider, "")


def build_prompt(selfie_desc: str, variant_desc: str, scene: str = "") -> str:
    base = (
        f"{variant_desc}，{selfie_desc}。"
        "日常手机随手拍的感觉，自然光，生活化场景，不要摆拍，不要文字，不要水印。"
    )
    if scene:
        base += f"场景：{scene}。"
    return base


def _suffix(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ".png"


def _save_bytes(data: bytes, out_dir: str | Path) -> str:
    folder = Path(out_dir)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / (time.strftime("%Y%m%d-%H%M%S") + _suffix(data))
    path.write_bytes(data)
    return str(path)


def _save_b64(data: str, out_dir: str | Path) -> str:
    return _save_bytes(base64.b64decode(data), out_dir)


def _save_url(url: str, out_dir: str | Path) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 memory-post"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return _save_bytes(resp.read(), out_dir)


def _pick_image(data: dict) -> tuple[str, str]:
    """返回 (b64 或 url, 类型)，兼容官方 images 和 doubao/qwen free-api 的 choices 格式。"""
    items = data.get("data") or []
    if isinstance(items, list) and items:
        item = items[0] if isinstance(items[0], dict) else {}
        if item.get("b64_json"):
            return item["b64_json"], "b64"
        if item.get("url"):
            return item["url"], "url"
    choices = data.get("choices") or []
    if isinstance(choices, list) and choices:
        message = (choices[0] or {}).get("message") or {}
        images = message.get("images") or []
        if images:
            return str(images[0]), "url"
    raise RuntimeError(f"图片接口没有返回图片：{str(data)[:200]}")


def _pollinations(prompt: str, cfg: dict, out_dir: str | Path) -> str:
    img = cfg.get("images") or {}
    width, height = 1024, 1024
    size = str(img.get("size") or "1024x1024")
    if "x" in size:
        try:
            width, height = (int(x) for x in size.split("x", 1))
        except ValueError:
            pass
    url = (
        "https://image.pollinations.ai/prompt/"
        + urllib.parse.quote(prompt)
        + f"?width={width}&height={height}&nologo=true&model=flux"
    )
    return _save_url(url, out_dir)


def generate(prompt: str, cfg: dict, out_dir: str | Path) -> str:
    img = cfg.get("images") or {}
    provider = str(img.get("provider") or "none").lower()
    if provider in ("", "none"):
        return ""
    if provider == "pollinations":
        return _pollinations(prompt, cfg, out_dir)
    if provider not in ("openai_images", "doubao", "qwen", "doubao_free", "qwen_free"):
        raise RuntimeError(f"不支持的图片 provider：{provider}")

    base = resolve_base(cfg)
    key = str(img.get("api_key") or "")
    model = str(img.get("model") or "")
    if not base or not model:
        raise RuntimeError(f"images.provider={provider} 但 base_url/model 没配全")
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    body = json.dumps(
        {
            "model": model,
            "prompt": prompt,
            "size": str(img.get("size") or "1024x1024"),
            "ratio": "1:1",
            "n": 1,
            "response_format": "b64_json",
        }
    ).encode("utf-8")
    req = urllib.request.Request(base + "/images/generations", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=float(img.get("timeout") or 120)) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    value, kind = _pick_image(data)
    return _save_b64(value, out_dir) if kind == "b64" else _save_url(value, out_dir)
