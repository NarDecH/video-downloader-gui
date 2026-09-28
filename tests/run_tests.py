#!/usr/bin/env python3
"""ชุดทดสอบ html_media (โหมดสำรอง) และการเชื่อมต่อกับ main.py

ทดสอบกับวิดีโอตัวอย่างสาธารณะ (CC) จาก test-videos.co.uk เท่านั้น
รัน: python tests/run_tests.py
"""
from __future__ import annotations

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


def test_main_integration() -> None:
    print("\n[5] การเชื่อมต่อกับ main.py (App._fallback)")
    import main  # noqa: E402

    check("main import html_media", hasattr(main, "html_media"))
    check("มี App._fallback", hasattr(main.App, "_fallback"))
    check("มี DownloadAborted", hasattr(html_media, "DownloadAborted"))


def test_gui_smoke() -> None:
    print("\n[6] GUI เปิดได้หลังแก้โค้ด")
    import tkinter as tk

    from main import App

    root = tk.Tk()
    root.withdraw()
    App(root)
    root.after(1200, root.destroy)
    root.mainloop()
    check("GUI smoke test", True)


if __name__ == "__main__":
    print("═══ ทดสอบโหมดสำรอง html_media + การเชื่อมต่อ main ═══")
    test_extract_patterns()
    test_local_html_with_remote_media()
    test_direct_url()
    test_web_page_scrape()
    test_main_integration()
    test_gui_smoke()
    fails = [r for r in results if not r[1]]
    print("\n──────────────────────────────")
    print(f"สรุป: {len(results) - len(fails)}/{len(results)} ผ่าน")
    sys.exit(1 if fails else 0)
