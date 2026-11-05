# -*- coding: utf-8 -*-
"""对外服务层：CLI / MCP / HTTP 共用，不依赖 AstrBot。"""

from __future__ import annotations

import json
from pathlib import Path

from . import config as cfgmod
from .comments import new_comments, normalize_post, reply_text, self_uin
from .composer import ANGLES, ANGLE_MAP, LLM, compose
from .images import build_prompt, generate
from .lint import Issue, lint
from .privacy import PrivacyGuard
from .privacy_auto import discover, judge
from .publish import dry_run
from .publish.qzone import QzoneError
from .publish.qzone_native import QzoneNativeError
from .qzone_api import QzoneAPI
from .selfimage import describe, pick
from .sources import diary_digest, load_diary, load_memories
from .state import Store

DEFAULT_PERSONA = "你是 DeepSeek 小鲸鱼，QQ 群里的群友。说话短、口语、有立场，不总结、不说教。"


def _load(config_path: str | Path) -> tuple[dict, Path]:
    path = Path(config_path).resolve()
    return cfgmod.load(path), path


def _persona(cfg: dict, path: Path) -> str:
    raw = cfgmod.resolve(cfg, "persona_file", path)
    if raw and Path(raw).exists():
        return Path(raw).read_text(encoding="utf-8")
    return DEFAULT_PERSONA


def _guard(cfg: dict) -> PrivacyGuard:
    privacy = cfg.get("privacy") or {}
    return PrivacyGuard(privacy.get("entities") or [], privacy.get("deny_words") or [])


def has_material(memories, diary, guard: PrivacyGuard) -> bool:
    usable = [m for m in memories if not guard.scan(m.text)]
    return bool(usable) or bool(diary)


def angles() -> list[dict]:
    return [{"id": a["id"], "label": a["label"]} for a in ANGLES]


def preview(
    config_path: str | Path,
    *,
    with_image: bool = False,
    angle_id: str | None = None,
    save_draft: bool = True,
) -> dict:
    cfg, path = _load(config_path)
    privacy = cfg.get("privacy") or {}
    memories = load_memories(cfgmod.resolve(cfg, "memory_file", path))
    diary = load_diary(cfgmod.resolve(cfg, "diary_dir", path), int(cfg.get("recent_days") or 3))
    guard = _guard(cfg)
    if bool(privacy.get("skip_if_no_material", True)) and not has_material(memories, diary, guard):
        return {"ok": False, "skipped": True, "reason": "no_material", "text": "", "issues": [], "used": []}
    diary_text = diary_digest(diary)
    llm = LLM(cfg)
    auto_hints: list[str] = []
    if bool(privacy.get("auto_entities", True)):
        auto_hints = discover(
            llm,
            [m.text for m in memories],
            diary_text,
            path.parent / "state" / "privacy_entities.json",
        )
    store = Store(path.parent / "state.json")
    variant = pick(cfg, len(store.posts()))
    result = compose(
        cfg,
        _persona(cfg, path),
        variant,
        memories,
        diary_text,
        store.recent_texts(7, include_drafts=True),
        guard,
        llm=llm,
        angle_id=angle_id,
    )
    issues = lint(
        result.text,
        guard,
        min_chars=int(privacy.get("min_chars") or 18),
        max_chars=int(privacy.get("max_chars") or 80),
        recent=store.recent_texts(7, include_drafts=True),
        similarity_threshold=float(privacy.get("similarity_threshold") or 0.55),
    )
    if not issues and bool(privacy.get("llm_judge", True)):
        hits = judge(llm, result.text, auto_hints)
        if hits:
            issues.append(Issue("privacy_llm", "模型判断可能含：" + "、".join(hits)))
    image_path = ""
    if with_image and not issues:
        try:
            image_path = generate(build_prompt("自拍或日常随手拍", describe(variant), scene=result.text), cfg, path.parent / "outbox" / "images")
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "text": result.text, "issues": issues + [f"image:{exc}"], "image": ""}
    if issues and save_draft:
        store.add_draft(
            result.text,
            issues=[str(i) for i in issues],
            details=[i.to_dict() for i in issues],
            used=result.used_memories,
            variant=str(variant.get("name")),
            image=image_path,
            angle=result.angle_id,
            angle_label=result.angle_label,
        )
    return {
        "ok": not issues,
        "text": result.text,
        "issues": [str(i) for i in issues],
        "details": [i.to_dict() for i in issues],
        "image": image_path,
        "variant": variant.get("name"),
        "used": result.used_memories,
        "angle": result.angle_id,
        "angle_label": result.angle_label,
    }


def publish(config_path: str | Path, *, force: bool = False, with_image: bool = False) -> dict:
    cfg, path = _load(config_path)
    result = preview(config_path, with_image=with_image)
    if result.get("issues") and not force:
        return {"ok": False, "published": False, **result}
    store = Store(path.parent / "state.json")
    adapter = str((cfg.get("publish") or {}).get("adapter") or "dry_run")
    media = [result["image"]] if result.get("image") else []
    try:
        if adapter in ("qzone_daemon", "qzone_native"):
            payload = QzoneAPI(cfg).publish(result["text"], media=media)
        else:
            payload = dry_run.publish(result["text"], outbox=str(path.parent / "outbox"))
    except (QzoneError, QzoneNativeError, RuntimeError) as exc:
        store.add_draft(result["text"], issues=[f"publish_failed:{exc}"], used=result.get("used") or [])
        return {"ok": False, "published": False, "text": result["text"], "issues": [f"publish_failed:{exc}"]}
    store.add_post(result["text"], fid=str(payload.get("fid") or ""), used=result.get("used") or [], image=result.get("image") or "")
    return {"ok": True, "published": True, "text": result["text"], "payload": payload}


def comments(config_path: str | Path, *, send: bool = False, limit: int = 5) -> list[dict]:
    cfg, path = _load(config_path)
    guard = _guard(cfg)
    persona = _persona(cfg, path)
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
    store = Store(path.parent / "state.json")
    replied = store.replied_ids()
    todo = [c for c in new_comments(posts, me) if f"{c['fid']}:{c['commentid']}" not in replied]
    out: list[dict] = []
    for comment in todo[:limit]:
        post_text = next((p["content"] for p in posts if p["fid"] == comment["fid"]), "")
        text = reply_text(cfg, persona, post_text, comment, guard)
        item = {"comment": comment, "reply": text, "sent": False}
        if send:
            api.reply(hostuin=me, fid=comment["fid"], commentid=comment["commentid"], comment_uin=comment["uin"], content=text)
            store.mark_replied(f"{comment['fid']}:{comment['commentid']}")
            item["sent"] = True
        out.append(item)
    return out


def drafts(config_path: str | Path) -> list[dict]:
    cfg, path = _load(config_path)
    return Store(path.parent / "state.json").drafts()


def publish_draft(config_path: str | Path, draft_id: str) -> dict:
    cfg, path = _load(config_path)
    store = Store(path.parent / "state.json")
    draft = store.get_draft(str(draft_id))
    if not draft:
        return {"ok": False, "issues": [f"找不到草稿 {draft_id}"]}
    text = str(draft.get("text") or "")
    image = str(draft.get("image") or "")
    media = [image] if image and Path(image).exists() else []
    adapter = str((cfg.get("publish") or {}).get("adapter") or "dry_run")
    try:
        if adapter in ("qzone_daemon", "qzone_native"):
            payload = QzoneAPI(cfg).publish(text, media=media)
        else:
            payload = dry_run.publish(text, outbox=str(path.parent / "outbox"))
    except (QzoneError, QzoneNativeError, RuntimeError) as exc:
        return {"ok": False, "text": text, "issues": [f"publish_failed:{exc}"]}
    store.remove_draft(str(draft_id))
    store.add_post(text, fid=str(payload.get("fid") or ""), used=draft.get("used") or [], variant=str(draft.get("variant") or ""), image=image)
    return {"ok": True, "published": True, "text": text, "payload": payload}


def delete_post(config_path: str | Path, fid: str) -> dict:
    cfg, path = _load(config_path)
    return QzoneAPI(cfg).delete(fid)


def update_draft(config_path: str | Path, draft_id: str, text: str) -> dict:
    cfg, path = _load(config_path)
    guard = _guard(cfg)
    store = Store(path.parent / "state.json")
    draft = store.get_draft(str(draft_id))
    if not draft:
        return {"ok": False, "issues": [f"找不到草稿 {draft_id}"]}
    privacy = cfg.get("privacy") or {}
    issues = lint(
        str(text or ""),
        guard,
        min_chars=int(privacy.get("min_chars") or 18),
        max_chars=int(privacy.get("max_chars") or 80),
        recent=[],
        similarity_threshold=float(privacy.get("similarity_threshold") or 0.55),
    )
    if issues:
        return {"ok": False, "issues": [str(i) for i in issues]}
    item = store.update_draft(str(draft_id), text=str(text or "").strip(), issues=[])
    return {"ok": True, "draft": item}


def regenerate_draft(config_path: str | Path, draft_id: str, angle_id: str | None = None) -> dict:
    cfg, path = _load(config_path)
    store = Store(path.parent / "state.json")
    draft = store.get_draft(str(draft_id))
    if not draft:
        return {"ok": False, "issues": [f"找不到草稿 {draft_id}"]}
    result = preview(config_path, angle_id=angle_id, save_draft=False)
    if result.get("skipped") or not result.get("ok"):
        return result
    item = store.replace_draft(
        str(draft_id),
        result["text"],
        used=result.get("used") or [],
        angle=str(result.get("angle") or ""),
        angle_label=str(result.get("angle_label") or ""),
        issues=[],
        image=str(draft.get("image") or ""),
    )
    return {"ok": True, "draft": item, "text": result["text"], "used": result.get("used") or [], "angle": result.get("angle")}


def _detect_paths(config_path: Path) -> dict:
    roots = [Path.cwd() / "data", config_path.parent / "data", config_path.parent]
    detected = {"memory_file": "", "diary_dir": "", "persona_file": ""}
    for root in roots:
        memory = root / "plugin_data" / "astrbot_plugin_master_aware" / "memory.json"
        if memory.exists() and not detected["memory_file"]:
            detected["memory_file"] = str(memory)
    for diary in (Path.cwd() / "大肥鱼日记", config_path.parent / "大肥鱼日记"):
        if diary.exists():
            if not detected["diary_dir"]:
                detected["diary_dir"] = str(diary)
            personas = sorted((diary / "小鲸鱼" / "人格").glob("*.md"))
            if personas and not detected["persona_file"]:
                detected["persona_file"] = str(personas[-1])
            break
    return detected


def onboarding_status(config_path: str | Path) -> dict:
    cfg, path = _load(config_path)
    return {
        "memory_file": cfgmod.resolve(cfg, "memory_file", path),
        "diary_dir": cfgmod.resolve(cfg, "diary_dir", path),
        "persona_file": cfgmod.resolve(cfg, "persona_file", path),
        "detected": _detect_paths(path),
    }


def apply_onboarding(config_path: str | Path, payload: dict) -> dict:
    cfg, path = _load(config_path)
    updates = {}
    for key in ("memory_file", "diary_dir", "persona_file"):
        value = str((payload or {}).get(key) or "").strip()
        if not value:
            continue
        if not Path(value).exists():
            return {"ok": False, "error": f"{key} 不存在：{value}"}
        updates[key] = value
    if not updates:
        return {"ok": False, "error": "没有可保存的路径"}
    cfg.update(updates)
    cfgmod.save(path, cfg)
    return {"ok": True, "config": {k: cfg.get(k) for k in updates}}


def doctor(config_path: str | Path) -> dict:
    cfg, path = _load(config_path)
    info = {
        "memory_file": cfgmod.resolve(cfg, "memory_file", path),
        "diary_dir": cfgmod.resolve(cfg, "diary_dir", path),
        "persona_file": cfgmod.resolve(cfg, "persona_file", path),
        "memories": len(load_memories(cfgmod.resolve(cfg, "memory_file", path))),
        "llm_key": bool((cfg.get("llm") or {}).get("api_key")),
        "adapter": (cfg.get("publish") or {}).get("adapter"),
        "images": (cfg.get("images") or {}).get("provider"),
    }
    info["ok"] = bool(info["memories"]) and info["llm_key"]
    return info
