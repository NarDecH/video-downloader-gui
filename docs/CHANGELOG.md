# Changelog

รูปแบบอ้างอิง [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) และใช้ [Semantic Versioning](https://semver.org/)

## [Unreleased]

### Added (เพิ่มใหม่)
- **โหมดสำรอง (fallback download)** — เมื่อ yt-dlp ดึงวีดีโอไม่สำเร็จ แอปจะสลับไปแยกลิงก์สื่อจากหน้า HTML โดยอัตโนมัติ: รองรับไฟล์ `.html` ในเครื่อง (คัดลอกสื่อในเครื่องหรือดาวน์โหลดสื่อระยะไกลที่อ้างถึง), ลิงก์ไฟล์สื่อตรง (mp4/mp3/ฯลฯ) และการดึงหน้าเว็บเพื่อหา `<video>/<source>/<a>/og:video` — สตรีมดาวน์โหลดพร้อม progress และปุ่มยกเลิกใช้งานได้เหมือนเดิม
- โมดูล `html_media.py` + หน้าทดสอบ `tests/test.html` (วิดีโอตัวอย่างสาธารณะ CC) และชุดทดสอบอัตโนมัติ `tests/run_tests.py` (16 เคส ผ่านทั้งหมด)
- สถานะใหม่ในตาราง: "ลองโหมดสำรอง…" และ "สำเร็จ (สำรอง) ✓"

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
