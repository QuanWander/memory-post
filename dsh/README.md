# 鲸语拾光 · DSH bundle

把 `memory-post` 的 MCP stdio server 接到 DSH。

## 前置

- Python 3.10+
- 仓库可导入 `mempost` / `adapters`
- `config.local.json`（或你自己的配置）存在

## 配置

`cordis.patch.yml` 默认使用本机路径：

- 解释器：`E:\QQ机器人\AstrBot\.venv\Scripts\python.exe`
- 工作目录：`E:\QQ机器人\发布\memory-post`
- 配置：`config.local.json`

换机器时改这三处；不要提交含密钥的配置。

## 工具

- `mcp__memory_post__mem_preview`
- `mcp__memory_post__mem_publish`
- `mcp__memory_post__mem_comments`
- `mcp__memory_post__mem_doctor`

没有 QQ/QQ 空间适配器时，`mem_publish` 会返回明确错误，不会假装成功。
