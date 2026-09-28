#!/usr/bin/env python3
"""ดึงและดาวน์โหลดสื่อจากหน้า HTML / ไฟล์ HTML ในเครื่อง / ลิงก์ไฟล์โดยตรง

ใช้เป็น fallback เมื่อ yt-dlp ดึงไม่สำเร็จ:
  1) ผู้ใช้วางพาธไฟล์ .html ในเครื่อง → parse หาสื่อ (รวม lazy-load/JSON/iframe) → คัดลอก/ดาวน์โหลด
  2) ลิงก์ไฟล์สื่อตรง ๆ (mp4/mp3/...) → สตรีมดาวน์โหลดพร้อม progress
  3) ลิงก์หน้าเว็บ HTML → ดึงหน้า (ตรวจ Content-Type: ถ้าเป็นสื่อ endpoint ไม่มีนามสกุลก็สตรีมเลย)
     แล้วหาสื่อจาก: <video>/<source>/<audio>/<embed>/<a>/og:video/twitter:player:stream,
     attribute แบบ lazy-load (data-src, data-video-src, data-mp4, ...), URL ที่ฝังใน JSON/สคริปต์
     (รวมแบบ escape "\\ /") และ manifest .m3u8/.mpd — manifest กับ iframe player จะส่งต่อให้
     "strong_downloader" (yt-dlp จาก main.py) ถ้าผู้เรียกให้มา
"""
from __future__ import annotations

import logging
import os
import pathlib
import re
import time
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from typing import Callable

log = logging.getLogger("vdl.html_media")
log.addHandler(logging.NullHandler())  # ตั้งค่าจริงโดย logger.setup_logging() ตอนแอปเปิด

MEDIA_EXT = (
    ".mp4", ".webm", ".mkv", ".mov", ".m4v", ".flv", ".ts", ".avi",
    ".mp3", ".m4a", ".ogg", ".wav", ".aac", ".opus", ".ogv", ".3gp",
    ".m3u8", ".mpd",
)
# ไฟล์ที่สตรีมดาวน์โหลดตรงได้ (HLS/DASH ให้ strong_downloader/yt-dlp จัดการ)
PROGRESSIVE_EXT = tuple(e for e in MEDIA_EXT if e not in (".m3u8", ".mpd"))
MANIFEST_EXT = (".m3u8", ".mpd")

# attribute สำหรับ lazy-load ที่เว็บนิยมใช้ (หน้าเว็บจริงมักใส่สื่อไว้ที่นี่ ไม่ใช่ src)
LAZY_ATTRS = ("data-src", "data-video-src", "data-mp4", "data-hls", "data-file", "data-url", "data-video", "data-source")
VIDEO_TAGS = ("video", "audio", "source", "embed")

# Content-Type → นามสกุล (สำหรับ endpoint ที่ URL ไม่มีนามสกุลสื่อ เช่น /getvideo?id=1)
_CT_EXT = {
    "video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov",
    "video/x-matroska": ".mkv", "video/x-flv": ".flv", "video/mpeg": ".mpeg",
    "video/mp2t": ".ts", "video/3gpp": ".3gp", "video/ogg": ".ogv",
    "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/aac": ".aac",
    "audio/ogg": ".ogg", "audio/wav": ".wav", "audio/x-wav": ".wav",
    "audio/opus": ".opus", "application/vnd.apple.mpegurl": ".m3u8",
    "application/dash+xml": ".mpd",
}

_MAX_EMBEDS = 5  # จำนวน iframe player ที่จะลองตามสูงสุดต่อหนึ่งหน้า

_UA = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    )
}

# URL สื่อที่ถูก quote อยู่ใน JSON/สคริปต์ (เช่น player config, JSON-LD contentUrl)
# รองรับ absolute (https://, https:\/\/ แบบ escape, //) และ relative ที่มี "/" นำทาง
_QUOTED_MEDIA_RE = re.compile(
    r"""["']([^"'\s]+?\.(?:mp4|m3u8|mpd|webm|mkv|mov|m4v|ts|flv|mp3|m4a|aac|ogg|opus|ogv|3gp)(?:\?[^\s"']*)?)["']""",
    re.I,
)
# attribute ที่ parser อาจพลาด (แท็กที่ JS ฝัง / attribute แปลก ๆ)
_ATTR_RE = re.compile(
    r"""(?:src|href|content|data-src|data-video-src|data-mp4|data-hls|data-file|data-url|data-video|data-source)\s*=\s*["']([^"']+)["']""",
    re.I,
)
_SKIP_PREFIXES = ("#", "javascript:", "data:", "blob:", "about:", "mailto:")


class DownloadAborted(Exception):
    """Raised when stop_flag is set during a fallback download."""


class _MediaHTMLParser(HTMLParser):
    """เก็บลิงก์สื่อจาก <video>/<source>/<audio>/<embed>/<a>/<meta> และลิงก์ iframe player"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.refs: list[str] = []
        self.embeds: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        a = dict(attrs)
        if tag in VIDEO_TAGS:
            src = a.get("src") or next((a[k] for k in LAZY_ATTRS if a.get(k)), "")
            if src:
                self.refs.append(src)
        elif tag == "a":
            href = a.get("href") or ""
            if href.lower().split("?")[0].endswith(MEDIA_EXT):
                self.refs.append(href)
        elif tag == "iframe":
            src = a.get("src") or a.get("data-src") or ""
            if src:
                self.embeds.append(src)
        elif tag == "meta":
            prop = (a.get("property") or a.get("name") or "").lower()
            if prop in ("og:video", "og:video:url", "og:video:secure_url", "twitter:player:stream") and a.get("content"):
                self.refs.append(a["content"])
            elif prop in ("twitter:player", "og:video:iframe") and a.get("content"):
                self.embeds.append(a["content"])


def _json_unescape(s: str) -> str:
    """คลี่ escape ที่พบบ่อยใน JSON/JS: \\/ → / และ \\u0026 → &"""
    return s.replace("\\/", "/").replace("\\u0026", "&").replace("\\u002F", "&")


def extract_media_from_html(html: str, base_url: str = "") -> list[str]:
    """คืนลิงก์สื่อ (absolute) ที่พบในเอกสาร HTML โดยไม่ซ้ำ"""
    parser = _MediaHTMLParser()
    parser.feed(html)

    seen: set[str] = set()
    out: list[str] = []

    def add(ref: str) -> None:
        ref = _json_unescape(ref.strip())
        if not ref or ref.startswith(_SKIP_PREFIXES):
            return
        if base_url:
            ref = urllib.parse.urljoin(base_url, ref)
        if ref not in seen:
            seen.add(ref)
            out.append(ref)

    for ref in parser.refs:
        add(ref)

    # Regex fallback สำหรับ attribute ที่ parser อาจพลาด (เช่น tag ที่ JS ฝัง)
    for m in _ATTR_RE.finditer(html):
        candidate = m.group(1)
        if candidate.lower().split("?")[0].endswith(MEDIA_EXT):
            add(candidate)

    # สื่อที่ฝังใน JSON/สคริปต์ (player config, JSON-LD, __NEXT_DATA__ ฯลฯ)
    # ชื่อไฟล์เปล่า ๆ ไม่มี "/" เสี่ยง false positive (ชื่อในแกลเลอรี/คอมเมนต์) — ข้าม
    for m in _QUOTED_MEDIA_RE.finditer(html):
        cand = m.group(1)
        if not re.match(r"(?:https?:)?//", cand, re.I) and "/" not in cand:
            continue
        add(cand)
    return out


def extract_embeds_from_html(html: str, base_url: str = "") -> list[str]:
    """คืนลิงก์ iframe player (absolute) ที่พบในหน้า — ผู้เรียกควรลองตามทีละลิงก์"""
    parser = _MediaHTMLParser()
    parser.feed(html)
    seen: set[str] = set()
    out: list[str] = []
    for ref in parser.embeds:
        ref = _json_unescape(ref.strip())
        if not ref or ref.startswith(_SKIP_PREFIXES):
            continue
        if base_url:
            ref = urllib.parse.urljoin(base_url, ref)
        if ref != base_url and ref not in seen:
            seen.add(ref)
            out.append(ref)
    return out


def _open(url: str, referer: str | None = None, timeout: float = 30):
    """เปิด URL แบบมี User-Agent จริง และส่ง Referer ของหน้าต้นทาง (CDN หลายเจ้าตรวจ hotlink)"""
    headers = dict(_UA)
    if referer:
        headers["Referer"] = referer
    log.debug("GET %s (referer=%s)", url, referer or "-")
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout)  # noqa: S310


def _decode_body(resp) -> str:
    """อ่าน body แล้ว decode ตาม charset จาก header / <meta charset> (รองรับเว็บไทย windows-874 ฯลฯ)"""
    data = resp.read()
    m = re.search(r"charset=([\w-]+)", resp.headers.get("Content-Type") or "", re.I)
    charset = m.group(1) if m else None
    if not charset:
        head = data[:8192].decode("ascii", "replace")
        m = re.search(r"""<meta[^>]+charset=["']?([\w-]+)""", head, re.I)
        charset = m.group(1) if m else "utf-8"
    try:
        return data.decode(charset, "replace")
    except LookupError:
        return data.decode("utf-8", "replace")


def fetch_page(url: str, timeout: float = 20, referer: str | None = None) -> str:
    with _open(url, referer=referer, timeout=timeout) as resp:
        ct = (resp.headers.get("Content-Type") or "").lower().split(";")[0].strip()
        body = _decode_body(resp)
    if ct.startswith(("video/", "audio/")):
        raise ValueError(f"URL เป็นไฟล์สื่อ ({ct}) ไม่ใช่หน้า HTML")
    return body


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


def _filename_for(url: str, content_type: str = "") -> str:
    """ชื่อไฟล์จาก URL ถ้าไม่มีนามสกุลสื่อ (เช่น endpoint .php) ใช้นามสกุลจาก Content-Type แทน"""
    name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path))
    stem, ext = os.path.splitext(name)
    ct = content_type.split(";")[0].strip().lower()
    if not ext or ext.lower() not in MEDIA_EXT:
        mapped = _CT_EXT.get(ct)
        if mapped:
            name = (stem or "video") + mapped
    if not name or name.startswith("."):
        name = "video.mp4"
    return _safe_name(name)


def _stream(resp, url: str, dest_dir: str, stop_flag=None, progress=None) -> str:
    """สตรีมจาก response ที่เปิดแล้วลงไฟล์ พร้อมรายงาน progress (0–100, ความเร็ว)"""
    total = int(resp.headers.get("Content-Length") or 0)
    path = os.path.join(dest_dir, _filename_for(url, resp.headers.get("Content-Type") or ""))
    started = time.time()
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
    log.info("saved: %s (%d bytes)", path, done)
    return path


def download_direct(url: str, dest_dir: str, stop_flag=None, progress=None, referer: str | None = None) -> str:
    """สตรีมดาวน์โหลดไฟล์สื่อตรงไปยัง dest_dir พร้อมรายงาน progress (0–100, ความเร็ว)"""
    with _open(url, referer=referer) as resp:
        return _stream(resp, url, dest_dir, stop_flag, progress)


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


def _from_html(
    html: str,
    base_url: str,
    dest_dir: str,
    stop_flag=None,
    progress=None,
    strong_downloader: Callable | None = None,
    try_local: bool = False,
    referer: str | None = None,
    depth: int = 0,
) -> list[str]:
    """หาสื่อจากเอกสาร HTML แล้วดาวน์โหลด — ลำดับ: ไฟล์ตรง → manifest → iframe player"""
    media = extract_media_from_html(html, base_url=base_url)
    progressive = [r for r in media if r.lower().split("?")[0].endswith(PROGRESSIVE_EXT)]
    manifests = [r for r in media if r.lower().split("?")[0].endswith(MANIFEST_EXT)]
    log.debug(
        "parse %s: %d media (%d progressive, %d manifest, %d embeds)",
        base_url, len(media), len(progressive), len(manifests), len(extract_embeds_from_html(html, base_url=base_url)),
    )
    saved: list[str] = []
    first_only = not try_local

    for ref in progressive:
        _check_stop(stop_flag)
        try:
            if try_local:
                p = _as_local_path(ref)
                if p and os.path.isfile(p):
                    log.info("direct (local copy): %s", ref)
                    saved.append(_copy_local(p, dest_dir, stop_flag, progress))
                elif urllib.parse.urlparse(ref).scheme.lower() in ("http", "https"):
                    log.info("direct download: %s", ref)
                    saved.append(download_direct(ref, dest_dir, stop_flag, progress, referer=referer))
            elif urllib.parse.urlparse(ref).scheme.lower() in ("http", "https"):
                log.info("direct download: %s", ref)
                saved.append(download_direct(ref, dest_dir, stop_flag, progress, referer=referer))
        except DownloadAborted:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("direct download failed: %s (%s)", ref, exc)
            continue
        if saved and first_only:
            return saved

    for ref in manifests:
        _check_stop(stop_flag)
        if strong_downloader is None:
            log.info("manifest found but no strong_downloader: %s", ref)
            continue
        try:
            log.info("manifest -> strong_downloader: %s (referer=%s)", ref, referer or "-")
            got = strong_downloader(ref, dest_dir, stop_flag, progress, referer=referer)
        except DownloadAborted:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("strong_downloader failed for manifest %s (%s)", ref, exc)
            continue
        if got:
            saved.extend(got)
            return saved

    # iframe player (เช่น หน้า WordPress ที่ฝัง player ภายนอก) — ตามได้ลึก 1 ระดับ
    if depth == 0:
        for emb in extract_embeds_from_html(html, base_url=base_url)[:_MAX_EMBEDS]:
            _check_stop(stop_flag)
            log.info("embed iframe -> follow: %s", emb)
            scheme = urllib.parse.urlparse(emb).scheme.lower()
            emb_path = emb.lower().split("?")[0]
            try:
                if emb_path.endswith(PROGRESSIVE_EXT):
                    if scheme in ("http", "https"):
                        saved.append(download_direct(emb, dest_dir, stop_flag, progress, referer=base_url))
                        return saved
                elif scheme == "file" and try_local:
                    p = _as_local_path(emb)
                    if p and os.path.isfile(p) and p.lower().endswith((".html", ".htm")):
                        with open(p, "r", encoding="utf-8", errors="replace") as fh:
                            sub_html = fh.read()
                        sub_base = pathlib.Path(p).resolve().as_uri()
                        got = _from_html(sub_html, sub_base, dest_dir, stop_flag, progress,
                                         strong_downloader, try_local=True, referer=sub_base, depth=1)
                        if got:
                            saved.extend(got)
                            return saved
                elif scheme in ("http", "https"):
                    try:
                        sub_html = fetch_page(emb, referer=base_url)
                    except ValueError:
                        log.info("embed returns media content, not HTML: %s", emb)
                        sub_html = None  # คืนเนื้อหาสื่อ ไม่ใช่หน้า HTML — ให้ strong_downloader จัดการต่อ
                    if sub_html is not None:
                        got = _from_html(sub_html, emb, dest_dir, stop_flag, progress,
                                         strong_downloader, try_local=False, referer=emb, depth=1)
                        if got:
                            saved.extend(got)
                            return saved
                    if strong_downloader is not None:
                        log.info("embed page yielded nothing -> strong_downloader: %s (referer=%s)", emb, base_url or "-")
                        got = strong_downloader(emb, dest_dir, stop_flag, progress, referer=base_url)
                        if got:
                            saved.extend(got)
                            return saved
                elif strong_downloader is not None and scheme == "file":
                    got = strong_downloader(emb, dest_dir, stop_flag, progress)
                    if got:
                        saved.extend(got)
                        return saved
            except DownloadAborted:
                raise
            except Exception:
                continue
    return saved


def smart_download(
    url: str,
    dest_dir: str,
    stop_flag=None,
    progress=None,
    strong_downloader: Callable | None = None,
) -> list[str]:
    """ดาวน์โหลดแบบเก็งเกตจาก URL/พาธที่ผู้ใช้ให้ คืนรายการไฟล์ที่บันทึกได้

    strong_downloader(url, dest_dir, stop_flag, progress, referer=None) -> list[str]
        (optional) ตัวดาวน์โหลดตัวที่สอง เช่น yt-dlp — ใช้กับ manifest .m3u8/.mpd
        และลิงก์ iframe player ที่แยกสื่อธรรมดาเอาไม่ได้; referer คือหน้าต้นทาง
        ที่เจอ URL นั้น (CDN บางเจ้าตรวจ hotlink)
    """
    # กรณี A: ไฟล์ HTML ในเครื่อง (พาธตรง ๆ หรือ file://)
    local = _as_local_path(url)
    if local and os.path.isfile(local) and local.lower().endswith((".html", ".htm")):
        log.info("case A: local html file %s", local)
        with open(local, "r", encoding="utf-8", errors="replace") as fh:
            html = fh.read()
        base_uri = pathlib.Path(local).resolve().as_uri()
        return _from_html(html, base_uri, dest_dir, stop_flag, progress,
                          strong_downloader, try_local=True, referer=base_uri)

    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        log.info("unsupported scheme %r: %s", scheme, url)
        return []

    # กรณี B: ลิงก์ไฟล์สื่อตรง
    if url.lower().split("?")[0].endswith(PROGRESSIVE_EXT):
        log.info("case B: direct media link %s", url)
        return [download_direct(url, dest_dir, stop_flag, progress)]

    # กรณี B1: ลิงก์ manifest HLS/DASH ตรง ๆ → ต้องใช้ strong_downloader (yt-dlp)
    if strong_downloader is not None and url.lower().split("?")[0].endswith(MANIFEST_EXT):
        log.info("case B1: manifest link -> strong_downloader %s", url)
        try:
            return list(strong_downloader(url, dest_dir, stop_flag, progress) or [])
        except DownloadAborted:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("strong_downloader failed for %s (%s)", url, exc)
            return []

    # กรณี B2: ลิงก์ endpoint ไม่มีนามสกุลสื่อ → ดึงมาแล้วดูจาก Content-Type
    # กรณี C: หน้าเว็บ HTML → แยกสื่อแล้วดาวน์โหลด
    log.info("case B2/C: fetch page %s", url)
    try:
        with _open(url) as resp:
            ct = (resp.headers.get("Content-Type") or "").lower().split(";")[0].strip()
            log.info("content-type=%s for %s", ct or "-", url)
            if strong_downloader is not None and ct in (
                "application/vnd.apple.mpegurl", "application/x-mpegurl", "application/dash+xml",
            ):
                log.info("manifest content-type -> strong_downloader %s", url)
                return list(strong_downloader(url, dest_dir, stop_flag, progress) or [])
            if ct.startswith(("video/", "audio/", "application/octet-stream")):
                log.info("media content-type -> streaming %s", url)
                return [_stream(resp, url, dest_dir, stop_flag, progress)]
            html = _decode_body(resp)
    except DownloadAborted:
        raise
    except Exception as exc:  # noqa: BLE001
        log.warning("page fetch failed: %s (%s)", url, exc)
        return []  # ดึงหน้าไม่ได้ (404/timeout/TLS ฯลฯ) — ไม่ raise ให้ผู้เรียกตัดสินเอง
    return _from_html(html, url, dest_dir, stop_flag, progress,
                      strong_downloader, try_local=False, referer=url)
