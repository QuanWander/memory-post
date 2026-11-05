# -*- coding: utf-8 -*-
"""命令行入口：init / doctor / preview / publish。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config as cfgmod
from . import service
from .comments import new_comments, normalize_post, reply_text, self_uin
from .composer import LLM, LLMError, compose
from .images import build_prompt, generate
from .lint import lint
from .privacy import PrivacyGuard
from .publish import dry_run
from .publish.qzone import QzoneDaemon, QzoneError
from .qzone_api import QzoneAPI
from .selfimage import describe, pick
from .sources import diary_digest, load_diary, load_memories
from .scheduler import run_daily
from .state import Store

DEFAULT_PERSONA = """你是 DeepSeek 小鲸鱼，QQ 群里的群友，不是客服。说话短、口语、有立场，不总结、不说教。"""


def _load(args) -> tuple[dict, Path]:
    path = Path(args.config).resolve()
    if not path.exists():
        raise SystemExit(f"配置文件不存在：{path}\n先运行：python -m mempost.cli init --config {path}")
    return cfgmod.load(path), path


def _persona(cfg: dict, config_path: Path) -> str:
    raw = cfgmod.resolve(cfg, "persona_file", config_path)
    if raw and Path(raw).exists():
        return Path(raw).read_text(encoding="utf-8")
    return DEFAULT_PERSONA


def _guard(cfg: dict) -> PrivacyGuard:
    privacy = cfg.get("privacy") or {}
    return PrivacyGuard(privacy.get("entities") or [], privacy.get("deny_words") or [])


def _prepare(cfg: dict, config_path: Path, *, with_image: bool = False):
    guard = _guard(cfg)
    memories = load_memories(cfgmod.resolve(cfg, "memory_file", config_path))
    diary = load_diary(cfgmod.resolve(cfg, "diary_dir", config_path), int(cfg.get("recent_days") or 3))
    store = Store(config_path.parent / "state.json")
    variant = pick(cfg, len(store.posts()))
    persona = _persona(cfg, config_path)
    result = compose(cfg, persona, variant, memories, diary_digest(diary), store.recent_texts(7, include_drafts=True), guard)
    issues = lint(
        result.text,
        guard,
        min_chars=int((cfg.get("privacy") or {}).get("min_chars") or 18),
        max_chars=int((cfg.get("privacy") or {}).get("max_chars") or 80),
        recent=store.recent_texts(7, include_drafts=True),
        similarity_threshold=float((cfg.get("privacy") or {}).get("similarity_threshold") or 0.55),
    )
    image_path = ""
    if with_image and not issues:
        try:
            prompt = build_prompt("自拍或日常随手拍", describe(variant))
            image_path = generate(prompt, cfg, config_path.parent / "outbox" / "images")
        except Exception as exc:  # noqa: BLE001
            print(f"[warn] 配图失败，按纯文字继续：{exc}", file=sys.stderr)
    return result, issues, variant, image_path, store


def cmd_init(args) -> int:
    import copy

    path = Path(args.config).resolve()
    if path.exists() and not args.force:
        print(f"已存在：{path}（要覆盖加 --force）")
        return 0
    cfg = copy.deepcopy(cfgmod.DEFAULT)
    if args.preset == "astrbot":
        _detect_astrbot(cfg)
    if args.memory_file:
        cfg["memory_file"] = args.memory_file
    if args.diary_dir:
        cfg["diary_dir"] = args.diary_dir
    if args.persona_file:
        cfg["persona_file"] = args.persona_file
    if args.api_key:
        cfg["llm"]["api_key"] = args.api_key
    if args.model:
        cfg["llm"]["model"] = args.model
    if args.time:
        cfg["schedule"]["time"] = args.time
    if args.mode:
        cfg["mode"] = args.mode
    if args.adapter:
        cfg["publish"]["adapter"] = args.adapter
    cfgmod.save(path, cfg)
    print(f"已生成配置：{path}")
    print("下一步：mem-post doctor，然后 mem-post preview")
    return 0


def _detect_astrbot(cfg: dict) -> None:
    """在常见的 AstrBot 目录结构里猜路径，猜不到就留空。"""
    candidates = [Path.cwd() / "data", Path.cwd() / "AstrBot" / "data", Path.cwd()]
    for data in candidates:
        mem = data / "plugin_data" / "astrbot_plugin_master_aware" / "memory.json"
        if mem.exists():
            cfg["memory_file"] = str(mem)
            qzone = data / "plugin_data" / "astrbot_plugin_qzone_ultra" / "state.json"
            if qzone.exists():
                cfg["publish"]["qzone_state_file"] = str(qzone)
            break
    diary = Path.cwd() / "大肥鱼日记"
    if diary.exists():
        cfg["diary_dir"] = str(diary)
        personas = sorted((diary / "小鲸鱼" / "人格").glob("*.md"))
        if personas:
            cfg["persona_file"] = str(personas[-1])


def cmd_doctor(args) -> int:
    cfg, path = _load(args)
    ok = True
    for key in ("memory_file", "diary_dir", "persona_file"):
        resolved = cfgmod.resolve(cfg, key, path)
        exists = bool(resolved) and Path(resolved).exists()
        print(f"{key}: {'OK' if exists else 'MISSING'} {resolved}")
        ok = ok and exists
    memories = load_memories(cfgmod.resolve(cfg, "memory_file", path))
    print(f"memories: {len(memories)}")
    print(f"llm.api_key: {'SET' if (cfg.get('llm') or {}).get('api_key') else 'EMPTY'}")
    print(f"publish.adapter: {(cfg.get('publish') or {}).get('adapter')}")
    print(f"images.provider: {(cfg.get('images') or {}).get('provider')}")
    return 0 if ok else 1


def cmd_preview(args) -> int:
    result = service.preview(args.config, with_image=args.image)
    print("—— 说说 ——")
    print(result.get("text", ""))
    print(f"（{len(result.get('text', ''))} 字，形象：{result.get('variant')}）")
    used = result.get("used") or []
    if used:
        print("—— 用到的记忆 ——")
        for item in used:
            print("-", item)
    if result.get("image"):
        print("—— 配图 ——")
        print(result["image"])
    issues = result.get("issues") or []
    if issues:
        print("—— 检查 ——")
        for issue in issues:
            print(issue)
        print("已存为草稿。")
        return 1
    print("—— 检查 ——\n通过")
    return 0


def cmd_publish(args) -> int:
    result = service.publish(args.config, force=args.force, with_image=args.image)
    if not result.get("ok"):
        for issue in result.get("issues") or []:
            print(issue)
        print("未通过检查或发布失败，已存草稿。")
        return 1
    print("已发布：" + json.dumps(result.get("payload") or {}, ensure_ascii=False)[:300])
    return 0


def cmd_comments(args) -> int:
    cfg, path = _load(args)
    guard = _guard(cfg)
    store = Store(path.parent / "state.json")
    persona = _persona(cfg, path)
    api = QzoneAPI(cfg)
    me = api.uin
    try:
        raw_posts = api.feeds(limit=5)
    except QzoneError as exc:
        print(f"拉取说说失败：{exc}")
        return 1
    posts = [normalize_post(x) for x in raw_posts]
    for post in posts:
        if post.get("fid"):
            try:
                detail = api.detail(post["fid"])
                comments = detail.get("comments") or detail.get("commentList") or []
                if comments:
                    post["comments"] = comments
            except QzoneError:
                pass
    replied = store.replied_ids()
    todo = [c for c in new_comments(posts, me) if f"{c['fid']}:{c['commentid']}" not in replied]
    if not todo:
        print("没有新评论。")
        return 0
    for comment in todo[:5]:
        post_text = next((p["content"] for p in posts if p["fid"] == comment["fid"]), "")
        text = reply_text(cfg, persona, post_text, comment, guard)
        who = comment["name"] or comment["uin"]
        if args.send:
            try:
                api.reply(hostuin=me, fid=comment["fid"], commentid=comment["commentid"], comment_uin=comment["uin"], content=text)
                store.mark_replied(f"{comment['fid']}:{comment['commentid']}")
                print(f"已回复 {who}：{text}")
            except QzoneError as exc:
                print(f"回复失败：{exc}")
        else:
            print(f"[dry-run] 回复 {who}：{text}")
    return 0


def cmd_drafts(args) -> int:
    items = service.drafts(args.config)
    if not items:
        print("没有草稿。")
        return 0
    for item in items:
        print("[{}] {}  {}".format(item.get("id"), item.get("created_at"), item.get("text")))
        for issue in item.get("issues") or []:
            print("    !", issue)
    print("\n审核后：mem-post approve <id> --config ...")
    return 0


def cmd_approve(args) -> int:
    result = service.publish_draft(args.config, args.id)
    if not result.get("ok"):
        print("没有发布：" + "；".join(result.get("issues") or []))
        return 1
    print("已发布：" + json.dumps(result.get("payload") or {}, ensure_ascii=False)[:300])
    return 0


def cmd_delete(args) -> int:
    result = service.delete_post(args.config, args.fid)
    print("已删除" if result else result)
    return 0


def cmd_run(args) -> int:
    cfg, path = _load(args)
    hhmm = str((cfg.get("schedule") or {}).get("time") or "21:30")

    def job() -> None:
        argv = ["--config", str(path), "publish"]
        cmd_publish(argparse.Namespace(config=str(path), image=args.image, force=False))

    print(f"每日 {hhmm} 生成并发布；草稿模式也会先生成。Ctrl+C 退出。")
    run_daily(job, hhmm, stamp_file=path.parent / "last_run.txt")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mem-post")
    parser.add_argument("--config", default="config.json")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", default=argparse.SUPPRESS)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", parents=[common])
    p_init.add_argument("--force", action="store_true")
    p_init.add_argument("--preset", choices=["astrbot"], default="")
    p_init.add_argument("--memory-file", default="")
    p_init.add_argument("--diary-dir", default="")
    p_init.add_argument("--persona-file", default="")
    p_init.add_argument("--api-key", default="")
    p_init.add_argument("--model", default="")
    p_init.add_argument("--time", default="")
    p_init.add_argument("--mode", choices=["draft", "publish"], default="")
    p_init.add_argument("--adapter", choices=["dry_run", "qzone_daemon"], default="")
    p_init.set_defaults(func=cmd_init)

    p_doc = sub.add_parser("doctor", parents=[common])
    p_doc.set_defaults(func=cmd_doctor)

    p_prev = sub.add_parser("preview", parents=[common])
    p_prev.add_argument("--image", action="store_true")
    p_prev.set_defaults(func=cmd_preview)

    p_pub = sub.add_parser("publish", parents=[common])
    p_pub.add_argument("--image", action="store_true")
    p_pub.add_argument("--force", action="store_true")
    p_pub.set_defaults(func=cmd_publish)

    p_com = sub.add_parser("comments", parents=[common])
    p_com.add_argument("--send", action="store_true")
    p_com.set_defaults(func=cmd_comments)

    p_drafts = sub.add_parser("drafts", parents=[common])
    p_drafts.set_defaults(func=cmd_drafts)

    p_approve = sub.add_parser("approve", parents=[common])
    p_approve.add_argument("id")
    p_approve.set_defaults(func=cmd_approve)

    p_delete = sub.add_parser("delete", parents=[common])
    p_delete.add_argument("fid")
    p_delete.set_defaults(func=cmd_delete)

    p_run = sub.add_parser("run", parents=[common])
    p_run.add_argument("--image", action="store_true")
    p_run.set_defaults(func=cmd_run)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
