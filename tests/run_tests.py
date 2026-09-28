#!/usr/bin/env python3
"""ชุดทดสอบ html_media (โหมดสำรอง) และการเชื่อมต่อกับ main.py

ทดสอบกับวิดีโอตัวอย่างสาธารณะ (CC) จาก test-videos.co.uk เท่านั้น
รัน: python tests/run_tests.py
"""
from __future__ import annotations

import logging
import os
import shutil
import sys
import tempfile

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import html_media  # noqa: E402

BBB_360 = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/360/Big_Buck_Bunny_360_10s_1MB.mp4"
BBB_720 = "https://test-videos.co.uk/vids/bigbuckbunny/mp4/h264/720/Big_Buck_Bunny_720_10s_1MB.mp4"
SINTEL_360 = "https://test-videos.co.uk/vids/sintel/mp4/h264/360/Sintel_360_10s_1MB.mp4"
POSTER_PNG = "https://test-videos.co.uk/vids/bigbuckbunny/poster/big_buck_bunny_360_10s_1MB.png"

TEST_PAGE = os.path.join(HERE, "test.html")
EMBED_PAGE = os.path.join(HERE, "test_embed.html")

results: list[tuple[str, bool, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, bool(cond), detail))
    print(("  ✅ PASS  " if cond else "  ❌ FAIL  ") + name + (f"  — {detail}" if detail and not cond else ""))


def tmpdir() -> str:
    d = tempfile.mkdtemp(prefix="vdl_test_")
    return d


def test_extract_patterns() -> None:
    print("\n[1] แยกลิงก์สื่อจาก HTML ครบทั้ง 4 รูปแบบ")
    with open(TEST_PAGE, "r", encoding="utf-8") as fh:
        html = fh.read()
    refs = html_media.extract_media_from_html(html, base_url="https://test-videos.co.uk/some/page/")
    check("พบลิงก์สื่อไม่ซ้ำกัน 3 รายการ (dedupe ถูกต้อง)", len(refs) == 3, f"พบ {len(refs)}: {refs}")
    check("รูปแบบ 1: <video><source>", any(BBB_360 in r for r in refs))
    check("รูปแบบ 2: <video src>", any(SINTEL_360 in r for r in refs))
    check("รูปแบบ 3: <a href> .mp4", any(BBB_720 in r for r in refs))
    check("รูปแบบ 4: og:video meta", any(SINTEL_360 in r for r in refs))
    check("ไม่ดึงรูปภาพ .png", not any(POSTER_PNG in r for r in refs))


def test_local_html_with_remote_media() -> None:
    print("\n[2] โหลดวีดีโอจากไฟล์ HTML ในเครื่อง (สื่ออยู่ระยะไกล)")
    d = tmpdir()
    saved = html_media.smart_download(TEST_PAGE, d)
    sizes = [os.path.getsize(p) for p in saved]
    check("ดาวน์โหลดสำเร็จ >= 3 ไฟล์", len(saved) >= 3, f"ได้ {len(saved)} ไฟล์: {saved}")
    check("ไฟล์มีขนาด > 500 KB จริง", bool(sizes) and min(sizes) > 500_000, str(sizes))
    shutil.rmtree(d, ignore_errors=True)


def test_direct_url() -> None:
    print("\n[3] ดาวน์โหลดลิงก์ไฟล์ตรง + progress callback")
    d = tmpdir()
    seen = []
    saved = html_media.smart_download(BBB_360, d, progress=lambda p, s: seen.append(p))
    check("ได้ไฟล์ 1 ไฟล์", len(saved) == 1, str(saved))
    check("ขนาด ~1 MB", bool(saved) and os.path.getsize(saved[0]) > 900_000)
    check("มี callback progress", len(seen) > 0 and max(seen) > 90, f"{len(seen)} callbacks, max={max(seen) if seen else 0:.0f}%")
    shutil.rmtree(d, ignore_errors=True)


def test_web_page_scrape() -> None:
    print("\n[4] ดึงสื่อจากหน้าเว็บ (URL) แบบไม่ระบุไฟล์")
    d = tmpdir()
    saved = html_media.smart_download(TEST_PAGE.replace(os.sep, "/"), d) if False else []
    # ใช้หน้าจริงบนโดเมนทดสอบ (serve ไฟล์เดียวกันผ่าน http)
    saved = html_media.smart_download("https://test-videos.co.uk/bigbuckbunny/mp4-h264/720", d)
    # หน้านี้อาจไม่มี <video> โดยตรง — ยอมรับทั้งสำเร็จหรือไม่พบสื่อ แต่ต้องไม่ raise
    check("ไม่ raise และคืน list", isinstance(saved, list), str(saved))
    shutil.rmtree(d, ignore_errors=True)


def test_extract_modern_patterns() -> None:
    print("\n[1b] แยกสื่อจากรูปแบบเว็บยุคใหม่ (lazy-load / JSON / HLS / embed)")
    with open(EMBED_PAGE, "r", encoding="utf-8") as fh:
        html = fh.read()
    base = "https://site.example/page/1/"
    refs = html_media.extract_media_from_html(html, base_url=base)
    check("lazy-load: data-src บน div", any(r == "https://cdn.example.com/lazy/div.mp4" for r in refs), str(refs))
    check("lazy-load: data-video-src บน <source>", any(r == "https://cdn.example.com/lazy/source.mp4" for r in refs))
    check("meta: og:video:secure_url", any(r == "https://cdn.example.com/meta/secure.mp4" for r in refs))
    check("meta: twitter:player:stream", any(r == "https://cdn.example.com/meta/twitter.mp4" for r in refs))
    check("JSON escape: \\/ → / และ \\u0026 → &",
          any(r == "https://cdn.example.com/json/escaped.mp4?tok=1&sig=2" for r in refs),
          str([r for r in refs if "json" in r]))
    check("สคริปต์: ลิงก์ .m3u8 (HLS)", any(r == "https://cdn.example.com/hls/index.m3u8" for r in refs))
    check("JSON-LD: contentUrl .webm", any(r == "https://cdn.example.com/jsonld/video.webm" for r in refs))
    check("ข้าม blob: URL (MediaSource)", not any(r.startswith("blob:") for r in refs))
    check("ไม่ดึงรูป poster.jpg", not any(r.endswith(".jpg") for r in refs))

    embeds = html_media.extract_embeds_from_html(html, base_url=base)
    check("iframe: player ภายนอก (dedupe src/data-src เหลือ 1)",
          embeds.count("https://player.example.com/e/abc123/player.html") == 1, str(embeds))
    check("iframe: เก็บทุกตัวรวม non-player ให้ผู้เรียกค่อยกรอง", len(embeds) == 2, str(embeds))


def test_local_embeds_and_manifest() -> None:
    print("\n[2b] ไฟล์ HTML ในเครื่อง: iframe player ในเครื่อง + manifest ส่งต่อ strong_downloader")
    d = tmpdir()
    out = tmpdir()
    os.makedirs(os.path.join(d, "media"), exist_ok=True)
    os.makedirs(os.path.join(d, "player"), exist_ok=True)
    clip = os.path.join(d, "media", "clip.mp4")
    with open(clip, "wb") as fh:
        fh.write(os.urandom(150_000))
    page = os.path.join(d, "page.html")
    with open(page, "w", encoding="utf-8") as fh:
        fh.write('<html><body><video src="media/clip.mp4"></video>'
                 '<iframe src="player/player.html"></iframe></body></html>')
    sub = os.path.join(d, "player", "player.html")
    with open(sub, "w", encoding="utf-8") as fh:
        fh.write("<html><body><script>var s='chunks/index.m3u8';</script></body></html>")

    strong_calls: list[str] = []
    strong_referers: list[str | None] = []
    strong_out = os.path.join(out, "strong.mp4")
    with open(strong_out, "wb") as fh:
        fh.write(os.urandom(64_000))

    def fake_strong(url: str, dest_dir: str, stop_flag=None, progress=None, referer: str | None = None) -> list[str]:
        strong_calls.append(url)
        strong_referers.append(referer)
        return [strong_out]

    saved = html_media.smart_download(page, out, strong_downloader=fake_strong)
    names = [os.path.basename(p) for p in saved]
    check("คัดลอกสื่อในเครื่อง (media/clip.mp4)", "clip.mp4" in names, str(saved))
    check("ตาม iframe ไปหน้า player แล้วส่ง manifest ให้ strong_downloader",
          len(strong_calls) == 1 and strong_calls[0].endswith("chunks/index.m3u8"), str(strong_calls))
    check("แนบ referer (หน้า player ที่เจอ manifest) ให้ strong_downloader",
          bool(strong_referers[0]) and strong_referers[0].endswith("player/player.html"), str(strong_referers))
    check("ไฟล์จาก strong_downloader ถูกรวมในผลลัพธ์", "strong.mp4" in names, str(saved))

    saved_m = html_media.smart_download("https://cdn.example.com/live/index.m3u8", out, strong_downloader=fake_strong)
    check("วางลิงก์ .m3u8 ตรง ๆ → ส่งต่อ strong_downloader ทันที",
          saved_m == [strong_out] and "https://cdn.example.com/live/index.m3u8" in strong_calls, str(saved_m))
    shutil.rmtree(d, ignore_errors=True)
    shutil.rmtree(out, ignore_errors=True)


def test_content_type_probe_and_referer() -> None:
    print("\n[3b] endpoint ไม่มีนามสกุล (ดูจาก Content-Type) + Referer ของหน้าต้นทาง")
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    video = os.urandom(64_000)
    seen = {"referer": ""}
    page_html = ""

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            path = self.path.split("?")[0]
            if path == "/clip.mp4":
                seen["referer"] = self.headers.get("Referer") or ""
                body, ct = video, "video/mp4"
            elif path == "/getvideo":
                body, ct = video, "video/mp4"
            else:
                body, ct = page_html.encode("utf-8"), "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args) -> None:
            pass

    srv = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"
    try:
        page_html = f'<html><body><video src="{base}/clip.mp4"></video></body></html>'
        d = tmpdir()
        saved = html_media.smart_download(f"{base}/getvideo?id=42", d)
        check("endpoint /getvideo?id=42 โหลดได้แม้ไม่มีนามสกุล",
              len(saved) == 1 and os.path.getsize(saved[0]) == len(video), str(saved))
        check("ตั้งนามสกุล .mp4 จาก Content-Type", bool(saved) and saved[0].endswith("getvideo.mp4"), str(saved))
        saved2 = html_media.smart_download(f"{base}/page.html", d)
        check("โหลดสื่อจากหน้าเว็บได้", len(saved2) == 1 and os.path.getsize(saved2[0]) == len(video), str(saved2))
        check("ส่ง Referer = URL หน้าต้นทาง (กัน CDN ตรวจ hotlink)", seen["referer"] == f"{base}/page.html",
              seen["referer"])
        shutil.rmtree(d, ignore_errors=True)
    finally:
        srv.shutdown()


def test_url_extraction_from_text() -> None:
    print("\n[4b] แตก URL ออกจากข้อความที่วาง (main.App._extract_url)")
    import main  # noqa: E402

    check("ข้อความไทยครอบ URL",
          main.App._extract_url("คลิปนี้เลยครับ https://x.com/user/status/1?v=2. สวยดี") == "https://x.com/user/status/1?v=2",
          main.App._extract_url("คลิปนี้เลยครับ https://x.com/user/status/1?v=2. สวยดี"))
    check("www. → เติม https://",
          main.App._extract_url("ดูที่ www.example.com/v.mp4 เลย") == "https://www.example.com/v.mp4")
    check("URL เปล่า ๆ ไม่ถูกแตะ", main.App._extract_url("https://a.b/c.mp4") == "https://a.b/c.mp4")
    check("พาธไฟล์ในเครื่องคงเดิม", main.App._extract_url(r"C:\Users\me\Desktop\page.html") == r"C:\Users\me\Desktop\page.html")
    check("วงเล็บปิดท้ายถูกตัด", main.App._extract_url("(ดู: https://a.b/c.mp4)") == "https://a.b/c.mp4")


def test_main_integration() -> None:
    print("\n[5] การเชื่อมต่อกับ main.py (App._fallback)")
    import main  # noqa: E402

    check("main import html_media", hasattr(main, "html_media"))
    check("มี App._fallback", hasattr(main.App, "_fallback"))
    check("มี App._ydl_download (strong downloader)", hasattr(main.App, "_ydl_download"))
    check("มี DownloadAborted", hasattr(html_media, "DownloadAborted"))
    check("มีเบราว์เซอร์ในแอป: App._open_browser", hasattr(main.App, "_open_browser"))
    check("มีปุ่มจับวีดีโอ: App._grab_current", hasattr(main.App, "_grab_current"))
    check("มี App.rank_browser_media", hasattr(main.App, "rank_browser_media"))
    check("มี App._sync_browser_url", hasattr(main.App, "_sync_browser_url"))
    check("มี App._open_log_folder", hasattr(main.App, "_open_log_folder"))
    check("main import logger (setup_logging/YtDlpLogger)",
          hasattr(main, "setup_logging") and hasattr(main, "YtDlpLogger"))


def test_logger() -> None:
    print("\n[6b] ระบบ log (logger.py — ไฟล์หมุนเวียน + YtDlpLogger)")
    import logger as vdl_logger

    path = vdl_logger.setup_logging()
    check("setup_logging คืนพาธและสร้างไฟล์", os.path.isfile(path), path)
    marker = f"ทดสอบเขียน log ไทย ✅ {os.getpid()}"
    logging.getLogger("vdl.test").info(marker)
    logging.getLogger("vdl.test").warning(f"warn marker {os.getpid()}")
    with open(path, "r", encoding="utf-8") as fh:
        content = fh.read()
    check("ข้อความภาษาไทยลงไฟล์แบบ UTF-8", marker in content, path)
    check("ระดับ WARNING ลงไฟล์", f"warn marker {os.getpid()}" in content)

    ydl = vdl_logger.YtDlpLogger()
    ydl.debug("[debug] quiet internals")
    ydl.debug("[download] Destination: example.mp4")
    ydl.warning("player fallback")
    ydl.error("boom error")
    with open(path, "r", encoding="utf-8") as fh:
        content2 = fh.read()
    check("YtDlpLogger ส่งข้อความของ yt-dlp เข้าไฟล์",
          "[download] Destination: example.mp4" in content2 and "boom error" in content2, path)

    n_before = len(logging.getLogger("vdl").handlers)
    vdl_logger.setup_logging()
    check("เรียก setup_logging ซ้ำไม่เติม handler (idempotent)",
          len(logging.getLogger("vdl").handlers) == n_before)


def test_browser_grab_ranking() -> None:
    print("\n[6c] เบราว์เซอร์ในแอป: จัดลำดับ candidate (App.rank_browser_media)")
    import main  # noqa: E402

    check("JS scan ใช้ performance entries + currentSrc",
          "performance.getEntriesByType" in main.JS_SCAN_MEDIA and "currentSrc" in main.JS_SCAN_MEDIA)
    scan = {
        "title": "ตัวอย่าง", "url": "https://site.example/watch/1",
        "videos": ["blob:https://site.example/uuid-1", "https://cdn.example/vid/playing.mp4"],
        "sources": ["https://cdn.example/vid/playing.mp4"],
        "resources": [
            "https://cdn.example/vid/main.m3u8",
            "https://cdn.example/vid/seg-1.ts",
            "https://cdn.example/vid/alt.mp4?tok=1",
            "https://cdn.example/api/data.json",
        ],
        "iframes": ["https://player.example/e/abc/player.html"],
    }
    ranked = main.App.rank_browser_media(scan)
    check("อันดับ 1 = วีดีโอที่กำลังเล่น (DOM currentSrc)",
          bool(ranked) and ranked[0] == "https://cdn.example/vid/playing.mp4", str(ranked))
    check("manifest .m3u8 มาก่อนไฟล์ตรงอื่น",
          "https://cdn.example/vid/main.m3u8" in ranked
          and ranked.index("https://cdn.example/vid/main.m3u8") < ranked.index("https://cdn.example/vid/alt.mp4?tok=1"),
          str(ranked))
    check("ตัด .ts segment ทิ้ง", not any(u.endswith(".ts") for u in ranked), str(ranked))
    check("ข้าม blob: (MediaSource)", not any(u.startswith("blob:") for u in ranked), str(ranked))
    check("ไม่จับ request ไม่มีนามสกุลสื่อ (API/XHR)", not any(u.endswith("data.json") for u in ranked), str(ranked))
    check("iframe player เป็นตัวสำรองท้ายสุด",
          ranked and ranked[-1] == "https://player.example/e/abc/player.html", str(ranked))
    check("ลิงก์ซ้ำถูก dedupe", len(ranked) == len(set(ranked)), str(ranked))
    check("จำนวนไม่เกิน 8", len(ranked) <= 8, str(len(ranked)))


def test_gui_smoke() -> None:
    print("\n[6] GUI เปิดได้หลังแก้โค้ด")
    if not os.environ.get("DISPLAY") and sys.platform == "linux":
        print("  ⏭ SKIP (no display on CI)")
        return
    import tkinter as tk

    from main import App

    root = tk.Tk()
    root.withdraw()
    app = App(root)
    root.after(1200, root.destroy)
    root.mainloop()
    check("GUI smoke test", True)


if __name__ == "__main__":
    print("═══ ทดสอบโหมดสำรอง html_media + การเชื่อมต่อ main ═══")
    test_extract_patterns()
    test_extract_modern_patterns()
    test_local_html_with_remote_media()
    test_local_embeds_and_manifest()
    test_direct_url()
    test_content_type_probe_and_referer()
    test_url_extraction_from_text()
    test_web_page_scrape()
    test_logger()
    test_browser_grab_ranking()
    test_main_integration()
    test_gui_smoke()
    fails = [r for r in results if not r[1]]
    print("\n──────────────────────────────")
    print(f"สรุป: {len(results) - len(fails)}/{len(results)} ผ่าน")
    sys.exit(1 if fails else 0)
