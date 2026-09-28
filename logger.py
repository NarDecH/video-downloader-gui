#!/usr/bin/env python3
"""ระบบบันทึก log สำหรับ Video Downloader — ไว้วิเคราะห์และดีบัก

- ไฟล์ log หมุนเวียนที่ %APPDATA%/video-downloader/logs/vdl.log (สูงสุด 1 MB × 5 ไฟล์สำรอง, UTF-8)
- ระดับ DEBUG ลงไฟล์เสมอ (ครบถ้วนเพื่อดีบัก); แสดงคอนโซลเฉพาะตอนรันจากซอร์สหรือตั้ง VDL_CONSOLE=1
- YtDlpLogger เป็น adapter ดึงข้อความภายในของ yt-dlp (debug/info/warning/error) เข้า log เดียวกัน
"""
from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import sys

APP_NAME = "video-downloader"
LOG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~/.config"), APP_NAME, "logs")
LOG_PATH = os.path.join(LOG_DIR, "vdl.log")

_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-7s [%(name)s] %(message)s"
_DATEFMT = "%Y-%m-%d %H:%M:%S"


def get_log_dir() -> str:
    return LOG_DIR


def get_log_path() -> str:
    return LOG_PATH


def setup_logging(logger_name: str = "vdl", log_path: str | None = None) -> str:
    """ตั้งค่า log หมุนเวียน (idempotent — เรียกซ้ำไม่เติม handler) คืนพาธไฟล์ log

    log_path แยกได้ตามโปรเซส (เช่น โปรเซสเบราว์เซอร์ใช้ vdl-browser.log)
    เพราะ RotatingFileHandler หลายโปรเซสแชร์ไฟล์เดียวจะชนกันตอน rotate
    """
    path = log_path or LOG_PATH
    root = logging.getLogger(logger_name)
    root.setLevel(logging.DEBUG)
    if root.handlers:
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fh = logging.handlers.RotatingFileHandler(path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
    fh.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
    fh.setLevel(logging.DEBUG)
    root.addHandler(fh)
    if not getattr(sys, "frozen", False) or os.environ.get("VDL_CONSOLE"):
        ch = logging.StreamHandler(sys.stderr)
        ch.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))
        ch.setLevel(logging.INFO)
        root.addHandler(ch)
    return path


def session_header(app: str, version: str) -> None:
    """บันทึกหัวเซสชัน: เวอร์ชัน/ระบบ/สภาพแวดล้อม — ใช้เทียบปัญหาข้ามเครื่อง"""
    log = logging.getLogger("vdl.app")
    log.info("=" * 70)
    log.info("session start: %s v%s", app, version)
    log.info(
        "python=%s platform=%s frozen=%s log=%s",
        sys.version.split()[0], platform.platform(), bool(getattr(sys, "frozen", False)), LOG_PATH,
    )


class YtDlpLogger:
    """Adapter ส่งข้อความภายในของ yt-dlp เข้า log (opts["logger"] ของ YoutubeDL)

    yt-dlp ส่งข้อความทั่วไปผ่าน debug() โดยข้อความสำคัญมักนำหน้าด้วยแท็ก เช่น
    "[download] Destination: ..." — แยกระดับ: [debug] → DEBUG, ที่เหลือ → INFO
    """

    def __init__(self, name: str = "vdl.ytdlp") -> None:
        self._log = logging.getLogger(name)

    def debug(self, msg) -> None:
        text = str(msg)
        if text.startswith("[debug] "):
            self._log.debug(text[len("[debug] "):])
        else:
            self._log.info(text)

    def info(self, msg) -> None:
        self._log.info(str(msg))

    def warning(self, msg) -> None:
        self._log.warning(str(msg))

    def error(self, msg) -> None:
        self._log.error(str(msg))
