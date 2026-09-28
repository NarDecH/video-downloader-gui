#!/usr/bin/env python3
"""ดึงและดาวน์โหลดสื่อจากหน้า HTML / ไฟล์ HTML ในเครื่อง / ลิงก์ไฟล์โดยตรง

ใช้เป็น fallback เมื่อ yt-dlp ดึงไม่สำเร็จ:
  1) ผู้ใช้วางพาธไฟล์ .html ในเครื่อง → parse หา <video>/<source>/og:video/ลิงก์สื่อ → คัดลอกไฟล์สื่อ
  2) ลิงก์ไฟล์สื่อตรง ๆ (mp4/mp3/...) → สตรีมดาวน์โหลดพร้อม progress
  3) ลิงก์หน้าเว็บ HTML → ดึงหน้า, parse หาสื่อ, โหลดไฟล์แรกที่สำเร็จ
"""
from __future__ import annotations

import os
import pathlib
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Callable

MEDIA_EXT = (
    ".mp4", ".webm", ".mkv", ".mov", ".m4v", ".flv", ".ts", ".avi",
    ".mp3", ".m4a", ".ogg", ".wav", ".aac", ".opus",
    ".m3u8", ".mpd",
)
# ไฟล์ที่สตรีมดาวน์โหลดตรงได้ (HLS/DASH ให้ yt-dlp จัดการ)
PROGRESSIVE_EXT = tuple(e for e in MEDIA_EXT if e not in (".m3u8", ".mpd"))

_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}


class DownloadAborted(Exception):
    """Raised when stop_flag is set during a fallback download."""


class _MediaHTMLParser(HTMLParser):
    """เก็บลิงก์สื่อจาก <video>/<source>/<audio>/<embed>/<a>/<meta og:video>"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        a = dict(attrs)
        src = a.get("src") or ""
        if tag in ("video", "audio", "source", "embed") and src:
            self.refs.append(src)
        elif tag == "a":
            href = a.get("href") or ""
            if href.lower().split("?")[0].endswith(MEDIA_EXT):
                self.refs.append(href)
        elif tag == "meta":
            prop = (a.get("property") or a.get("name") or "").lower()
            if prop in ("og:video", "og:video:url", "og:video:secure_url") and a.get("content"):
                self.refs.append(a["content"])


def extract_media_from_html(html: str, base_url: str = "") -> list[str]:
    """คืนลิงก์สื่อ (absolute) ที่พบในเอกสาร HTML โดยไม่ซ้ำ"""
    parser = _MediaHTMLParser()
    parser.feed(html)

    seen: set[str] = set()
    out: list[str] = []

    def add(ref: str) -> None:
        ref = ref.strip()
        if not ref or ref.startswith(("#", "javascript:", "data:")):
            return
        if base_url:
            ref = urllib.parse.urljoin(base_url, ref)
        if ref not in seen:
            seen.add(ref)
            out.append(ref)

    for ref in parser.refs:
        add(ref)

    # Regex fallback สำหรับ attribute ที่ parser อาจพลาด (เช่น tag ที่ JS ฝัง)
    for m in re.finditer(r"""(?:src|href|content)\s*=\s*["']([^"']+)["']""", html, re.I):
        candidate = m.group(1)
        if candidate.lower().split("?")[0].endswith(MEDIA_EXT):
            add(candidate)
    return out


def fetch_page(url: str, timeout: float = 20) -> str:
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        return resp.read().decode("utf-8", "replace")


def _as_local_path(u: str) -> str | None:
    if not u:
        return None
    if u.startswith("file:"):
        return urllib.request.url2pathname(urllib.parse.urlparse(u).path)
    if re.match(r"^[A-Za-z]:[\\/]", u) or u.startswith(("/", "./", "../")):
        return u
    return None


def _emit(progress: Callable | None, pct: float, speed: str) -> None:
    if progress:
        try:
            progress(pct, speed)
        except Exception:
            pass


def _check_stop(stop_flag) -> None:
    if stop_flag is not None and stop_flag.is_set():
        raise DownloadAborted("ยกเลิกโดยผู้ใช้")


def _safe_name(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "video.mp4"


def download_direct(url: str, dest_dir: str, stop_flag=None, progress=None) -> str:
    """สตรีมดาวน์โหลดไฟล์สื่อตรงไปยัง dest_dir พร้อมรายงาน progress (0–100, ความเร็ว)"""
    req = urllib.request.Request(url, headers=_UA)
    started = time.time()
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310
        total = int(resp.headers.get("Content-Length") or 0)
        name = _safe_name(os.path.basename(urllib.parse.urlparse(url).path))
        path = os.path.join(dest_dir, name)
        done = 0
        with open(path, "wb") as fh:
            while True:
                _check_stop(stop_flag)
                chunk = resp.read(256 * 1024)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                rate = done / max(time.time() - started, 1e-6)
                _emit(progress, done / total * 100.0 if total else 0.0, f"{rate / 1048576:.1f} MB/s")
    return path


def _copy_local(src: str, dest_dir: str, stop_flag=None, progress=None) -> str:
    total = os.path.getsize(src)
    path = os.path.join(dest_dir, _safe_name(os.path.basename(src)))
    started = time.time()
    done = 0
    with open(src, "rb") as fin, open(path, "wb") as fout:
        while True:
            _check_stop(stop_flag)
            chunk = fin.read(256 * 1024)
            if not chunk:
                break
            fout.write(chunk)
            done += len(chunk)
            rate = done / max(time.time() - started, 1e-6)
            _emit(progress, done / total * 100.0 if total else 0.0, f"{rate / 1048576:.1f} MB/s")
    return path


def smart_download(url: str, dest_dir: str, stop_flag=None, progress=None) -> list[str]:
    """ดาวน์โหลดแบบเก็งเก็ตจาก URL/พาธที่ผู้ใช้ให้ คืนรายการไฟล์ที่บันทึกได้"""
    saved: list[str] = []

    # กรณี A: ไฟล์ HTML ในเครื่อง (พาธตรง ๆ หรือ file://)
    local = _as_local_path(url)
    if local and os.path.isfile(local) and local.lower().endswith((".html", ".htm")):
        with open(local, "r", encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        base_uri = pathlib.Path(local).resolve().as_uri()
        for ref in extract_media_from_html(html, base_url=base_uri):
            p = _as_local_path(ref)
            try:
                if p and os.path.isfile(p):
                    saved.append(_copy_local(p, dest_dir, stop_flag, progress))
                elif urllib.parse.urlparse(ref).scheme.lower() in ("http", "https") and ref.lower().split("?")[0].endswith(PROGRESSIVE_EXT):
                    saved.append(download_direct(ref, dest_dir, stop_flag, progress))
            except DownloadAborted:
                raise
            except Exception:
                continue
        return saved

    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        return saved

    # กรณี B: ลิงก์ไฟล์สื่อตรง
    if url.lower().split("?")[0].endswith(PROGRESSIVE_EXT):
        saved.append(download_direct(url, dest_dir, stop_flag, progress))
        return saved

    # กรณี C: หน้าเว็บ HTML → แยกสื่อแล้วโหลดไฟล์แรกที่สำเร็จ
    try:
        html = fetch_page(url)
    except Exception:
        return saved
    for ref in extract_media_from_html(html, base_url=url):
        if urllib.parse.urlparse(ref).scheme.lower() not in ("http", "https"):
            continue
        if not ref.lower().split("?")[0].endswith(PROGRESSIVE_EXT):
            continue
        try:
            saved.append(download_direct(ref, dest_dir, stop_flag, progress))
            break  # หนึ่งลิงก์ = หนึ่งวิดีโอ พอสำหรับโหมดสำรอง
        except Exception:
            continue
    return saved
