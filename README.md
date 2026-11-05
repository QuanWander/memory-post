# 鲸语拾光 · 记忆说说

> 她不是每天编一段生活，她是把记得的事写下来。

给 AI 角色用的 QQ 空间说说生成器：读记忆和日记 → 用她的人格写 → 过隐私 → 草稿或自动发 → 还能回评论。

![version](https://img.shields.io/badge/version-0.3.0-blue)
![python](https://img.shields.io/badge/python-3.10%2B-blue)
![license](https://img.shields.io/badge/license-MIT-green)
![tests](https://img.shields.io/badge/tests-52%20passed-brightgreen)

## 为什么又做一个

不少 QQ 空间插件在「模拟生活」：今天去了哪、穿了什么、天气怎样。发出来像那么回事，但跟这个角色**记得的事**没关系。

memory-post 反过来：**先看她知道什么，再决定发什么。**

素材来自 `memory.json` 和最近几天的日记；写的时候用她的人格；写完了先过隐私和文本检查；默认只存草稿，你点头才发。

## 它好在哪

1. **记忆驱动，不是编生活**
   从真实记忆里挑 2–3 条小事，改写成她自己的画面和感受，不逐条复述，也不写「我记得」。

2. **三层隐私，命中就不发**
   正则挡手机/身份证/QQ/链接 → 实体名单挡学校、姓名、城市 → 模型复核再扫一遍。任何一层命中，这条就进草稿，不会发出去。

3. **默认草稿，先看再发**
   `publish.adapter` 默认 `dry_run`，只写 `outbox/`。确认没问题再切 `qzone_daemon`，不会一上来就往你空间发东西。

4. **不绑 AstrBot，也不绑 qzone_ultra**
   核心是纯 Python：CLI 能跑，MCP 能接，HTTP 能调。发布支持两种后端：`qzone_daemon`（借 qzone_ultra 的手）和 `qzone_native`（自带 Cookie 直连，完全独立）。哪天不用 AstrBot，记忆和配置都还在。

5. **评论也能回**
   拉最近说说的新评论，用她的人格回一句；默认 dry-run，`--send` 才真发；回过的记下来，不重复回。

6. **发得出，也说得清**
   每条都记录用了哪几条记忆、哪个社区形象、为什么被拦。不是黑盒。

## 和现成插件比

| 现成插件常见做法 | memory-post |
|---|---|
| 模拟日程、天气、穿搭 | 真实记忆条目 + 最近日记 |
| 可能把主人信息带出去 | 三层过滤，命中即拦 |
| 只能跑在 AstrBot 里 | CLI / MCP / HTTP / AstrBot 壳 |
| 配好就直接发 | 默认 dry-run + 草稿 |
| 发完不知道为什么发这条 | 记录用了哪几条记忆、哪个形象 |
| 回复评论要另装插件 | 内置评论回复，默认只预览 |

## 一分钟上手

```bash
# 1. 装
pip install memory_post-0.3.0-py3-none-any.whl

# 2. 生成配置（AstrBot 用户可加 --preset astrbot 自动猜路径）
mem-post init --config config.json --preset astrbot

# 3. 检查
mem-post doctor --config config.json

# 4. 只生成，不发
mem-post preview --config config.json

# 5. 确认后再发
mem-post publish --config config.json
```

最小配置：

```json
{
  "memory_file": "data/memory.json",
  "diary_dir": "大肥鱼日记",
  "persona_file": "大肥鱼日记/小鲸鱼/人格/默认.md",
  "llm": {
    "base_url": "https://api.deepseek.com/v1",
    "api_key": "sk-...",
    "model": "deepseek-flash"
  },
  "privacy": {
    "entities": ["学校名", "你的名字", "你的QQ"],
    "deny_words": ["主人"]
  },
  "publish": { "adapter": "dry_run" }
}
```

## 它不做什么

- 不爬聊天记录，只读你给的记忆文件和日记目录
- 不读别人的空间，只处理自己最近的说说和评论
- 不生成视频、不支持多图
- 免费网页版豆包/千问没有公开 API，配图要自己填 key；没 key 就只发文字



## 可视化设置

「鲸语拾光」右上角「设置」可以直接改：

- 发布方式、运行模式、每天几点生成
- 模型：flash / pro（自动取最新版本）
- 评论：自动回复开关、轮询间隔、每小时/每天上限
- 配图：provider、模型、base_url、API Key
- 隐私：额外实体名单

保存会写回插件配置，并重启评论监听任务；API Key 留空表示不修改。

## 配置

| 键 | 说明 |
|---|---|
| `memory_file` | `memory.json` 路径（兼容 master_aware 格式） |
| `diary_dir` | 日记目录（`YYYY-MM-DD_主题.md`） |
| `persona_file` | 人格文件路径 |
| `recent_days` | 读最近几天日记 |
| `schedule.time` | 每天几点跑，默认 `21:30` |
| `self_image.variants` | 她在社区里的形象，可多个，按天轮换 |
| `llm.model` | `flash` 或 `pro`，自动解析当前最新版本 |
| `llm.*` | OpenAI 兼容接口（DeepSeek / 豆包 / 千问都行） |
| `publish.adapter` | `dry_run` / `qzone_daemon` |
| `publish.qzone_state_file` | qzone_ultra 的 `state.json`，读 daemon 端口和 secret |
| `reply_comments` | 每天顺带回评论（默认关） |
| `comments_send` | 评论回复是否真发（默认关，只记日志） |
| `comments_limit` | 每次最多回几条 |
| `images.provider` | `none` / `doubao` / `qwen` / `openai_images` |
| `privacy.entities` | 手动补充的实体：学校、姓名、QQ、城市……（可不填） |
| `privacy.auto_entities` | 从记忆/日记自动找敏感实体，默认开 |
| `privacy.llm_judge` | 发布前让模型再判一次隐私，默认开 |
| `privacy.deny_words` | 不能出现的词：主人、学生名单…… |
| `privacy.min_chars/max_chars` | 说说长度 |
| `privacy.similarity_threshold` | 和最近说说去重阈值 |

## 隐私

四层，任何一层命中都不会发布：

1. **正则**：手机、身份证、邮箱、链接、@、6 位以上数字、QQ 上下文
2. **实体名单**：`privacy.entities` 里的词，出现即拦（可以不填）
3. **自动实体发现**：从记忆和日记里自动找学校、地名、人名等候选，缓存 7 天
4. **模型复核**：发布前让模型再判断一次「这条会不会暴露主人」，命中就存草稿

自动发现和模型复核默认开启，可以在配置里关：

```json
{
  "privacy": {
    "auto_entities": true,
    "llm_judge": true
  }
}
```

评论回复同样走这几层。

'## 鲸语拾光（可视化视图）

AstrBot 插件详情页 →「鲸语拾光」：

- 列出所有草稿（文字、时间、配图、检查结果）
- 一键「生成一条」
- 「发布」前二次确认
- 「删除」不要的草稿
- 「复制」文字

也可以继续用指令：

```
/记忆说说 草稿
/记忆说说 发 <id>
```

## 命令行'

```bash
mem-post init --config config.json
mem-post doctor --config config.json
mem-post preview --config config.json          # 只生成
mem-post preview --config config.json --image  # 带配图
mem-post publish --config config.json          # 按 publish.adapter 发
mem-post comments --config config.json         # 评论回复预览（dry-run）
mem-post comments --config config.json --send  # 真回
mem-post drafts --config config.json           # 列草稿
mem-post approve <id> --config config.json     # 审核后发某条草稿
mem-post run --config config.json              # 每天定时
```

## MCP

```bash
python -m adapters.mcp.server --config config.json
```

工具：`mem_preview`、`mem_publish`、`mem_comments`、`mem_doctor`。
DSH / Claude 等支持 MCP 的 agent 可以直接接。

## HTTP

```bash
python -m adapters.http.server --config config.json --port 8766
```

```
GET  /health
GET  /v1/doctor
POST /v1/preview   {"with_image": false}
POST /v1/publish   {"force": false}
POST /v1/comments  {"send": false}
```

## 完全独立：qzone_native

不装 AstrBot、不装 qzone_ultra，只靠 Cookie：

```bash
pip install "memory-post[qzone]"
```

```json
{
  "publish": {
    "adapter": "qzone_native",
    "qzone_cookie": "uin=o3768709013; skey=...; p_skey=..."
  }
}
```

Cookie 从浏览器拿：登录 QQ 空间 → F12 → Network → 任意请求 → Copy as cURL，把 `Cookie:` 后面整串贴进 `qzone_cookie`。

也可以继续用 qzone_ultra 的 `state.json`（填 `qzone_state_file`），不用手动贴。

**Cookie 过期怎么办：让 OneBot 现取，不重贴。**

只要 QQ 还登录着，协议端（SnowLuma / NapCat / Lagrange）一般支持 `get_cookies` / `get_credentials`：

```json
{
  "publish": {
    "adapter": "qzone_native",
    "onebot_base_url": "http://127.0.0.1:3000",
    "onebot_token": "你的 OneBot token"
  }
}
```

每次发布前会先向 OneBot 要一套新 Cookie；`qzone_cookie` 留空即可。取不到才回退到 `state.json` 或环境变量 `QZONE_COOKIE`。

没有协议端、也不想贴 Cookie，就继续用 `qzone_daemon`，让 qzone_ultra 管绑定。

注意：

- `qzone_native` 也支持带图（会先上传到空间相册），前提是配了可用的图片 provider
- 直连接口比 daemon 更容易触发风控，默认还是 dry-run

## 配图

`images.provider`：

- `none`：不配图（默认）
- `pollinations`：免费、不要 key，质量一般，可能有水印
- `doubao`：豆包 Ark 官方接口，`base_url` 自动用 `https://ark.cn-beijing.volces.com/api/v3`
- `qwen`：千问 DashScope 兼容模式，`base_url` 自动用 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- `doubao_free` / `qwen_free`：指向本地的逆向代理（见下），需要代理返回图片
- `openai_images`：自定义 `base_url`

官方 `doubao` / `qwen` 还需要 `images.model` 和 `images.api_key`；没配 key 就自动跳过，只发文字。

### 免费网页版能不能用

能，但**不建议**当成正式方案：

- 有开源逆向项目，把网页版包成 OpenAI 兼容接口，例如
  [doubao-free-api](https://github.com/Bitsea1/doubao-free-api) 和
  [qwen-free-api](https://github.com/hipeyeking/qwen-free-api)
- 需要从网页登录态里拿 `sessionid`，项目自己标注「不稳定、可能封禁、仅限自用」
- 我们的 `doubao_free` / `qwen_free` 就是给这类代理留的口子：本地跑代理，`images.base_url` 指向它

更稳的顺序：官方免费额度 → `pollinations` 兜底 → 逆向代理（自用、风险自负）。


## 测试

```bash
python -m unittest discover -s tests
```

52 个单测，覆盖：隐私正则、实体、文本长度、Markdown、链接、重复、记忆解析、草稿/发布状态、生成重试、评论解析、MCP、配置合并、调度时间、Cookie 解析、native 发布。

## 已知限制

- `qzone_daemon` 依赖 qzone_ultra 已安装并登录；`qzone_native` 不需要，但要自己贴 Cookie
- `qzone_native` 的图片上传代码已接上，但还没有用真实 key 跑过
- 图片接口要自己配 key；免费网页版豆包/千问没有公开 API
- 暂不支持视频、多图、秒级定时
- 市场版本审核中；现在可先下 release 里的 wheel
