# 独立发布方案（qzone_native）

> 状态：已完成，v0.2.0 起可用。`publish.adapter = qzone_native`，配 `qzone_cookie` 即可，不装 AstrBot / qzone_ultra。

目标：不装 qzone_ultra、不依赖 AstrBot，也能用 Cookie 直接发说说、读评论、回评论。

## 为什么现在不算完全独立

- 生成：`mempost` 已经独立（CLI / MCP / HTTP）
- 发布：`qzone_daemon` 适配器调的是 qzone_ultra 的本地 daemon
- 评论：同样走 daemon

## 方案

把 qzone_ultra 的 MIT 协议桥接层 vendor 进 `mempost/_vendor/qzone_bridge/`，
只保留协议、解析、客户端，不保留 daemon / AstrBot 插件部分。

新增 `mempost/publish/qzone_native.py`：

- Cookie 来源，按优先级：
  1. `qzone_cookie` 配置（浏览器复制的一整串）
  2. `publish.qzone_state_file`（qzone_ultra 的 state.json，有就自动读）
  3. 环境变量 `QZONE_COOKIE`
- 用 `QzoneClient.publish_mood()` 发说说
- 用 `get_feeds()` / `detail()` + parser 读最近说说和评论
- 用 `add_comment()` / `reply_comment()` 回评论
- 不需要 aiohttp / daemon / 端口

依赖：`httpx`（可选依赖 `memory-post[qzone]`）。

## 步骤

| 阶段 | 内容 | 验收 |
|---|---|---|
| P0 | 确认 qzone_bridge 依赖闭包、许可证、Cookie 字段 | 能 import `QzoneClient` |
| P1 | vendor 到 `mempost/_vendor/`，写 logging shim，保留 LICENSE | 纯 Python 环境能 import |
| P2 | `qzone_native.py`：Cookie 解析、publish_mood、feeds/detail | 单元测试 + 一条草稿级调用 |
| P3 | 评论：add_comment / reply_comment，接到 comments.py | dry-run 能列出评论 |
| P4 | CLI/服务/AstrBot 壳接 `adapter=qzone_native`；doctor 检查 Cookie | 命令可跑 |
| P5 | 测试、文档、release v0.2.0、市场更新 | 全过 |

## 第一版不做

- 图片上传（先纯文字；配图继续走 qzone_ultra daemon）
- 视频、多图、定时秒级
- 自动获取 Cookie（浏览器导出后手动填）

## 风险

- Cookie 会过期，过期要重新贴
- QQ 空间协议会变，上游 qzone_bridge 更新后要同步
- 直接调接口比 daemon 更容易触发风控，默认仍是 dry-run

## 验收

1. `pip install memory-post[qzone]` 后，不装 AstrBot 能 `mem-post publish` 发一条纯文字
2. `mem-post comments` 能读到真实评论（dry-run）
3. 所有现有 38 个测试继续过
4. 代码里没有 `astrbot` import
