# 可移植性说明

## 核心（可离开 AstrBot）

- `mempost/`：记忆读取、生成、草稿、发布适配器
- `adapters/mcp/`：MCP stdio 服务
- `adapters/http/`：HTTP 服务

## AstrBot 壳

- `main.py`：AstrBot 插件入口、页面注册、事件钩子

## DSH 迁移

- 核心不 import AstrBot，可直接作为 MCP 工具运行
- 发布到 QQ 空间仍依赖平台适配器；没有平台时应返回明确错误
- DSH bundle 只做 MCP 接线，不内嵌 Python

## 不迁移

- AstrBot 页面本身可以保留；DSH 面板后续另做
