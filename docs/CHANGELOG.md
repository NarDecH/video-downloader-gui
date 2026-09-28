# Changelog

รูปแบบอ้างอิง [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) และใช้ [Semantic Versioning](https://semver.org/)

## [Unreleased]

### Added (เพิ่มใหม่)
- **Android: เอนจิน yt-dlp + ffmpeg จริงบนแอป — พร้อมใช้งานกับลิงก์ทั่วไป** (youtubedl-android):
  - วาง/แชร์ลิงก์จาก**เว็บใดก็ได้** (หลายพันเว็บไซต์) — ไม่จำกัดแค่ YouTube/SoundCloud/Bandcamp อีกต่อไป
  - รองรับ **HLS (.m3u8) และ DASH (.mpd)** รวมถึงเคส video+audio แยกไฟล์ที่ต้อง merge ด้วย ffmpeg (แพ็กมาในแอป) และแปลงเป็น mp3
  - **โหมดสำรองแยกสื่อจากหน้าเว็บ** พอร์ตจากเดสก์ท็อป: lazy-load `data-*`, สื่อใน JSON/สคริปต์ (escape `\/`, `\u0026`), manifest ใน player, iframe player — ใช้กับหน้า `player.html` ที่ฝัง player ภายนอกได้
  - เลือกคุณภาพสำหรับลิงก์ทั่วไป: ดีที่สุด / 1080p / 720p / 480p / เสียงเท่านั้น (mp3) — selector เดียวกับเดสก์ท็อป
  - **อัปเดตเอนจิน yt-dlp อัตโนมัติ** ครั้งแรกหลังติดตั้ง (จำสถานะไว้; เว็บเปลี่ยนบ่อยเอนจินต้องใหม่) — อัปเดตไม่ได้ก็ยังใช้เวอร์ชันที่แพ็กมาได้
  - บันทึกเข้า `Downloads/` ผ่าน MediaStore อย่างถูกต้องบน Android 10+ (Android 9 ลงไปใช้เส้นทางเดิมพร้อมขอสิทธิ์)
  - ลำดับการทำงานต่อลิงก์: NewPipe (เว็บรู้จัก) → เอนจิน yt-dlp → โหมดสำรองแยกสื่อ → ลองทีละ candidate จนสำเร็จ พร้อม progress %
  - APK ใหญ่ขึ้นเป็น ~156 MB เพราะแพ็ก Python + ffmpeg (ABI: arm64-v8a / armeabi-v7a / x86_64)
  - เทสต์ JVM ของ scraper 10 เคส (ไม่ใช้เครือข่าย) และยืนยัน build debug+release (R8) ผ่านทั้งคู่
- **เบราว์เซอร์ในแอป (WebView2)** — พิมพ์ URL เพื่อเปิดหน้าเว็บที่ต้องการในแอป (pywebview รันเป็นโปรเซสลูกบน MainThread ของตัวเอง สื่อสารผ่าน localhost TCP; ผู้ใช้คลิกลิงก์ในหน้าได้ปกติ ช่อง URL ตามอัตโนมัติ; ถ้าเปิดไม่ได้ (ไม่มี WebView2) จะ fallback เปิดเบราว์เซอร์ระบบให้เอง)
- **ปุ่ม "ดาวน์โหลดวีดีโอที่กำลังแสดง"** — สแกนหน้าที่เปิดอยู่ในเบราว์เซอร์แล้วดึงวีดีโอตรงจากหน้านั้น: จับ `<video>/<source>` ที่กำลังเล่น (currentSrc), **performance entries** (เจอ manifest `.m3u8` ที่ hls.js โหลดหลังกดเล่น, ไฟล์ mp4 ตรง) และ iframe player — จัดลำดับ candidate อัตโนมัติ (ไฟล์ตรง → HLS/DASH ผ่านเอนจิน yt-dlp → iframe) ลองทีละตัวจนสำเร็จ
- **ระบบไฟล์ log อย่างละเอียดเพื่อวิเคราะห์/ดีบัก** — `%APPDATA%/video-downloader/logs/vdl.log` (หมุนเวียน 1 MB × 5 ไฟล์, UTF-8): หัวเซสชัน (เวอร์ชัน/OS/Python/ffmpeg/yt-dlp), ข้อความภายในของ yt-dlp ทั้งหมด (YtDlpLogger), ทุกขั้นตอนของโหมดสำรอง (fetch/Content-Type/manifest/iframe), การสแกนหน้าเว็บในเบราว์เซอร์พร้อมรายการ candidate, และ traceback ครบทุกความผิดพลาด — เปิดโฟลเดอร์จากเมนู **ช่วยเหลือ → เปิดโฟลเดอร์ log…**; โปรเซสเบราว์เซอร์เขียนแยกไฟล์ `vdl-browser.log` (กันชนกันตอน rotate)
- **โหมดสำรองจับสื่อได้กว้างขึ้น — รองรับเว็บได้มากกว่าเดิม**:
  - **iframe player ภายนอก** — หน้าที่ฝังวีดีโอผ่าน player ภายนอก (เช่น WordPress) จะตามเข้าไปหน้า player (ลึก 1 ระดับ, สูงสุด 5 iframe) แล้วดึงสื่อจากในนั้นต่อ
  - **สตรีม HLS/DASH** (.m3u8/.mpd) ที่มักซ่อนในสคริปต์ของ player — จับได้และส่งต่อให้เอนจิน yt-dlp ดาวน์โหลดเอง (ใช้คุณภาพ/จำกัดความเร็ว/MP3 ที่ตั้งไว้ด้วย)
  - **lazy-load** — attribute `data-src` / `data-video-src` / `data-mp4` / `data-hls` ฯลฯ
  - **สื่อที่ฝังใน JSON/สคริปต์** — player config, JSON-LD `contentUrl`, `__NEXT_DATA__` (รวมแบบ escape `\/` และ `\u0026`)
  - **ลิงก์ endpoint ไม่มีนามสกุล** (เช่น `/getvideo?id=1`) — ตรวจจาก Content-Type แล้วสตรีม พร้อมตั้งนามสกุลไฟล์ให้อัตโนมัติ
  - **meta เพิ่ม**: `twitter:player:stream`
- **ส่ง Referer ของหน้าต้นทาง** ตอนโหลดสื่อ **และตอนส่ง manifest/iframe ให้เอนจิน yt-dlp** — ผ่าน CDN ที่ตรวจ hotlink ได้มากขึ้น
- **อ่านหน้าเว็บตาม charset จริง** (จาก Content-Type / `<meta charset>`) — รองรับเว็บไทย windows-874
- **วางข้อความปน URL ได้** — แตกลิงก์ออกจากข้อความแชร์/ย่อหน้าอัตโนมัติ (`www.` เติม https ให้)
- ข้าม `blob:`/`data:` URL (MediaSource) อย่างชัดเจน — ไม่เซฟไฟล์เพี้ยน
- ชุดทดสอบ 16 → **61 เคส** — เพิ่ม fixture จำลองเว็บจริง (iframe + lazy-load + HLS + JSON), เทสต์ localhost server แบบออฟไลน์, เทสต์ระบบ log และการจัดลำดับ candidate ของเบราว์เซอร์

## [1.2.0] — 2026-09-28

### Added (เพิ่มใหม่)
- **เดสก์ท็อป: จำค่าการตั้งค่า** — โฟลเดอร์/คุณภาพ/ความเร็ว/ภาษา/ขนาดหน้าต่าง ถูกบันทึกอัตโนมัติลง `%APPDATA%/video-downloader/config.json` (พร้อม migration ค่าเก่า)
- **เดสก์ท็อป: แถบความคืบหน้าต่อรายการ** — แถบตัวอักษร ▓ ในตารางแยกต่อแถว ไม่ต้องเดาจากแถบรวม
- **เดสก์ท็อป: รองรับคุกกี้เบราว์เซอร์** (Chrome/Firefox/Edge/Brave/ฯลฯ) สำหรับคอนเทนต์ที่ต้องล็อกอิน และตัวเลือก **โหลดทั้งเพลย์ลิสต์**
- **เดสก์ท็อป: เช็คอัปเดตอัตโนมัติ** — ตรวจ release ใหม่ตอนเปิดโปรแกรม แสดงแบนเนอร์คลิกไปดาวน์โหลด (มีเมนูตรวจเองด้วย)
- **เดสก์ท็อป: สลับภาษาไทย/อังกฤษ** จากเมนู — ครบทุก label รวมตัวเลือกคุณภาพ
- **Android: เลือกบริการอัตโนมัติ** — YouTube / SoundCloud / Bandcamp ตามโดเมนลิงก์ พร้อมตัวเลือก **เสียงเท่านั้น** (kbps)
- **Android: R8 minify + shrinkResources** — APK ลดจาก 5.9 MB → ~2.2 MB
- **Android: ภาษาอังกฤษ** (values-en) ตามภาษาระบบ
- **CI: workflow Tests** — รันชุดทดสอบ + ruff ทุก push/PR ก่อนขึ้น release
- **เว็บ: `docs/data/latest.json`** — release workflow เขียนข้อมูลไฟล์+checksum กลับเข้า repo หน้าเว็บอ่านแบบ same-origin ไม่ติด GitHub API rate limit อีก
- **หลักฐานที่มาไฟล์ (build provenance)** — ทั้ง EXE และ APK generate artifact attestation ผ่าน GitHub (`gh attestation verify`)
- **สคริปต์ `scripts/bump.py`** — เปลี่ยนเวอร์ชันทุกจุด (main.py / version_info / build.gradle / CHANGELOG) จากคำสั่งเดียว

### Changed (เปลี่ยนแปลง)
- Release body ฝั่ง Android แนบ SHA256 ของ APK ใน release notes ให้หน้าเว็บแสดงได้

## [1.1.0] — 2026-09-28

### Added (เพิ่มใหม่)
- **แอป Android** (Kotlin + NewPipeExtractor) — APK ติดตั้งได้ รับลิงก์แชร์ เลือกคุณภาพ ดาวน์โหลดลง Downloads พร้อม notification และ progress
- **โหมดสำรอง (fallback download)** — เมื่อ yt-dlp ดึงวีดีโอไม่สำเร็จ แอปจะสลับไปแยกลิงก์สื่อจากหน้า HTML โดยอัตโนมัติ: รองรับไฟล์ `.html` ในเครื่อง (คัดลอกสื่อในเครื่องหรือดาวน์โหลดสื่อระยะไกลที่อ้างถึง), ลิงก์ไฟล์สื่อตรง (mp4/mp3/ฯลฯ) และการดึงหน้าเว็บเพื่อหา `<video>/<source>/<a>/og:video` — สตรีมดาวน์โหลดพร้อม progress และปุ่มยกเลิกใช้งานได้เหมือนเดิม
- โมดูล `html_media.py` + หน้าทดสอบ `tests/test.html` (วิดีโอตัวอย่างสาธารณะ CC) และชุดทดสอบอัตโนมัติ `tests/run_tests.py` (16 เคส ผ่านทั้งหมด)
- สถานะใหม่ในตาราง: "ลองโหมดสำรอง…" และ "สำเร็จ (สำรอง) ✓"
- CI build signed APK บน tag `v*` + หน้าเว็บแสดงปุ่มดาวน์โหลด Android

## [1.0.0] — 2026-09-28

### Added (เพิ่มใหม่)
- แอป GUI (tkinter) สำหรับดาวน์โหลดวีดีโอจากเว็บไซต์สาธารณะด้วยเอนจิน yt-dlp
- รองรับหลายลิงก์พร้อมกัน (คิวดาวน์โหลด) พร้อมตารางแสดงสถานะรายการ
- เลือกคุณภาพ: ดีที่สุด (mp4) / 1080p / 720p / 480p / แยกเสียงเป็น MP3
- แถบความคืบหน้า + เปอร์เซ็นต์ + ความเร็ว + เวลาที่เหลือ แบบเรียลไทม์
- ปุ่มยกเลิกทั้งหมด — หยุดงานกลางคันได้อย่างปลอดภัย (ผ่าน progress hook)
- จำกัดความเร็วดาวน์โหลด: 1 / 5 / 10 MB/s หรือไม่จำกัด
- bundle ffmpeg ผ่าน imageio-ffmpeg — รวมไฟล์วีดีโอ+เสียงและแปลง MP3 ได้ทันที ไม่ต้องติดตั้งเพิ่ม
- แพ็กเป็น EXE ไฟล์เดียวด้วย PyInstaller (onefile, windowed) พร้อมไอคอนและ version resource
- คู่มือ AGENT.md สำหรับผู้ร่วมพัฒนา/AI agent
- เอกสาร README / RESEARCH / CHANGELOG ในรูปแบบ Markdown และ HTML
- หน้าเว็บดาวน์โหลดบน GitHub Pages — ดึง release ล่าสุดจาก GitHub API อัตโนมัติ พร้อมปุ่มดาวน์โหลดและ SHA256 checksum
- GitHub Actions: build EXE และสร้าง release อัตโนมัติเมื่อ push tag `v*` + deploy Pages

### Technical (รายละเอียดเทคนิค)
- Python 3.14 / tkinter — สื่อสารระหว่างเธรดด้วย `queue.Queue` + `root.after()`
- yt-dlp 2026.08.19 — format selector บังคับ mp4, `ratelimit`, `concurrent_fragment_downloads`
- ffmpeg-win-x86_64 v7.1 (~25 MB) bundle ใน EXE
- ขนาด EXE ~82.5 MB, smoke test ผ่าน (เปิดโปรแกรม 6 วินาทีไม่ crash)
