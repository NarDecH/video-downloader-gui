#!/usr/bin/env python3
"""โปรเซสเบราว์เซอร์ในแอป — รัน pywebview บน main thread ของโปรเซสตัวเอง

pywebview บังคับ webview.start() บน MainThread ของโปรเซส จึงต้องแยกเบราว์เซอร์
ออกเป็นโปรเซสลูก ส่วนแอปหลัก (tkinter) สั่งงานผ่าน TCP บน 127.0.0.1 —
คำสั่ง JSON หนึ่งบรรทัดต่อการเชื่อมต่อ ตอบกลับ JSON หนึ่งบรรทัด:

  {"cmd": "ping"}                      -> {"ok": true}
  {"cmd": "url"}                       -> {"ok": true, "url": "..."}
  {"cmd": "navigate", "url": "..."}    -> {"ok": true}
  {"cmd": "scan", "js": "..."}         -> {"ok": true, "result": <evaluate_js>}
  {"cmd": "quit"}                      -> {"ok": true} แล้วปิดหน้าต่าง/จบโปรเซส

เรียกใช้: python browser_app.py --port N --url U   (หรือ main.py --vdl-browser ใน EXE)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import socket
import sys
import threading

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from logger import get_log_dir, setup_logging  # noqa: E402

log = logging.getLogger("browser")

_BROWSER_SIZE = (1100, 780)


def _handle(req: dict, win) -> dict:
    cmd = req.get("cmd")
    if cmd == "ping":
        return {"ok": True}
    if win is None:
        return {"ok": False, "error": "window not ready"}
    if cmd == "url":
        return {"ok": True, "url": win.get_current_url()}
    if cmd == "navigate":
        win.load_url(str(req.get("url") or ""))
        return {"ok": True}
    if cmd == "scan":
        result = win.evaluate_js(str(req.get("js") or "document.title"))
        return {"ok": True, "result": result}
    if cmd == "quit":
        threading.Timer(0.2, win.destroy).start()  # ให้ response ส่งถึงก่อนปิด
        return {"ok": True}
    return {"ok": False, "error": f"unknown cmd: {cmd}"}


def _ipc_server(port: int, win_holder: dict) -> None:
    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", port))
        srv.listen(4)
        log.info("ipc server listening on 127.0.0.1:%d", port)
        while True:
            conn, _addr = srv.accept()
            try:
                conn.settimeout(60)
                buf = b""
                while not buf.endswith(b"\n"):
                    chunk = conn.recv(65536)
                    if not chunk:
                        break
                    buf += chunk
                if not buf.strip():
                    continue
                req = json.loads(buf.decode("utf-8"))
                try:
                    resp = _handle(req, win_holder.get("win"))
                except Exception as exc:  # noqa: BLE001
                    log.exception("cmd %s failed", req.get("cmd"))
                    resp = {"ok": False, "error": str(exc)}
                conn.sendall((json.dumps(resp, ensure_ascii=False) + "\n").encode("utf-8"))
            except Exception:  # noqa: BLE001
                log.exception("ipc connection error")
            finally:
                try:
                    conn.close()
                except OSError:
                    pass
    except Exception:  # noqa: BLE001
        log.exception("ipc server died")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Video Downloader in-app browser subprocess")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--url", required=True)
    parser.add_argument("--width", type=int, default=_BROWSER_SIZE[0])
    parser.add_argument("--height", type=int, default=_BROWSER_SIZE[1])
    args, _unknown = parser.parse_known_args(argv)  # ข้าม flag อื่น เช่น --vdl-browser จาก EXE

    setup_logging(
        "browser",
        os.path.join(get_log_dir(), "vdl-browser.log"),
    )
    log.info("browser subprocess start: url=%s port=%d", args.url, args.port)

    try:
        import webview
    except ImportError:
        log.exception("pywebview is not installed")
        return 2

    win_holder: dict = {"win": None}
    try:
        win_holder["win"] = webview.create_window(
            "Video Downloader — Browser", args.url, width=args.width, height=args.height,
        )
    except Exception:  # noqa: BLE001
        log.exception("create_window failed")
        return 1

    threading.Thread(target=_ipc_server, args=(args.port, win_holder), daemon=True).start()
    try:
        webview.start()  # block จนปิดหน้าต่างทั้งหมด
        log.info("browser subprocess end")
    except Exception:  # noqa: BLE001
        log.exception("webview.start failed (WebView2 runtime missing?)")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
