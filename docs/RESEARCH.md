# Research — Video Downloader GUI

![banner](img/banner.png)

เอกสารสรุปงานวิจัยและเหตุผลการตัดสินใจทางเทคนิคของโปรเจกต์ ครอบคลุม: เลือกเอนจินดาวน์โหลด, เฟรมเวิร์ก UI, การแพ็ก EXE, การกระจายไฟล์, และความเสี่ยง

---

## 1. การเลือกเอนจินดาวน์โหลด

| ตัวเลือก | รองรับเว็บไซต์ | ดูแลรักษา | ภาษา | คะแนนรวม |
|---|---|---|---|---|
| **yt-dlp** ✅ | 1,000+ เว็บไซต์ | Active (release ทุกเดือน) | Python | ★★★★★ |
| youtube-dl (ต้นทาง) | ~1,000 | ช้ามากนับจาก 2021 | Python | ★★ |
| gallery-dl | เน้นรูปภาพ/คลังรูป | Active | Python | ★★★ (ไม่ตรงงานวีดีโอ) |
| พัฒนา scraper เอง | เว็บละ 1 ชุดโค้ด | ต้องดูแลเองทุกเว็บ | อะไรก็ได้ | ★ (บำรุงรักษาไม่ไหว) |

**ข้อสรุป:** เลือก `yt-dlp` เพราะ (1) รองรับเว็บไซต์จำนวนมากด้วย extractors ที่ชุมชนดูแล, (2) เป็น Python จึงฝังเป็นไลบรารีได้โดยตรง (`import yt_dlp`), (3) มี progress hooks, format selection และ rate limiting ในตัว, (4) release ถี่พอจะตามการเปลี่ยนแปลงของแพลตฟอร์มได้

### จุดสำคัญที่ใช้จาก yt-dlp

- `format` selector เช่น `bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best` เพื่อบังคับ mp4 ที่เล่นได้ทุกเครื่อง
- `progress_hooks` สำหรับดึงเปอร์เซ็นต์/ความเร็ว/ETA มาแสดงใน GUI
- `ratelimit` สำหรับจำกัดความเร็ว, `concurrent_fragment_downloads` เพิ่มความเร็วชิ้นส่วน
- `postprocessors: FFmpegExtractAudio` สำหรับโหมดแยกเสียง MP3

## 2. การเลือกเฟรมเวิร์ก GUI

| ตัวเลือก | ขนาดหลังแพ็ก | ความยาก | ธีมสวย | พอเพียงกับงานนี้ |
|---|---|---|---|---|
| **tkinter/ttk** ✅ | 0 MB เพิ่ม (มากับ Python) | ต่ำ | พอใช้ | ✅ |
| PySide6 / Qt | +60–80 MB | กลาง | สวย | over-engineering |
| CustomTkinter | +10 MB | ต่ำ | สวยกว่า ttk | สำรองไว้เป็น phase 2 |
| Electron/Tauri | +100 MB / +5 MB | สูง (ต้องเขียน 2 ภาษา) | สวยมาก | ไม่คุ้ม |

**ข้อสรุป:** tkinter มาพร้อม Python, เสถียร, แพ็กแล้วไฟล์เล็กที่สุด — เหมาะกับเครื่องมือสาธารณะประเภท "เปิด วางลิงก์ กดดาวน์โหลด" ถ้าอนาคตต้องการธีมสวยขึ้น สามารถเปลี่ยนไป CustomTkinter โดยคงโครงสร้าง `App` เดิมได้

## 3. การจัดการ ffmpeg

ปัญหา: วิดีโอคุณภาพสูงบน YouTube แยกไฟล์วีดีโอ (webm/mp4) กับเสียง (m4a) ออกจากกัน ต้องใช้ ffmpeg รวมกลับ

ทางเลือกที่พิจารณา:

1. ~~บังคับผู้ใช้ติดตั้ง ffmpeg เอง~~ — ขัดข้อง "ผู้ใช้ไม่ต้องติดตั้งอะไร"
2. ~~ดาวน์โหลด ffmpeg ตอน first-run~~ — ซับซ้อน, เสี่ยงโดน antivirus, ต้องมีเน็ต
3. **bundle ผ่านแพ็กเกจ `imageio-ffmpeg`** ✅ — ffmpeg-win-x86_64 (v7.1, ~25 MB) ถูก copy ลงใน EXE ตอน build ผ่าน `binaries` ใน .spec แล้วค้นหาตอน runtime ด้วยลำดับ: `imageio_ffmpeg.get_ffmpeg_exe()` → ข้าง EXE → `_MEIPASS` → PATH

## 4. Threading model ของ GUI

```
[Thread: worker]                    [Thread: UI (main)]
  yt_dlp.extract_info()  --queue-->  root.after(100ms) poll
  progress_hooks raise               อัปเดต Treeview/Progressbar
  DownloadCancelled เมื่อหยุด
```

- tkinter ไม่ thread-safe → ทุกอย่างที่แตะ UI ต้องอยู่บน main thread
- worker สื่อสารผ่าน `queue.Queue` เท่านั้น
- การยกเลิก: UI ตั้ง `threading.Event` → progress hook ของ yt-dlp (ซึ่งถูกเรียกบน worker thread) เช็คแฟล็กแล้ว raise `DownloadCancelled` → yt-dlp หยุดอย่างสะอาด

## 5. การแพ็ก EXE ด้วย PyInstaller

- โหมด **onefile + windowed** (`console=False`) → ไฟล์เดียว ไม่มีหน้าต่างดำ
- แนบ `icon.ico` 6 ขนาด (16–256px) + `version_info.txt` ให้ EXE มี metadata ครบ
- ผลทดสอบ: สร้างสำเร็จ, เปิดโปรแกรมได้ (smoke test 6 วินาที), ขนาด ~82.5 MB
- ข้อแลกเปลี่ยนที่ยอมรับ: onefile แตกไฟล์ลง temp ตอนเปิด (ช้า 2–5 วิแรก) — ถ้าอยากเร็วขึ้นเปลี่ยนเป็น onedir + zip ได้จาก .spec เดิม

## 6. การกระจายไฟล์ (Distribution)

| ช่องทาง | ข้อดี | ข้อเสีย |
|---|---|---|
| **GitHub Releases + Actions** ✅ | ฟรี, build อัตโนมัติจาก tag, มี SHA256 กำกับ | SmartScreen ยังเตือน (ไม่มี code signing) |
| code signing cert | ไม่มีเตือน | มีค่าใช้จ่ายรายปี (~$100–400) |
| Microsoft Store | การรับรองจาก MS | ค่าธรรมเนียม + กระบวนการ review |

**GitHub Actions (release.yml):** เมื่อ push tag `v*` → ติดตั้ง Python 3.13 + deps → build ด้วย .spec เดียวกับ local → คำนวณ SHA256 → สร้าง release อัตโนมัติพร้อมแนบ `VideoDownloaderGUI.exe` และ `checksums.txt`

**GitHub Pages (pages.yml + index.html):** หน้าเว็บสถิติ (ไม่มี build step) ดึง `https://api.github.com/repos/NarDecH/video-downloader-gui/releases/latest` แล้วแสดง: เวอร์ชัน, วันที่, ขนาดไฟล์, ปุ่มดาวน์โหลดตรงไปยัง asset, และค่า SHA256 จาก `checksums.txt` ใน release เดียวกัน — ทำให้ checksum แสดงบนหน้าเว็บ**ตรงกับไฟล์จริงเสมอ** เพราะมาจากแหล่งเดียวกัน (หมายเหตุ: API มี rate limit 60 ครั้ง/ชม./IP จึงแสดงข้อความแนะนำไป Releases เมื่อโดน limit)

## 7. ความเสี่ยงและการรับมือ

| ความเสี่ยง | ผลกระทบ | การรับมือ |
|---|---|---|
| เว็บไซต์เปลี่ยนโครงสร้าง → ดาวน์โหลดพัง | สูง | อัปเดต yt-dlp บ่อย; CI build จาก tag ใหม่ง่าย |
| SmartScreen เตือนผู้ใช้ใหม่ | กลาง | เอกสารอธิบาย "Run anyway" + เผยแพร่ SHA256 ให้ตรวจ |
| โดนถามถึงการใช้งานผิดกฎหมาย | กลาง | ข้อความ Legal ชัดเจนใน README/หน้าเว็บ; ไม่ใส่ฟีเจอร์เจาะจงเว็บผิดกฎหมาย |
| API rate limit บนหน้าเว็บ | ต่ำ | cache ผลลัพธ์ใน localStorage 1 ชม. + fallback ลิงก์ Releases |
| Python 3.14 ใหม่มาก แพ็กเกจบางตัวยังไม่รองรับ | ต่ำ | ทดสอบ build แล้วผ่านทั้งหมด; CI pin Python 3.13 เป็นตัวเลือกสำรอง |

## 8. แนวทางพัฒนาต่อ (Roadmap)

- [ ] คิวดาวน์โหลดแบบลากจัดลำดับ + จำกัดจำนวนงานขนาน
- [ ] รองรับ cookies (โฟลเดอร์ `--cookies-from-browser`) สำหรับคอนเทนต์ที่ต้องล็อกอิน
- [ ] ปุ่ม "เปิดไฟล์หลังเสร็จ" + notification ระบบ
- [ ] อัปเดตตัวติดตั้งแบบ auto-update (เช็ค release API จากในแอป)
- [ ] ธีมมืด/สว่าง (CustomTkinter)
