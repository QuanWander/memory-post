# -*- coding: utf-8 -*-
"""MCP 适配器（stdio）：给 DSH / Claude 等 agent 直接调用。

启动：
    python -m adapters.mcp.server --config config.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mempost import service

CONFIG = os.environ.get("MEMPOST_CONFIG", "config.json")
SERVER_INFO = {"name": "memory-post", "version": "0.1.0"}
PROTOCOL_VERSION = "2024-11-05"


def tools() -> list[dict]:
    return [
        {
            "name": "mem_preview",
            "description": "用记忆生成一条 QQ 空间说说草稿，不发布。",
            "inputSchema": {
                "type": "object",
                "properties": {"with_image": {"type": "boolean", "default": False}},
            },
        },
        {
            "name": "mem_publish",
            "description": "生成并发布一条记忆说说。默认 dry_run，是否真的发取决于配置。",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "force": {"type": "boolean", "default": False},
                    "with_image": {"type": "boolean", "default": False},
                },
            },
        },
        {
            "name": "mem_comments",
            "description": "拉取最近说说的评论并生成回复；send=false 只预览。",
            "inputSchema": {
                "type": "object",
                "properties": {"send": {"type": "boolean", "default": False}},
            },
        },
        {
            "name": "mem_doctor",
            "description": "检查配置、记忆数量、LLM key、发布适配器。",
            "inputSchema": {"type": "object", "properties": {}},
        },
    ]


def call_tool(name: str, args: dict) -> dict:
    try:
        if name == "mem_preview":
            data = service.preview(CONFIG, with_image=bool(args.get("with_image")))
        elif name == "mem_publish":
            data = service.publish(CONFIG, force=bool(args.get("force")), with_image=bool(args.get("with_image")))
        elif name == "mem_comments":
            data = {"comments": service.comments(CONFIG, send=bool(args.get("send")))}
        elif name == "mem_doctor":
            data = service.doctor(CONFIG)
        else:
            return {"content": [{"type": "text", "text": f"未知工具：{name}"}], "isError": True}
    except Exception as exc:  # noqa: BLE001
        return {"content": [{"type": "text", "text": f"执行失败：{exc}"}], "isError": True}
    return {"content": [{"type": "text", "text": json.dumps(data, ensure_ascii=False, indent=2)}]}


def handle(request: dict) -> dict | None:
    method = request.get("method")
    rid = request.get("id")
    if method == "initialize":
        return {"jsonrpc": "2.0", "id": rid, "result": {"protocolVersion": PROTOCOL_VERSION, "capabilities": {"tools": {}}, "serverInfo": SERVER_INFO}}
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": rid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": rid, "result": {"tools": tools()}}
    if method == "tools/call":
        params = request.get("params") or {}
        return {"jsonrpc": "2.0", "id": rid, "result": call_tool(str(params.get("name") or ""), params.get("arguments") or {})}
    return {"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main() -> None:
    global CONFIG
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG)
    args, _ = parser.parse_known_args()
    CONFIG = args.config
    for line in sys.stdin:
        line = line.strip().lstrip("\ufeff")
        if not line:
            continue
        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(request)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
