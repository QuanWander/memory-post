# -*- coding: utf-8 -*-
"""HTTP 适配器：给其他 bot / 脚本调用，也自带「鲸语拾光」页面。

启动：
    python -m adapters.http.server --config config.json --port 8766

页面：
    http://127.0.0.1:8766/view/
"""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from mempost import service
from mempost.state import Store

CONFIG = os.environ.get("MEMPOST_CONFIG", "config.json")
VIEW_DIR = Path(__file__).resolve().parents[2] / "views" / "whale-words"


def _config_path() -> Path:
    return Path(CONFIG).resolve()


def _store() -> Store:
    return Store(_config_path().parent / "state.json")


def _send(handler, payload: dict, code: int = 200) -> None:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _send_file(handler, path: Path) -> None:
    if not path.is_file():
        _send(handler, {"ok": False, "error": "not found"}, 404)
        return
    data = path.read_bytes()
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    handler.send_response(200)
    handler.send_header("Content-Type", ctype + ("; charset=utf-8" if ctype.startswith("text/") or ctype.endswith("javascript") else ""))
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/health":
            _send(self, {"ok": True, "service": "memory-post"})
            return
        if path == "/v1/doctor":
            _send(self, service.doctor(CONFIG))
            return
        if path == "/v1/drafts":
            _send(self, {"drafts": service.drafts(CONFIG), "adapter": service.doctor(CONFIG).get("adapter")})
            return
        if path == "/v1/drafts/image":
            draft_id = (parse_qs(parsed.query).get("id") or [""])[0]
            draft = _store().get_draft(draft_id)
            if not draft or not draft.get("image"):
                _send(self, {"ok": False, "error": "not found"}, 404)
                return
            f = Path(str(draft["image"]))
            if not f.is_file():
                _send(self, {"ok": False, "error": "not found"}, 404)
                return
            ctype = mimetypes.guess_type(str(f))[0] or "image/png"
            data = base64.b64encode(f.read_bytes()).decode("ascii")
            _send(self, {"data": f"data:{ctype};base64,{data}"})
            return
        if path in ("/view", "/view/"):
            _send_file(self, VIEW_DIR / "index.html")
            return
        if path.startswith("/view/"):
            name = Path(path[len("/view/"):]).name
            _send_file(self, VIEW_DIR / name)
            return
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/view/")
            self.end_headers()
            return
        _send(self, {"ok": False, "error": "not found"}, 404)

    def do_POST(self):  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            _send(self, {"ok": False, "error": "bad json"}, 400)
            return
        try:
            if path == "/v1/preview":
                data = service.preview(CONFIG, with_image=bool(body.get("with_image")))
            elif path == "/v1/generate":
                data = service.preview(CONFIG, with_image=bool(body.get("with_image")))
            elif path == "/v1/publish":
                data = service.publish(CONFIG, force=bool(body.get("force")), with_image=bool(body.get("with_image")))
            elif path == "/v1/drafts/publish":
                data = service.publish_draft(CONFIG, str(body.get("id") or ""))
            elif path == "/v1/drafts/delete":
                data = {"deleted": _store().remove_draft(str(body.get("id") or ""))}
            elif path == "/v1/comments":
                data = {"comments": service.comments(CONFIG, send=bool(body.get("send")))}
            else:
                _send(self, {"ok": False, "error": "not found"}, 404)
                return
        except Exception as exc:  # noqa: BLE001
            _send(self, {"ok": False, "error": str(exc)}, 500)
            return
        _send(self, data)

    def log_message(self, fmt, *args):  # pragma: no cover
        sys.stderr.write("[memory-post-http] " + fmt % args + "\n")


def main() -> None:
    global CONFIG
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=CONFIG)
    parser.add_argument("--port", type=int, default=8766)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()
    CONFIG = args.config
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f"memory-post HTTP listening on http://{args.host}:{args.port}")
    print(f"鲸语拾光: http://{args.host}:{args.port}/view/")
    server.serve_forever()


if __name__ == "__main__":
    main()
