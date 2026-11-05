# -*- coding: utf-8 -*-
"""AstrBot 适配器：记忆说说。

核心在 mempost/，这里只做：读配置、每天定时、提供一个手动指令。
"""

from __future__ import annotations

import asyncio
import copy
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.api.web import error_response, file_response, json_response, request

from mempost import config as cfgmod
from mempost.comments import new_comments, normalize_post, reply_text, self_uin
from mempost.composer import LLM, compose
from mempost.images import build_prompt, generate
from mempost.lint import Issue, lint
from mempost.privacy import PrivacyGuard
from mempost.privacy_auto import discover, judge
from mempost.publish import dry_run
from mempost.publish.qzone import QzoneError
from mempost.publish.qzone_native import QzoneNativeError
from mempost.qzone_api import QzoneAPI
from mempost.selfimage import describe, pick
from mempost.sources import diary_digest, load_diary, load_memories
from mempost.state import Store

DEFAULT_PERSONA = "你是 DeepSeek 小鲸鱼，QQ 群里的群友。说话短、口语、有立场，不总结、不说教。"


@register(
    "astrbot_plugin_memory_post",
    "大肥鱼",
    "用她自己的记忆，每天写一条 QQ 空间说说",
    "0.2.5",
)
class MemoryPost(Star):
    def __init__(self, context: Context, config: dict | None = None) -> None:
        super().__init__(context)
        self.config = config or {}
        self._base = Path(__file__).resolve().parents[2] / "plugin_data" / "astrbot_plugin_memory_post"
        self._task: asyncio.Task | None = None
        self._comment_task: asyncio.Task | None = None
        context.register_web_api("/astrbot_plugin_memory_post/drafts", self.page_drafts, ["GET"], "List drafts")
        context.register_web_api("/astrbot_plugin_memory_post/drafts/publish", self.page_publish, ["POST"], "Publish draft")
        context.register_web_api("/astrbot_plugin_memory_post/drafts/delete", self.page_delete, ["POST"], "Delete draft")
        context.register_web_api("/astrbot_plugin_memory_post/drafts/image", self.page_image, ["GET"], "Draft image")
        context.register_web_api("/astrbot_plugin_memory_post/generate", self.page_generate, ["POST"], "Generate draft")

    # ------------------------------------------------------------------ 页面 API
    async def page_drafts(self):
        store = Store(self._base / "state.json")
        items = []
        for x in store.drafts():
            items.append(
                {
                    "id": x.get("id"),
                    "text": x.get("text"),
                    "created_at": x.get("created_at"),
                    "issues": x.get("issues") or [],
                    "image": bool(x.get("image")),
                }
            )
        return json_response({"drafts": items, "adapter": str(self.config.get("publish_adapter") or "dry_run")})

    async def page_publish(self):
        payload = await request.json(default={})
        draft_id = str(payload.get("id") or "")
        if not draft_id:
            return error_response("missing id", status_code=400)
        result = await asyncio.to_thread(self._publish_draft_sync, draft_id)
        return json_response(result)

    async def page_delete(self):
        payload = await request.json(default={})
        draft_id = str(payload.get("id") or "")
        store = Store(self._base / "state.json")
        return json_response({"deleted": store.remove_draft(draft_id)})

    async def page_image(self):
        draft_id = request.query.get("id", "")
        store = Store(self._base / "state.json")
        draft = store.get_draft(draft_id)
        if not draft or not draft.get("image"):
            return error_response("not found", status_code=404)
        path = Path(str(draft["image"]))
        if not path.exists():
            return error_response("not found", status_code=404)
        suffix = path.suffix.lower()
        ctype = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(suffix, "image/png")
        return file_response(path, filename=path.name, content_type=ctype)

    async def page_generate(self):
        result = await asyncio.to_thread(self._generate_sync)
        return json_response(result)

    # ------------------------------------------------------------------ 配置
    def _split(self, key: str, default: str = "") -> list[str]:
        raw = str(self.config.get(key) or default)
        return [x.strip() for x in raw.replace("，", ",").split(",") if x.strip()]

    def _core_config(self) -> dict:
        cfg = copy.deepcopy(cfgmod.DEFAULT)
        cfg["memory_file"] = str(self.config.get("memory_file") or "")
        cfg["diary_dir"] = str(self.config.get("diary_dir") or "")
        cfg["persona_file"] = str(self.config.get("persona_file") or "")
        cfg["recent_days"] = int(self.config.get("recent_days") or 3)
        cfg["mode"] = str(self.config.get("mode") or "draft")
        cfg["schedule"]["time"] = str(self.config.get("schedule_time") or "21:30")
        cfg["llm"]["base_url"] = str(self.config.get("llm_base_url") or cfg["llm"]["base_url"])
        cfg["llm"]["api_key"] = str(self.config.get("llm_api_key") or "")
        cfg["llm"]["model"] = str(self.config.get("llm_model") or cfg["llm"]["model"])
        cfg["publish"]["adapter"] = str(self.config.get("publish_adapter") or "dry_run")
        cfg["publish"]["qzone_state_file"] = str(self.config.get("qzone_state_file") or "")
        cfg["publish"]["qzone_cookie"] = str(self.config.get("qzone_cookie") or "")
        cfg["publish"]["onebot_base_url"] = str(self.config.get("onebot_base_url") or cfg["publish"]["onebot_base_url"])
        cfg["publish"]["onebot_token"] = str(self.config.get("onebot_token") or "")
        cfg["publish"]["onebot_domain"] = str(self.config.get("onebot_domain") or "user.qzone.qq.com")
        cfg["publish"]["outbox_dir"] = str(self._base / "outbox")
        cfg["privacy"]["entities"] = self._split("privacy_entities")
        cfg["privacy"]["deny_words"] = self._split("privacy_deny_words", "主人")
        cfg["privacy"]["auto_entities"] = bool(self.config.get("privacy_auto_entities", True))
        cfg["privacy"]["llm_judge"] = bool(self.config.get("privacy_llm_judge", True))
        cfg["privacy"]["min_chars"] = int(self.config.get("min_chars") or 18)
        cfg["privacy"]["max_chars"] = int(self.config.get("max_chars") or 80)
        cfg["images"]["provider"] = str(self.config.get("images_provider") or "none")
        cfg["images"]["base_url"] = str(self.config.get("images_base_url") or "")
        cfg["images"]["api_key"] = str(self.config.get("images_api_key") or "")
        cfg["images"]["model"] = str(self.config.get("images_model") or "")
        return cfg

    # ------------------------------------------------------------------ 生成
    def _generate_sync(self) -> dict:
        cfg = self._core_config()
        guard = PrivacyGuard(cfg["privacy"]["entities"], cfg["privacy"]["deny_words"])
        memories = load_memories(cfg["memory_file"])
        diary = load_diary(cfg["diary_dir"], cfg["recent_days"])
        store = Store(self._base / "state.json")
        variant = pick(cfg, len(store.posts()))
        persona = DEFAULT_PERSONA
        if cfg["persona_file"] and Path(cfg["persona_file"]).exists():
            persona = Path(cfg["persona_file"]).read_text(encoding="utf-8")
        llm = LLM(cfg)
        diary_text = diary_digest(diary)
        auto_hints: list[str] = []
        if cfg["privacy"].get("auto_entities", True):
            auto_hints = discover(llm, [m.text for m in memories], diary_text, self._base / "state" / "privacy_entities.json")
        result = compose(cfg, persona, variant, memories, diary_text, store.recent_texts(7, include_drafts=True), guard, llm=llm)
        issues = lint(
            result.text,
            guard,
            min_chars=cfg["privacy"]["min_chars"],
            max_chars=cfg["privacy"]["max_chars"],
            recent=store.recent_texts(7, include_drafts=True),
            similarity_threshold=cfg["privacy"]["similarity_threshold"],
        )
        if not issues and cfg["privacy"].get("llm_judge", True):
            hits = judge(llm, result.text, auto_hints)
            if hits:
                issues.append(Issue("privacy_llm", "模型判断可能含：" + "、".join(hits)))
        image_path = ""
        if not issues and cfg["images"]["provider"] not in ("", "none"):
            try:
                image_path = generate(build_prompt("自拍或日常随手拍", describe(variant), scene=result.text), cfg, self._base / "outbox" / "images")
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[memory-post] 配图失败，按纯文字继续：{exc}")

        if issues:
            store.add_draft(result.text, issues=[str(i) for i in issues], used=result.used_memories, variant=str(variant.get("name")), image=image_path)
            return {"ok": False, "text": result.text, "issues": [str(i) for i in issues], "image": image_path}

        mode = str(cfg.get("mode") or "draft")
        if mode != "publish":
            store.add_draft(result.text, used=result.used_memories, variant=str(variant.get("name")), image=image_path)
            return {"ok": True, "published": False, "text": result.text, "image": image_path}

        adapter = str(cfg["publish"]["adapter"] or "dry_run")
        try:
            if adapter in ("qzone_daemon", "qzone_native"):
                payload = QzoneAPI(cfg).publish(result.text, media=[image_path] if image_path else [])
            else:
                payload = dry_run.publish(result.text, outbox=str(self._base / "outbox"))
        except (QzoneError, QzoneNativeError, RuntimeError) as exc:
            store.add_draft(result.text, issues=[f"publish_failed:{exc}"], used=result.used_memories, variant=str(variant.get("name")), image=image_path)
            return {"ok": False, "text": result.text, "issues": [f"publish_failed:{exc}"], "image": image_path}

        store.add_post(result.text, fid=str(payload.get("fid") or ""), used=result.used_memories, variant=str(variant.get("name")), image=image_path)
        return {"ok": True, "published": True, "text": result.text, "image": image_path, "payload": payload}

    # ------------------------------------------------------------------ 评论
    def _comments_sync(self, send: bool = False) -> dict:
        cfg = self._core_config()
        guard = PrivacyGuard(cfg["privacy"]["entities"], cfg["privacy"]["deny_words"])
        persona = DEFAULT_PERSONA
        if cfg["persona_file"] and Path(cfg["persona_file"]).exists():
            persona = Path(cfg["persona_file"]).read_text(encoding="utf-8")
        api = QzoneAPI(cfg)
        me = api.uin
        posts = [normalize_post(x) for x in api.feeds(limit=5)]
        for post in posts:
            if post.get("fid"):
                try:
                    detail = api.detail(post["fid"])
                    comments = detail.get("comments") or detail.get("commentList") or []
                    if comments:
                        post["comments"] = comments
                except (QzoneError, QzoneNativeError):
                    pass
        store = Store(self._base / "state.json")
        replied = store.replied_ids()
        limit = int(self.config.get("comments_limit") or 3)
        todo = [c for c in new_comments(posts, me) if f"{c['fid']}:{c['commentid']}" not in replied][:limit]
        out: list[dict] = []
        for comment in todo:
            post_text = next((p["content"] for p in posts if p["fid"] == comment["fid"]), "")
            text = reply_text(cfg, persona, post_text, comment, guard)
            if send:
                api.reply(hostuin=me, fid=comment["fid"], commentid=comment["commentid"], comment_uin=comment["uin"], content=text)
                store.mark_replied(f"{comment['fid']}:{comment['commentid']}")
            out.append({"who": comment.get("name") or comment["uin"], "reply": text, "sent": send})
        return {"comments": out}

    # ------------------------------------------------------------------ 评论监听
    def _watch_baseline(self) -> dict:
        cfg = self._core_config()
        api = QzoneAPI(cfg)
        store = Store(self._base / "state.json")
        seen = store.seen_ids()
        pending: list[str] = []
        for post in [normalize_post(x) for x in api.feeds(5)]:
            if not post.get("comment_count") and not post.get("comments"):
                continue
            try:
                detail = api.detail(post["fid"])
            except (QzoneError, QzoneNativeError):
                continue
            for comment in new_comments([{**post, "comments": detail.get("comments") or []}], api.uin):
                key = f"{post['fid']}:{comment['commentid']}"
                if key not in seen:
                    pending.append(key)
                    seen.add(key)
        store.mark_seen_many(pending)
        return {"baseline": len(pending)}

    def _watch_once(self) -> dict:
        cfg = self._core_config()
        api = QzoneAPI(cfg)
        store = Store(self._base / "state.json")
        seen = store.seen_ids()
        replied = store.replied_ids()
        fresh: list[tuple[dict, dict, str]] = []
        already: list[str] = []
        for post in [normalize_post(x) for x in api.feeds(5)]:
            if not post.get("comment_count") and not post.get("comments"):
                continue
            try:
                detail = api.detail(post["fid"])
            except (QzoneError, QzoneNativeError):
                continue
            for comment in new_comments([{**post, "comments": detail.get("comments") or []}], api.uin):
                key = f"{post['fid']}:{comment['commentid']}"
                if key in seen:
                    continue
                if key in replied:
                    already.append(key)
                    continue
                fresh.append((post, comment, key))
        store.mark_seen_many(already)
        if not fresh:
            return {"new": 0, "replied": 0}
        if not bool(self.config.get("comments_send", False)):
            store.mark_seen_many([key for _, _, key in fresh])
            return {"new": len(fresh), "replied": 0, "mode": "dry_run"}

        per_hour = int(self.config.get("comments_per_hour") or 3)
        per_day = int(self.config.get("comments_per_day") or 20)
        now = time.time()
        times = store.comment_reply_times()
        hour_count = sum(1 for t in times if t > now - 3600)
        day_count = sum(1 for t in times if t > now - 86400)
        persona = DEFAULT_PERSONA
        if cfg["persona_file"] and Path(cfg["persona_file"]).exists():
            persona = Path(cfg["persona_file"]).read_text(encoding="utf-8")
        guard = PrivacyGuard(cfg["privacy"]["entities"], cfg["privacy"]["deny_words"])
        success: list[str] = []
        for post, comment, key in fresh:
            if hour_count >= per_hour or day_count >= per_day:
                break
            text = reply_text(cfg, persona, post.get("content", ""), comment, guard)
            if not text:
                continue
            try:
                api.reply(hostuin=api.uin, fid=post["fid"], commentid=comment["commentid"], comment_uin=comment["uin"], content=text)
            except (QzoneError, QzoneNativeError) as exc:
                logger.warning(f"[memory-post] 评论回复失败，保留重试：{exc}")
                continue
            success.append(key)
            hour_count += 1
            day_count += 1
        store.record_comment_replies(success)
        return {"new": len(fresh), "replied": len(success), "pending": len(fresh) - len(success)}


    async def _comment_watch_loop(self) -> None:
        try:
            data = await asyncio.to_thread(self._watch_baseline)
            logger.info(f"[memory-post] 评论监听基线：{data}")
        except Exception:
            logger.exception("[memory-post] 评论监听基线失败")
        minutes = max(1, int(self.config.get("comment_poll_minutes") or 10))
        while True:
            await asyncio.sleep(minutes * 60)
            try:
                data = await asyncio.to_thread(self._watch_once)
                logger.info(f"[memory-post] 评论监听：{data}")
            except Exception:
                logger.exception("[memory-post] 评论监听失败")

    # ------------------------------------------------------------------ 定时
    async def initialize(self) -> None:
        if not bool(self.config.get("enabled", True)):
            return
        self._task = asyncio.create_task(self._loop())
        if bool(self.config.get("comment_watch", False)):
            self._comment_task = asyncio.create_task(self._comment_watch_loop())

    async def terminate(self) -> None:
        for task in (self._task, self._comment_task):
            if task:
                task.cancel()
        self._task = None
        self._comment_task = None

    async def _loop(self) -> None:
        while True:
            hhmm = str(self.config.get("schedule_time") or "21:30")
            try:
                hour, minute = (int(x) for x in hhmm.split(":"))
            except ValueError:
                hour, minute = 21, 30
            now = datetime.now()
            target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if target <= now:
                target += timedelta(days=1)
            wait = max(30.0, (target - now).total_seconds())
            await asyncio.sleep(wait)
            try:
                result = await asyncio.to_thread(self._generate_sync)
                logger.info(f"[memory-post] 定时生成：{result}")
            except Exception:
                logger.exception("[memory-post] 定时生成失败")
            if bool(self.config.get("reply_comments", False)) and not bool(self.config.get("comment_watch", False)):
                try:
                    data = await asyncio.to_thread(self._comments_sync, bool(self.config.get("comments_send", False)))
                    logger.info(f"[memory-post] 评论回复：{data}")
                except Exception:
                    logger.exception("[memory-post] 评论回复失败")

    def _publish_draft_sync(self, draft_id: str) -> dict:
        cfg = self._core_config()
        store = Store(self._base / "state.json")
        draft = store.get_draft(draft_id)
        if not draft:
            return {"ok": False, "issues": [f"找不到草稿 {draft_id}"]}
        text = str(draft.get("text") or "")
        image = str(draft.get("image") or "")
        media = [image] if image and Path(image).exists() else []
        adapter = str(cfg["publish"]["adapter"] or "dry_run")
        try:
            if adapter in ("qzone_daemon", "qzone_native"):
                payload = QzoneAPI(cfg).publish(text, media=media)
            else:
                payload = dry_run.publish(text, outbox=str(self._base / "outbox"))
        except (QzoneError, QzoneNativeError, RuntimeError) as exc:
            return {"ok": False, "text": text, "issues": [f"publish_failed:{exc}"]}
        store.remove_draft(draft_id)
        store.add_post(text, fid=str(payload.get("fid") or ""), used=draft.get("used") or [], variant=str(draft.get("variant") or ""), image=image)
        return {"ok": True, "published": True, "text": text, "payload": payload}

    # ------------------------------------------------------------------ 指令
    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("记忆说说")
    async def mem_post_cmd(self, event: AstrMessageEvent, sub: str = ""):
        """手动生成或发布一条记忆说说。用法：/记忆说说 预览 | /记忆说说 发布"""
        if sub.strip() == "预览":
            result = await asyncio.to_thread(self._generate_sync)
            yield event.plain_result(("草稿：\n" if not result.get("published") else "已发布：\n") + result.get("text", "") + ("\n检查：" + "；".join(result.get("issues") or []) if result.get("issues") else ""))
            return
        if sub.strip() == "发布":
            old = self.config.get("mode")
            self.config["mode"] = "publish"
            try:
                result = await asyncio.to_thread(self._generate_sync)
            finally:
                self.config["mode"] = old
            yield event.plain_result(result.get("text", "") if result.get("ok") else "失败：" + "；".join(result.get("issues") or []))
            return
        if sub.strip() == "草稿":
            store = Store(self._base / "state.json")
            items = store.drafts()
            yield event.plain_result("\n".join(f"[{x.get('id')}] {x.get('text')}" for x in items) or "没有草稿")
            return
        if sub.strip().startswith("发"):
            draft_id = sub.strip()[1:].strip()
            if not draft_id:
                yield event.plain_result("用法：/记忆说说 发 <草稿id>")
                return
            result = await asyncio.to_thread(self._publish_draft_sync, draft_id)
            yield event.plain_result(result.get("text", "") if result.get("ok") else "失败：" + "；".join(result.get("issues") or []))
            return
        if sub.strip() == "回评论":
            data = await asyncio.to_thread(self._comments_sync, False)
            items = data.get("comments") or []
            yield event.plain_result("\n".join(f"{x['who']}：{x['reply']}" for x in items) or "没有新评论")
            return
        yield event.plain_result("用法：/记忆说说 预览 / 草稿 / 发 <id> / 发布 / 回评论")

    @filter.llm_tool()
    async def mem_post_preview(self, event: AstrMessageEvent):
        """生成一条记忆说说草稿，不发布。"""
        result = await asyncio.to_thread(self._generate_sync)
        return result.get("text", "") or "生成失败"

    @filter.llm_tool()
    async def mem_post_comments(self, event: AstrMessageEvent, send: bool = False):
        """拉最近说说的评论并生成回复；send=true 才真正发布回复。

        Args:
            send(boolean): 是否真的把回复发出去，默认只预览。
        """
        data = await asyncio.to_thread(self._comments_sync, bool(send))
        items = data.get("comments") or []
        if not items:
            return "没有新评论"
        return "\n".join(f"{x['who']}：{x['reply']}" for x in items)
