#!/usr/bin/env python3
"""Video Downloader GUI - ดาวน์โหลดวีดีโอจากเว็บไซต์สาธารณะด้วย yt-dlp

รองรับ: YouTube, TikTok, Facebook, X/Twitter, Instagram (สาธารณะ), Vimeo
และอีกหลายพันเว็บไซต์ ดูรายชื่อได้ที่ https://github.com/yt-dlp/yt-dlp

โปรดใช้เฉพาะกับคอนเทนต์ที่มีสิทธิ์ดาวน์โหลดตามกฎหมายและเงื่อนไขของแต่ละเว็บไซต์
"""

from __future__ import annotations

import json
import os
import queue
import re
import shutil
import sys
import threading
import urllib.request
import webbrowser
import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog, messagebox, ttk
from typing import Any

try:
    import yt_dlp
except ImportError:
    tk.Tk().withdraw()
    messagebox.showerror("Video Downloader", "ไม่พบไลบรารี yt-dlp — ติดตั้งด้วยคำสั่ง: pip install yt-dlp")
    sys.exit(1)

import html_media

APP_TITLE = "Video Downloader GUI"
APP_VERSION = "1.2.0"
GITHUB_REPO = "NarDecH/video-downloader-gui"

# ---------- ตัวเลือกคุณภาพ/ความเร็ว (key เป็น id เพื่อรองรับหลายภาษา) ----------
FORMAT_MAP: dict[str, str] = {
    "best": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "1080": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
    "720": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
    "480": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best",
    "mp3": "bestaudio/best",
}
_FORMAT_ID_BY_LEGACY_TH = {
    "คุณภาพดีที่สุด (mp4)": "best",
    "1080p หรือต่ำกว่า": "1080",
    "720p หรือต่ำกว่า": "720",
    "480p หรือต่ำกว่า": "480",
    "เสียงอย่างเดียว (mp3)": "mp3",
}

SPEED_MAP: dict[str, str | None] = {
    "unlimited": None,
    "1m": "1M",
    "5m": "5M",
    "10m": "10M",
}
_SPEED_ID_BY_LEGACY_TH = {"ไม่จำกัด": "unlimited", "1 MB/s": "1m", "5 MB/s": "5m", "10 MB/s": "10m"}

COOKIES_BROWSERS = ["", "chrome", "firefox", "edge", "brave", "chromium", "vivaldi", "opera", "safari"]

# ---------- i18n ----------
LANG: dict[str, dict[str, str]] = {
    "th": {
        "url_frame": "ลิงก์วีดีโอ (หนึ่งลิงก์ต่อบรรทัด)",
        "quality": "คุณภาพ:",
        "speed": "จำกัดความเร็ว:",
        "cookies": "คุกกี้เบราว์เซอร์:",
        "playlist": "โหลดทั้งเพลย์ลิสต์",
        "dest": "โฟลเดอร์ปลายทาง:",
        "browse": "เลือก…",
        "start": "▶ เริ่มดาวน์โหลด",
        "cancel": "■ ยกเลิกทั้งหมด",
        "open": "📂 เปิดโฟลเดอร์",
        "col_title": "รายการ",
        "col_progress": "ความคืบหน้า",
        "col_status": "สถานะ",
        "col_speed": "ความเร็ว/เวลาที่เหลือ",
        "ready": "พร้อมทำงาน",
        "downloading": "กำลังดาวน์โหลด…",
        "merging": "กำลังรวมไฟล์วีดีโอ+เสียง…",
        "done_all": "เสร็จสิ้นทุกรายการ",
        "canceling": "กำลังยกเลิก…",
        "err_no_url": "กรุณาวางลิงก์วีดีโออย่างน้อยหนึ่งลิงก์",
        "err_bad_dir": "โฟลเดอร์ปลายทางไม่มีอยู่ — กรุณาเลือกใหม่",
        "warn_ffmpeg": "⚠ ไม่พบ ffmpeg — การรวมไฟล์วีดีโอ/เสียงคุณภาพสูงและการแปลง mp3 อาจใช้ไม่ได้",
        "menu_lang": "ภาษา/Language",
        "menu_help": "ช่วยเหลือ",
        "menu_check_update": "ตรวจสอบเวอร์ชันใหม่…",
        "menu_about": "เกี่ยวกับ",
        "update_banner": "🔔 มีเวอร์ชันใหม่ {v} — คลิกที่นี่เพื่อดาวน์โหลด",
        "uptodate": "คุณใช้เวอร์ชันล่าสุดแล้ว (v{v})",
        "about": "{app} v{v}\nดาวน์โหลดวีดีโอจากเว็บไซต์สาธารณะ\n\nเอนจิน: yt-dlp • License: MIT\nRepo: https://github.com/{repo}",
        "fmt_best": "คุณภาพดีที่สุด (mp4)",
        "fmt_1080": "1080p หรือต่ำกว่า",
        "fmt_720": "720p หรือต่ำกว่า",
        "fmt_480": "480p หรือต่ำกว่า",
        "fmt_mp3": "เสียงอย่างเดียว (mp3)",
        "sp_unlimited": "ไม่จำกัด",
        "sp_1m": "1 MB/s",
        "sp_5m": "5 MB/s",
        "sp_10m": "10 MB/s",
        "ck_none": "ไม่ใช้",
    },
    "en": {
        "url_frame": "Video URLs (one per line)",
        "quality": "Quality:",
        "speed": "Speed limit:",
        "cookies": "Browser cookies:",
        "playlist": "Download whole playlist",
        "dest": "Destination folder:",
        "browse": "Browse…",
        "start": "▶ Start download",
        "cancel": "■ Cancel all",
        "open": "📂 Open folder",
        "col_title": "Item",
        "col_progress": "Progress",
        "col_status": "Status",
        "col_speed": "Speed / ETA",
        "ready": "Ready",
        "downloading": "Downloading…",
        "merging": "Merging video+audio…",
        "done_all": "All done",
        "canceling": "Cancelling…",
        "err_no_url": "Please paste at least one video URL",
        "err_bad_dir": "Destination folder does not exist — choose again",
        "warn_ffmpeg": "⚠ ffmpeg not found — merging high-quality streams and mp3 conversion may not work",
        "menu_lang": "ภาษา/Language",
        "menu_help": "Help",
        "menu_check_update": "Check for updates…",
        "menu_about": "About",
        "update_banner": "🔔 New version {v} available — click here to download",
        "uptodate": "You are on the latest version (v{v})",
        "about": "{app} v{v}\nDownload videos from public websites\n\nEngine: yt-dlp • License: MIT\nRepo: https://github.com/{repo}",
        "fmt_best": "Best quality (mp4)",
        "fmt_1080": "1080p or lower",
        "fmt_720": "720p or lower",
        "fmt_480": "480p or lower",
        "fmt_mp3": "Audio only (mp3)",
        "sp_unlimited": "Unlimited",
        "sp_1m": "1 MB/s",
        "sp_5m": "5 MB/s",
        "sp_10m": "10 MB/s",
        "ck_none": "None",
    },
}

# ---------- ค่าตั้งต่อผู้ใช้ ----------
CONFIG_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~/.config"), "video-downloader")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")


def load_config() -> dict:
    cfg: dict = {}
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
            cfg = json.load(fh)
    except (OSError, json.JSONDecodeError):
        cfg = {}
    # แปลงค่าเก่า (ป้ายภาษาไทย) เป็น id
    if cfg.get("format") in _FORMAT_ID_BY_LEGACY_TH:
        cfg["format"] = _FORMAT_ID_BY_LEGACY_TH[cfg["format"]]
    if cfg.get("limit") in _SPEED_ID_BY_LEGACY_TH:
        cfg["limit"] = _SPEED_ID_BY_LEGACY_TH[cfg["limit"]]
    defaults = {
        "language": "th",
        "download_dir": os.path.join(os.path.expanduser("~"), "Downloads"),
        "format": "best",
        "limit": "unlimited",
        "cookies_browser": "",
        "playlist": False,
        "geometry": "860x640",
    }
    return {**defaults, **cfg}


def save_config(cfg: dict) -> None:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as fh:
            json.dump(cfg, fh, ensure_ascii=False, indent=2)
    except OSError:
        pass


def resource_path(rel: str) -> str:
    """Resolve resource path for both dev mode and PyInstaller onefile."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def find_ffmpeg() -> str | None:
    """Locate ffmpeg: bundled via imageio-ffmpeg first, then next to the exe, then PATH."""
    try:
        import imageio_ffmpeg

        p = imageio_ffmpeg.get_ffmpeg_exe()
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    candidates = [
        os.path.join(os.path.dirname(sys.executable), "ffmpeg.exe"),
        os.path.join(getattr(sys, "_MEIPASS", ""), "ffmpeg.exe"),
        shutil.which("ffmpeg"),
    ]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass and os.path.isdir(meipass):
        import glob

        hits = glob.glob(os.path.join(meipass, "ffmpeg*.exe"))
        if hits:
            return hits[0]
    return None


@dataclass
class DownloadItem:
    url: str
    fmt: str  # format id: best/1080/720/480/mp3
    limit: str  # speed id
    status: str = "รอคิว"
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    title: str = ""
    error: str = ""
    ydl: Any = None
    cancelled: bool = False


def progress_bar_text(pct: float) -> str:
    """แถบความคืบหน้าแบบตัวอักษรสำหรับช่องในตาราง (10 ช่อง)"""
    filled = max(0, min(10, int(round(pct / 10.0))))
    return "█" * filled + "░" * (10 - filled)


class HookBridge:
    """Collects yt-dlp progress events from the worker thread into a thread-safe queue."""

    def __init__(self, event_q: "queue.Queue[tuple]", stop_flag: threading.Event, item: DownloadItem) -> None:
        self.event_q = event_q
        self.stop_flag = stop_flag
        self.item = item

    def __call__(self, d: dict) -> None:
        if self.stop_flag.is_set():
            raise yt_dlp.utils.DownloadCancelled("ยกเลิกโดยผู้ใช้")
        status = d.get("status")
        if status == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            done = d.get("downloaded_bytes") or 0
            pct = (done / total * 100.0) if total else 0.0
            speed = d.get("speed")
            eta = d.get("eta")
            self.item.progress = pct
            self.event_q.put((
                "progress",
                self.item,
                pct,
                f"{speed / 1_048_576:.1f} MB/s" if speed else "",
                f"{eta}s" if eta is not None else "",
            ))
        elif status == "finished":
            self.event_q.put(("merging",))


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.cfg = load_config()
        self.lang = self.cfg.get("language", "th")

        root.title(f"{APP_TITLE} v{APP_VERSION}")
        root.geometry(self.cfg.get("geometry", "860x640"))
        root.minsize(760, 560)
        try:
            root.iconbitmap(resource_path("icon.ico"))
        except tk.TclError:
            pass

        ffmpeg = find_ffmpeg()
        self.ffmpeg_path = ffmpeg
        self.event_q: "queue.Queue[tuple]" = queue.Queue()
        self.items: list[DownloadItem] = []
        self.tree_iids: dict[str, str] = {}
        self.worker: threading.Thread | None = None
        self.stop_flag = threading.Event()
        self._closing = False

        self._build_menu()
        self._build_ui(ffmpeg is not None)
        self.root.after(100, self._poll_events)
        self.root.after(1200, self._check_updates_silent)
        root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ---------- helpers ----------
    def tr(self, key: str, **kw) -> str:
        text = LANG.get(self.lang, LANG["th"]).get(key) or LANG["th"].get(key) or key
        return text.format(**kw) if kw else text

    def fmt_label(self, fid: str) -> str:
        return self.tr(f"fmt_{fid}")

    def speed_label(self, sid: str) -> str:
        return self.tr(f"sp_{sid}")

    # ---------- Menu ----------
    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        lang_menu = tk.Menu(menubar, tearoff=0)
        self.lang_var = tk.StringVar(value=self.lang)
        for code, label in (("th", "ไทย"), ("en", "English")):
            lang_menu.add_radiobutton(label=label, variable=self.lang_var,
                                      value=code, command=lambda c=code: self._switch_lang(c))
        menubar.add_cascade(label=self.tr("menu_lang"), menu=lang_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label=self.tr("menu_check_update"), command=self._check_updates_manual)
        help_menu.add_command(label=self.tr("menu_about"), command=self._show_about)
        menubar.add_cascade(label=self.tr("menu_help"), menu=help_menu)
        self.root.config(menu=menubar)
        self.menubar = menubar

    def _switch_lang(self, code: str) -> None:
        self.lang = code
        self.cfg["language"] = code
        save_config(self.cfg)
        # สร้าง UI ใหม่ทั้งหมดด้วยภาษาใหม่
        for w in self.root.winfo_children():
            if not isinstance(w, tk.Menu):
                w.destroy()
        self._build_menu()
        self._build_ui(self.ffmpeg_path is not None)

    # ---------- UI ----------
    def _build_ui(self, has_ffmpeg: bool) -> None:
        pad = {"padx": 10, "pady": 6}

        self.update_banner = tk.Label(self.root, text="", fg="#fff", bg="#b45309", cursor="hand2")
        self.update_banner.pack(fill="x")
        self.update_banner.pack_forget()

        top = ttk.LabelFrame(self.root, text=self.tr("url_frame"))
        top.pack(fill="x", **pad)
        self.url_text = tk.Text(top, height=5, wrap="word", undo=True)
        self.url_text.pack(fill="both", expand=True, padx=8, pady=8)

        opts = ttk.Frame(self.root)
        opts.pack(fill="x", **pad)

        ttk.Label(opts, text=self.tr("quality")).grid(row=0, column=0, sticky="w")
        fmt_ids = list(FORMAT_MAP)
        self.fmt_var = tk.StringVar(value=self.cfg.get("format", "best"))
        ttk.Combobox(opts, textvariable=self.fmt_var, state="readonly", width=28,
                     values=[self.fmt_label(f) for f in fmt_ids]).grid(row=0, column=1, sticky="w", padx=(4, 16))

        ttk.Label(opts, text=self.tr("speed")).grid(row=0, column=2, sticky="w")
        speed_ids = list(SPEED_MAP)
        self.limit_var = tk.StringVar(value=self.cfg.get("limit", "unlimited"))
        ttk.Combobox(opts, textvariable=self.limit_var, state="readonly", width=10,
                     values=[self.speed_label(s) for s in speed_ids]).grid(row=0, column=3, sticky="w", padx=4)

        ttk.Label(opts, text=self.tr("cookies")).grid(row=0, column=4, sticky="w", padx=(16, 0))
        self.cookies_var = tk.StringVar(value=self.cfg.get("cookies_browser", ""))
        ck_vals = [self.tr("ck_none")] + [b for b in COOKIES_BROWSERS if b]
        self.cookies_cb = ttk.Combobox(opts, textvariable=self.cookies_var, state="readonly",
                                       values=ck_vals, width=10)
        self.cookies_cb.grid(row=0, column=5, sticky="w", padx=4)

        self.playlist_var = tk.BooleanVar(value=bool(self.cfg.get("playlist", False)))
        ttk.Checkbutton(opts, text=self.tr("playlist"), variable=self.playlist_var)\
            .grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        ttk.Label(opts, text=self.tr("dest")).grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.dir_var = tk.StringVar(value=self.cfg.get("download_dir", ""))
        ttk.Entry(opts, textvariable=self.dir_var).grid(row=2, column=1, columnspan=4, sticky="we", padx=4, pady=(8, 0))
        ttk.Button(opts, text=self.tr("browse"), command=self._pick_dir).grid(row=2, column=5, sticky="w", padx=4, pady=(8, 0))

        opts.columnconfigure(1, weight=1)

        if not has_ffmpeg:
            ttk.Label(self.root, text=self.tr("warn_ffmpeg"), foreground="#b45309").pack(fill="x", padx=12)

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", **pad)
        self.start_btn = ttk.Button(btns, text=self.tr("start"), command=self._start)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text=self.tr("cancel"), command=self._cancel_all, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        self.open_btn = ttk.Button(btns, text=self.tr("open"), command=self._open_folder)
        self.open_btn.pack(side="right")

        columns = ("title", "progress", "status", "speed")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=9)
        self.tree.heading("title", text=self.tr("col_title"))
        self.tree.heading("progress", text=self.tr("col_progress"))
        self.tree.heading("status", text=self.tr("col_status"))
        self.tree.heading("speed", text=self.tr("col_speed"))
        self.tree.column("title", width=330)
        self.tree.column("progress", width=170, anchor="center")
        self.tree.column("status", width=130, anchor="center")
        self.tree.column("speed", width=170, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        self.pb = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.pb.pack(fill="x", padx=10, pady=(0, 2))

        self.status_var = tk.StringVar(value=self.tr("ready"))
        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(fill="x", padx=12, pady=(0, 8))

    # ---------- Actions ----------
    def _current_format_id(self) -> str:
        sel = self.fmt_var.get()
        for fid in FORMAT_MAP:
            if self.fmt_label(fid) == sel:
                return fid
        return "best"

    def _current_speed_id(self) -> str:
        sel = self.limit_var.get()
        for sid in SPEED_MAP:
            if self.speed_label(sid) == sel:
                return sid
        return "unlimited"

    def _current_cookies(self) -> str:
        sel = self.cookies_var.get()
        if not sel or sel == self.tr("ck_none"):
            return ""
        return sel if sel in COOKIES_BROWSERS else ""

    def _pick_dir(self) -> None:
        d = filedialog.askdirectory(initialdir=self.dir_var.get() or os.path.expanduser("~"))
        if d:
            self.dir_var.set(d)

    def _open_folder(self) -> None:
        path = self.dir_var.get()
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606
        elif sys.platform == "darwin":
            os.system(f'open "{path}" &')  # noqa: S605
        else:
            os.system(f'xdg-open "{path}" &')  # noqa: S605

    def _persist_settings(self) -> None:
        self.cfg.update({
            "download_dir": self.dir_var.get(),
            "format": self._current_format_id(),
            "limit": self._current_speed_id(),
            "cookies_browser": self._current_cookies(),
            "playlist": bool(self.playlist_var.get()),
            "geometry": self.root.winfo_geometry(),
            "language": self.lang,
        })
        save_config(self.cfg)

    def _on_close(self) -> None:
        self._persist_settings()
        self._closing = True
        self.root.destroy()

    def _start(self) -> None:
        urls = [u.strip() for u in self.url_text.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showwarning(APP_TITLE, self.tr("err_no_url"))
            return
        if not os.path.isdir(self.dir_var.get()):
            messagebox.showwarning(APP_TITLE, self.tr("err_bad_dir"))
            return
        self._persist_settings()

        self.items = [DownloadItem(url=u, fmt=self._current_format_id(), limit=self._current_speed_id()) for u in urls]
        self.tree.delete(*self.tree.get_children())
        self.tree_iids.clear()
        for it in self.items:
            iid = self.tree.insert("", "end", values=(it.url, progress_bar_text(0), it.status, ""))
            self.tree_iids[id(it)] = iid

        self.stop_flag.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.status_var.set(self.tr("downloading"))
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

    def _cancel_all(self) -> None:
        self.stop_flag.set()
        for it in self.items:
            it.cancelled = True
        self.status_var.set(self.tr("canceling"))

    # ---------- Update check ----------
    def _check_updates_silent(self) -> None:
        threading.Thread(target=self._check_updates_worker, args=(False,), daemon=True).start()

    def _check_updates_manual(self) -> None:
        self.status_var.set("...")
        threading.Thread(target=self._check_updates_worker, args=(True,), daemon=True).start()

    def _check_updates_worker(self, verbose: bool) -> None:
        try:
            req = urllib.request.Request(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                headers={"Accept": "application/vnd.github+json"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:  # noqa: S310
                data = json.loads(resp.read().decode("utf-8"))
            tag = str(data.get("tag_name", "")).lstrip("v")
            m_new = tuple(int(x) for x in tag.split(".")[:3]) if re.match(r"^\d+(\.\d+){1,2}$", tag) else None
            m_cur = tuple(int(x) for x in APP_VERSION.split(".")[:3])
            if m_new and m_new > m_cur:
                self.event_q.put(("update", f"v{tag}"))
            elif verbose:
                self.event_q.put(("uptodate", f"v{tag or APP_VERSION}"))
        except Exception:
            if verbose:
                self.event_q.put(("uptodate", f"v{APP_VERSION}"))

    def _open_release_page(self, _evt: object = None) -> None:
        webbrowser.open(f"https://github.com/{GITHUB_REPO}/releases/latest")

    def _show_about(self) -> None:
        messagebox.showinfo(APP_TITLE, self.tr("about", app=APP_TITLE, v=APP_VERSION, repo=GITHUB_REPO))

    # ---------- Worker ----------
    def _worker(self) -> None:
        ffmpeg = self.ffmpeg_path
        for it in self.items:
            if self.stop_flag.is_set():
                it.status = "ยกเลิก"
                self.event_q.put(("row", it, it.status, it.progress, "", ""))
                continue
            fmt = FORMAT_MAP.get(it.fmt, FORMAT_MAP["best"])
            audio_only = fmt.startswith("bestaudio")
            cookies = self._current_cookies()
            outtmpl = os.path.join(self.dir_var.get(), "%(title).150s.%(ext)s")
            opts: dict[str, Any] = {
                "format": fmt,
                "outtmpl": outtmpl,
                "progress_hooks": [HookBridge(self.event_q, self.stop_flag, it)],
                "noprogress": True,
                "quiet": True,
                "no_warnings": True,
                "retries": 5,
                "fragment_retries": 5,
                "concurrent_fragment_downloads": 4,
                "restrictfilenames": False,
                "overwrites": False,
                "postprocessor_args": ["-movflags", "+faststart"],
                "noplaylist": not bool(self.playlist_var.get()),
            }
            if it.limit != "unlimited" and SPEED_MAP.get(it.limit):
                opts["ratelimit"] = _parse_rate(SPEED_MAP[it.limit] or "")
            if cookies:
                opts["cookiesfrombrowser"] = (cookies,)
            if ffmpeg:
                opts["ffmpeg_location"] = ffmpeg
            if audio_only:
                opts["postprocessors"] = [
                    {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                ]

            def row(status=it.status, prog=it.progress, speed="", eta=""):
                it.status = status
                self.event_q.put(("row", it, status, prog, speed, eta))

            row("กำลังดึงข้อมูล…", 0)
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    it.ydl = ydl
                    info = ydl.extract_info(it.url, download=True)
                    it.title = (info or {}).get("title") or it.url
                    if self.stop_flag.is_set() and it.cancelled:
                        raise yt_dlp.utils.DownloadCancelled("ยกเลิกโดยผู้ใช้")
                    row("สำเร็จ ✓", 100, "", "")
            except yt_dlp.utils.DownloadCancelled:
                row("ยกเลิก", it.progress, "", "")
            except Exception as exc:  # noqa: BLE001
                row("ลองโหมดสำรอง…", it.progress, "", "")
                saved = self._fallback(it, row)
                if not saved:
                    if self.stop_flag.is_set():
                        row("ยกเลิก", it.progress, "", "")
                    else:
                        it.error = str(exc)
                        row("ล้มเหลว ✗", it.progress, "", "")
            finally:
                it.ydl = None
        self.event_q.put(("done",))

    def _fallback(self, it: DownloadItem, row) -> list[str]:
        """โหมดสำรอง: HTML/media scraper + direct streaming (ใช้เมื่อ yt-dlp ล้มเหลว)"""

        def on_prog(pct: float, speed: str) -> None:
            it.progress = pct
            row("สำรอง: กำลังโหลด…", pct, speed, "")

        try:
            saved = html_media.smart_download(it.url, self.dir_var.get(), self.stop_flag, on_prog)
        except html_media.DownloadAborted:
            return []
        except Exception as exc:  # noqa: BLE001
            it.error = f"fallback: {exc}"
            return []
        if saved:
            it.title = os.path.basename(saved[0])
            row("สำเร็จ (สำรอง) ✓", 100, "", "")
        return saved

    # ---------- Event pump ----------
    def _poll_events(self) -> None:
        if self._closing:
            return
        try:
            while True:
                ev = self.event_q.get_nowait()
                kind = ev[0]
                if kind == "progress":
                    _, it, pct, speed, eta = ev
                    self.pb["value"] = pct
                    iid = self.tree_iids.get(id(it))
                    if iid:
                        self.tree.set(iid, "progress", f"{progress_bar_text(pct)} {pct:.0f}%")
                        self.tree.set(iid, "speed", f"{speed} {eta}".strip())
                    self.status_var.set(f"{self.tr('downloading')} {pct:.1f}%  {speed}  {eta}")
                elif kind == "row":
                    _, it, status, prog, speed, eta = ev
                    iid = self.tree_iids.get(id(it))
                    if iid:
                        title = it.title or it.url
                        self.tree.set(iid, "title", title[:120])
                        self.tree.set(iid, "progress", f"{progress_bar_text(prog)} {prog:.0f}%")
                        self.tree.set(iid, "status", status)
                        self.tree.set(iid, "speed", f"{speed} {eta}".strip())
                        if status.startswith("สำเร็จ") or status.startswith("ล้มเหลว") or status == "ยกเลิก":
                            self.pb["value"] = 0
                elif kind == "merging":
                    self.status_var.set(self.tr("merging"))
                elif kind == "update":
                    tag = ev[1]
                    self.update_banner.config(text=self.tr("update_banner", v=tag))
                    self.update_banner.pack(fill="x", before=self.root.winfo_children()[0])
                    self.update_banner.bind("<Button-1>", self._open_release_page)
                elif kind == "uptodate":
                    self.status_var.set(self.tr("uptodate", v=ev[1].lstrip("v")))
                elif kind == "done":
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.status_var.set(self.tr("done_all"))
                    ok = sum(1 for i in self.items if i.status.startswith("สำเร็จ"))
                    fails = [i for i in self.items if i.status == "ล้มเหลว ✗"]
                    if fails:
                        first = fails[0]
                        messagebox.showwarning(
                            APP_TITLE,
                            f"สำเร็จ {ok} รายการ, ล้มเหลว {len(fails)} รายการ\n\nตัวอย่างข้อผิดพลาด:\n{first.error[:500]}",
                        )
        except queue.Empty:
            pass
        self.root.after(100, self._poll_events)


def _parse_rate(text: str) -> float:
    """'1M' -> bytes/sec float."""
    text = text.strip().upper()
    mult = 1.0
    if text.endswith("K"):
        mult, text = 1024.0, text[:-1]
    elif text.endswith("M"):
        mult, text = 1024.0 ** 2, text[:-1]
    return float(text) * mult


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
