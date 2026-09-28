#!/usr/bin/env python3
"""Generate docs/img/banner.png and docs/img/screenshot.png illustrations."""
from PIL import Image, ImageDraw, ImageFilter, ImageFont
import os


def load_font(size, bold=False):
    for name in ([" tahomabd.ttf", "tahoma.ttf"] if bold else ["tahoma.ttf"]):
        try:
            return ImageFont.truetype(name.replace(" ", ""), size)
        except OSError:
            continue
    return ImageFont.load_default()

HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = os.path.abspath(os.path.join(HERE, "..", "docs", "img"))
os.makedirs(OUTDIR, exist_ok=True)


def gradient(size, top, bottom):
    w, h = size
    img = Image.new("RGBA", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        t = y / max(h - 1, 1)
        c = tuple(int(top[i] + t * (bottom[i] - top[i])) for i in range(3)) + (255,)
        d.line([(0, y), (w, y)], fill=c)
    return img


# ---------------- Banner 1200x400 ----------------
W, H = 1200, 400
banner = gradient((W, H), (94, 118, 211), (231, 48, 26))
d = ImageDraw.Draw(banner)

# soft circles decoration
for cx, cy, r, alpha in [(980, 60, 160, 28), (1080, 330, 200, 22), (760, 300, 120, 18)]:
    circ = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(circ).ellipse([cx - r, cy - r, cx + r, cy + r], fill=(255, 255, 255, alpha))
    banner.alpha_composite(circ.filter(ImageFilter.GaussianBlur(6)))

# big play button
ps = Image.new("RGBA", (W, H), (0, 0, 0, 0))
pd = ImageDraw.Draw(ps)
pd.ellipse([120, 110, 300, 290], fill=(255, 255, 255, 235))
pd.polygon([(192, 158), (192, 242), (262, 200)], fill=(94, 118, 211, 255))
banner.alpha_composite(ps.filter(ImageFilter.GaussianBlur(1)))

d = ImageDraw.Draw(banner)
f_title = load_font(64, bold=True)
f_sub = load_font(27)
d.text((340, 138), "Video Downloader GUI", font=f_title, fill=(255, 255, 255, 255))
d.text((342, 232), "yt-dlp + tkinter  |  Windows EXE  |  ไม่ต้องติดตั้ง Python", font=f_sub, fill=(255, 235, 235, 255))
# version pill
pill_w, pill_h = 150, 44
d.rounded_rectangle([340, 292, 340 + pill_w, 292 + pill_h], radius=22, fill=(255, 255, 255, 40), outline=(255, 255, 255, 120))
f_pill = load_font(22, bold=True)
d.text((340 + 26, 292 + 8), "v1.0.0", font=f_pill, fill=(255, 255, 255, 255))
banner.save(os.path.join(OUTDIR, "banner.png"))
print("banner.png", banner.size)

# ---------------- GUI mockup 1280x800 ----------------
W, H = 1280, 800
app = Image.new("RGBA", (W, H), (243, 244, 246, 255))
d = ImageDraw.Draw(app)

# window chrome
d.rounded_rectangle([0, 0, W, 52], radius=8, fill=(255, 255, 255, 255))
d.line([(0, 52), (W, 52)], fill=(229, 231, 235, 255), width=2)
d.ellipse([20, 20, 34, 34], fill=(239, 68, 68, 255))
d.ellipse([44, 20, 58, 34], fill=(245, 158, 11, 255))
d.ellipse([68, 20, 82, 34], fill=(34, 197, 94, 255))
d.text((100, 16), "Video Downloader GUI  v1.0.0", fill=(75, 85, 99, 255))

# url box
d.rounded_rectangle([30, 80, W - 30, 170], radius=10, fill=(255, 255, 255, 255), outline=(209, 213, 219, 255))
d.text((50, 95), "ลิงก์วีดีโอ (หนึ่งลิงก์ต่อบรรทัด)", font=load_font(20), fill=(107, 114, 128, 255))
d.text((50, 125), "https://www.youtube.com/watch?v=dQw4w9WgXcQ", font=load_font(22), fill=(31, 41, 55, 255))

# option chips
f_ui = load_font(19)
d.rounded_rectangle([30, 195, 340, 240], radius=10, fill=(255, 255, 255, 255), outline=(209, 213, 219, 255))
d.text((50, 208), "คุณภาพ: คุณภาพดีที่สุด (mp4)", font=f_ui, fill=(31, 41, 55, 255))
d.rounded_rectangle([360, 195, 580, 240], radius=10, fill=(255, 255, 255, 255), outline=(209, 213, 219, 255))
d.text((380, 208), "จำกัดความเร็ว: ไม่จำกัด", font=f_ui, fill=(31, 41, 55, 255))
d.rounded_rectangle([600, 195, 990, 240], radius=10, fill=(255, 255, 255, 255), outline=(209, 213, 219, 255))
d.text((620, 208), "โฟลเดอร์: C:\\Users\\me\\Downloads", font=f_ui, fill=(31, 41, 55, 255))

# buttons
f_btn = load_font(21, bold=True)
d.rounded_rectangle([30, 265, 235, 315], radius=10, fill=(79, 70, 229, 255))
d.text((58, 279), "▶ เริ่มดาวน์โหลด", font=f_btn, fill=(255, 255, 255, 255))
d.rounded_rectangle([255, 265, 440, 315], radius=10, fill=(229, 231, 235, 255))
d.text((283, 279), "■ ยกเลิกทั้งหมด", font=f_btn, fill=(55, 65, 81, 255))
d.rounded_rectangle([W - 225, 265, W - 30, 315], radius=10, fill=(229, 231, 235, 255))
d.text((W - 195, 279), "📂 เปิดโฟลเดอร์", font=f_btn, fill=(55, 65, 81, 255))

# table
f_col = load_font(19)
f_cell = load_font(18)
tx0, ty0 = 30, 340
d.rounded_rectangle([tx0, ty0, W - 30, ty0 + 300], radius=10, fill=(255, 255, 255, 255), outline=(209, 213, 219, 255))
cols = [("รายการ", tx0 + 20), ("ความคืบหน้า", 620), ("สถานะ", 820), ("ความเร็ว", 970)]
for name, x in cols:
    d.text((x, ty0 + 14), name, font=f_col, fill=(107, 114, 128, 255))
d.line([(tx0, ty0 + 50), (W - 30, ty0 + 50)], fill=(229, 231, 235, 255), width=2)

rows = [
    ("Rick Astley - Never Gonna Give You Up", 100, "กำลังดาวน์โหลด…", "8.2 MB/s เหลือ 12s"),
    ("Some Channel - clip 2026", 64, "กำลังรวมไฟล์…", ""),
    ("Vimeo - Explainer video", 100, "สำเร็จ ✓", ""),
]
for i, (title, pct, status, speed) in enumerate(rows):
    y = ty0 + 70 + i * 76
    d.text((tx0 + 20, y), title, font=f_cell, fill=(31, 41, 55, 255))
    bx, bw = 620, 150
    d.rounded_rectangle([bx, y + 2, bx + bw, y + 22], radius=10, fill=(229, 231, 235, 255))
    d.rounded_rectangle([bx, y + 2, bx + int(bw * pct / 100), y + 22], radius=10, fill=(79, 70, 229, 255))
    d.text((bx + bw + 12, y), f"{pct}%", font=f_cell, fill=(55, 65, 81, 255))
    d.text((820, y), status, font=f_cell, fill=(22, 163, 74, 255) if "สำเร็จ" in status else (55, 65, 81, 255))
    if speed:
        d.text((970, y), speed, font=f_cell, fill=(107, 114, 128, 255))

# bottom progress + status
d.rounded_rectangle([30, 680, W - 30, 712], radius=10, fill=(229, 231, 235, 255))
d.rounded_rectangle([30, 680, 30 + int((W - 60) * 0.42), 712], radius=10, fill=(79, 70, 229, 255))
d.text((30, 730), "กำลังดาวน์โหลด… 42.0%  8.2 MB/s  เหลือ 12s", font=f_cell, fill=(55, 65, 81, 255))

app.save(os.path.join(OUTDIR, "screenshot.png"))
print("screenshot.png", app.size)
