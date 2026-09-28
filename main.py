#!/usr/bin/env python3
"""Video Downloader GUI - ดาวน์โหลดวีดีโอจากเว็บไซต์สาธารณะด้วย yt-dlp

รองรับ: YouTube, TikTok, Facebook, X/Twitter, Instagram (สาธารณะ), Vimeo
และอีกหลายพันเว็บไซต์ ดูรายชื่อได้ที่ https://github.com/yt-dlp/yt-dlp

โปรดใช้เฉพาะกับคอนเทนต์ที่มีสิทธิ์ดาวน์โหลดตามกฎหมายและเงื่อนไขของแต่ละเว็บไซต์
"""

from __future__ import annotations

import os
import queue
import shutil
import sys
import threading
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

APP_TITLE = "Video Downloader GUI"
APP_VERSION = "1.0.0"

FORMAT_CHOICES = {
    "คุณภาพดีที่สุด (mp4)": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
    "1080p หรือต่ำกว่า": "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
    "720p หรือต่ำกว่า": "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720][ext=mp4]/best",
    "480p หรือต่ำกว่า": "bestvideo[height<=480][ext=mp4]+bestaudio[ext=m4a]/best[height<=480][ext=mp4]/best",
    "เสียงอย่างเดียว (mp3)": "bestaudio/best",
}

SPEED_LIMITS = {
    "ไม่จำกัด": None,
    "1 MB/s": "1M",
    "5 MB/s": "5M",
    "10 MB/s": "10M",
}


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
    # Fallback: any bundled ffmpeg* binary (e.g. ffmpeg-win-x86_64-v7.1.exe)
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
    fmt: str
    limit: str
    status: str = "รอคิว"
    progress: float = 0.0
    speed: str = ""
    eta: str = ""
    title: str = ""
    error: str = ""
    ydl: Any = None
    cancelled: bool = False


class HookBridge:
    """Collects yt-dlp progress events from the worker thread into a thread-safe queue."""

    def __init__(self, event_q: "queue.Queue[tuple]", stop_flag: threading.Event) -> None:
        self.event_q = event_q
        self.stop_flag = stop_flag

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
            self.event_q.put((
                "progress",
                pct,
                f"{speed / 1_048_576:.1f} MB/s" if speed else "",
                f"{eta}s" if eta is not None else "",
            ))
        elif status == "finished":
            self.event_q.put(("merging",))
        elif status == "error":
            self.event_q.put(("error", d.get("filename", "")))


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title(f"{APP_TITLE} v{APP_VERSION}")
        root.geometry("860x640")
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

        self._build_ui(ffmpeg is not None)
        self.root.after(100, self._poll_events)

    # ---------- UI ----------
    def _build_ui(self, has_ffmpeg: bool) -> None:
        pad = {"padx": 10, "pady": 6}

        top = ttk.LabelFrame(self.root, text="ลิงก์วีดีโอ (หนึ่งลิงก์ต่อบรรทัด)")
        top.pack(fill="x", **pad)
        self.url_text = tk.Text(top, height=5, wrap="word", undo=True)
        self.url_text.pack(fill="both", expand=True, padx=8, pady=8)
        self.url_text.insert("1.0", "https://www.youtube.com/watch?v=dQw4w9WgXcQ\n")

        opts = ttk.Frame(self.root)
        opts.pack(fill="x", **pad)

        ttk.Label(opts, text="คุณภาพ:").grid(row=0, column=0, sticky="w")
        self.fmt_var = tk.StringVar(value=next(iter(FORMAT_CHOICES)))
        fmt_cb = ttk.Combobox(opts, textvariable=self.fmt_var, state="readonly",
                              values=list(FORMAT_CHOICES), width=28)
        fmt_cb.grid(row=0, column=1, sticky="w", padx=(4, 16))

        ttk.Label(opts, text="จำกัดความเร็ว:").grid(row=0, column=2, sticky="w")
        self.limit_var = tk.StringVar(value=next(iter(SPEED_LIMITS)))
        lim_cb = ttk.Combobox(opts, textvariable=self.limit_var, state="readonly",
                              values=list(SPEED_LIMITS), width=10)
        lim_cb.grid(row=0, column=3, sticky="w", padx=4)

        ttk.Label(opts, text="โฟลเดอร์ปลายทาง:").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.dir_var = tk.StringVar(value=os.path.join(os.path.expanduser("~"), "Downloads"))
        dir_entry = ttk.Entry(opts, textvariable=self.dir_var)
        dir_entry.grid(row=1, column=1, columnspan=2, sticky="we", padx=4, pady=(8, 0))
        ttk.Button(opts, text="เลือก…", command=self._pick_dir).grid(row=1, column=3, sticky="w", padx=4, pady=(8, 0))

        opts.columnconfigure(1, weight=1)

        if not has_ffmpeg:
            warn = ttk.Label(
                self.root,
                text="⚠ ไม่พบ ffmpeg — การรวมไฟล์วีดีโอ/เสียงคุณภาพสูงและการแปลง mp3 อาจใช้ไม่ได้",
                foreground="#b45309",
            )
            warn.pack(fill="x", padx=12)

        btns = ttk.Frame(self.root)
        btns.pack(fill="x", **pad)
        self.start_btn = ttk.Button(btns, text="▶ เริ่มดาวน์โหลด", command=self._start)
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text="■ ยกเลิกทั้งหมด", command=self._cancel_all, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        self.open_btn = ttk.Button(btns, text="📂 เปิดโฟลเดอร์", command=self._open_folder)
        self.open_btn.pack(side="right")

        columns = ("title", "progress", "status", "speed")
        self.tree = ttk.Treeview(self.root, columns=columns, show="headings", height=9)
        self.tree.heading("title", text="รายการ")
        self.tree.heading("progress", text="ความคืบหน้า")
        self.tree.heading("status", text="สถานะ")
        self.tree.heading("speed", text="ความเร็ว/เวลาที่เหลือ")
        self.tree.column("title", width=340)
        self.tree.column("progress", width=110, anchor="center")
        self.tree.column("status", width=140, anchor="center")
        self.tree.column("speed", width=180, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        style = ttk.Style(self.root)
        style.layout("Horizontal.TProgressbar",
                     [("Horizontal.Progressbar.trough", {"children": [("Horizontal.Progressbar.pbar", {"side": "left", "sticky": "ns"})], "sticky": "we"}),
                      ("Horizontal.Progressbar.border", {"sticky": "we"})])
        self.pb = ttk.Progressbar(self.root, mode="determinate", maximum=100)
        self.pb.pack(fill="x", padx=10, pady=(0, 2))

        self.status_var = tk.StringVar(value="พร้อมทำงาน")
        ttk.Label(self.root, textvariable=self.status_var, anchor="w").pack(fill="x", padx=12, pady=(0, 8))

    # ---------- Actions ----------
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

    def _start(self) -> None:
        urls = [u.strip() for u in self.url_text.get("1.0", "end").splitlines() if u.strip()]
        if not urls:
            messagebox.showwarning(APP_TITLE, "กรุณาวางลิงก์วีดีโออย่างน้อยหนึ่งลิงก์")
            return
        if not os.path.isdir(self.dir_var.get()):
            messagebox.showwarning(APP_TITLE, "โฟลเดอร์ปลายทางไม่มีอยู่ — กรุณาเลือกใหม่")
            return

        self.items = [DownloadItem(url=u, fmt=self.fmt_var.get(), limit=self.limit_var.get()) for u in urls]
        self.tree.delete(*self.tree.get_children())
        self.tree_iids.clear()
        for it in self.items:
            iid = self.tree.insert("", "end", values=(it.url, "0%", it.status, ""))
            self.tree_iids[id(it)] = iid

        self.stop_flag.clear()
        self.start_btn.config(state="disabled")
        self.cancel_btn.config(state="normal")
        self.status_var.set("กำลังดาวน์โหลด…")
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

    def _cancel_all(self) -> None:
        self.stop_flag.set()
        for it in self.items:
            it.cancelled = True
        self.status_var.set("กำลังยกเลิก…")

    # ---------- Worker ----------
    def _worker(self) -> None:
        ffmpeg = self.ffmpeg_path
        for it in self.items:
            if self.stop_flag.is_set():
                it.status = "ยกเลิก"
                self.event_q.put(("row", it, it.status, it.progress, "", ""))
                continue
            fmt = FORMAT_CHOICES.get(it.fmt, "best")
            audio_only = fmt.startswith("bestaudio")
            outtmpl = os.path.join(self.dir_var.get(), "%(title).150s.%(ext)s")
            opts: dict[str, Any] = {
                "format": fmt,
                "outtmpl": outtmpl,
                "progress_hooks": [HookBridge(self.event_q, self.stop_flag)],
                "noprogress": True,
                "quiet": True,
                "no_warnings": True,
                "retries": 5,
                "fragment_retries": 5,
                "concurrent_fragment_downloads": 4,
                "restrictfilenames": False,
                "overwrites": False,
                "postprocessor_args": ["-movflags", "+faststart"],
            }
            if it.limit != "ไม่จำกัด" and SPEED_LIMITS.get(it.limit):
                opts["ratelimit"] = _parse_rate(SPEED_LIMITS[it.limit])
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
                it.error = str(exc)
                row("ล้มเหลว ✗", it.progress, "", "")
            finally:
                it.ydl = None
        self.event_q.put(("done",))

    # ---------- Event pump ----------
    def _poll_events(self) -> None:
        try:
            while True:
                ev = self.event_q.get_nowait()
                kind = ev[0]
                if kind == "progress":
                    _, pct, speed, eta = ev
                    self.pb["value"] = pct
                    self.status_var.set(f"กำลังดาวน์โหลด… {pct:.1f}%  {speed}  เหลือ {eta}")
                elif kind == "row":
                    _, it, status, prog, speed, eta = ev
                    iid = self.tree_iids.get(id(it))
                    if iid:
                        title = it.title or it.url
                        self.tree.set(iid, "title", title[:120])
                        self.tree.set(iid, "progress", f"{prog:.0f}%")
                        self.tree.set(iid, "status", status)
                        self.tree.set(iid, "speed", f"{speed} {eta}".strip())
                        if status.startswith("สำเร็จ") or status.startswith("ล้มเหลว") or status == "ยกเลิก":
                            self.pb["value"] = 0
                elif kind == "merging":
                    self.status_var.set("กำลังรวมไฟล์วีดีโอ+เสียง…")
                elif kind == "done":
                    self.start_btn.config(state="normal")
                    self.cancel_btn.config(state="disabled")
                    self.status_var.set("เสร็จสิ้นทุกรายการ")
                    ok = sum(1 for i in self.items if i.status == "สำเร็จ ✓")
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
