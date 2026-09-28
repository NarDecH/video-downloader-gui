# AGENT.md — คู่มือสำหรับ AI Agent / Developer

> โปรเจกต์: **Video Downloader GUI** — แอป GUI ดาวน์โหลดวีดีโอจากเว็บไซต์สาธารณะด้วย yt-dlp
> Repo: `https://github.com/NarDecH/video-downloader-gui`
> เว็บดาวน์โหลด: `https://nardech.github.io/video-downloader-gui/`

---

## 1. ภาพรวมโปรเจกต์

| องค์ประกอบ | เทคโนโลยี |
|---|---|
| UI | Python 3.13+ / 3.14 + tkinter (ttk) |
| ดาวน์โหลด | [yt-dlp](https://github.com/yt-dlp/yt-dlp) |
| ffmpeg | bundle ผ่าน [imageio-ffmpeg](https://pypi.org/project/imageio-ffmpeg/) (ไม่ต้องติดตั้งแยก) |
| แพ็ก EXE | [PyInstaller](https://pyinstaller.org/) onefile + windowed + icon |
| CI | GitHub Actions: build EXE อัตโนมัติเมื่อ tag `v*` |
| เว็บไซต์ | GitHub Pages — ดึง release ล่าสุดจาก GitHub API |

## 2. โครงสร้างไฟล์

```
.
├── main.py                    # แอป GUI หลัก (tkinter + yt-dlp + fallback + i18n + config + เบราว์เซอร์ในแอป)
├── html_media.py              # โหมดสำรอง: แยกสื่อจาก HTML (video/og:video, lazy-load data-*, JSON/สคริปต์, HLS/DASH, iframe player) / ไฟล์ .html ในเครื่อง / ลิงก์ตรง + probe จาก Content-Type (สตรีมพร้อม progress)
├── logger.py                  # ระบบ log หมุนเวียน (logs/vdl.log 1MB×5) + YtDlpLogger adapter + session header
├── browser_app.py             # โปรเซสเบราว์เซอร์ในแอป (pywebview/WebView2 บน MainThread ของโปรเซส + IPC TCP 127.0.0.1)
├── scripts/bump.py            # bump เวอร์ชันทุกจุดจากคำสั่งเดียว: python scripts/bump.py X.Y.Z
├── tests/
│   ├── test.html              # หน้าทดสอบ (วิดีโอตัวอย่างสาธารณะ CC จาก test-videos.co.uk) 4 รูปแบบการฝัง
│   ├── test_embed.html        # fixture offline: lazy-load + iframe player + JSON/สคริปต์ + HLS
│   └── run_tests.py           # ชุดทดสอบอัตโนมัติ 40 เคส (รัน: python tests/run_tests.py)
├── VideoDownloaderGUI.spec    # สเปก PyInstaller (onefile, icon, bundle ffmpeg)
├── version_info.txt           # Windows version resource ของ EXE
├── requirements.txt           # dependencies
├── assets/
│   ├── icon_master.py         # สคริปต์วาดไอคอนต้นฉบับ 1024px
│   ├── icon_master.png        # ไฟล์ไอคอนต้นฉบับ
│   ├── make_icon.py           # สร้าง icon.ico หลายขนาดจาก master
│   ├── icon.ico               # ไอคอนแอป (16–256px)
│   └── make_docs_images.py    # สร้างภาพประกอบใน docs/img
├── docs/
│   ├── index.html             # หน้าเว็บดาวน์โหลด (GitHub Pages)
│   ├── README.md / .html
│   ├── RESEARCH.md / .html
│   ├── CHANGELOG.md / .html
│   └── img/                   # banner.png, screenshot.png
└── .github/workflows/
    ├── release.yml            # build EXE + สร้าง release เมื่อ tag v*
    └── pages.yml              # deploy docs/index.html ขึ้น Pages
```

## 3. คำสั่งที่ใช้บ่อย

```bash
# ติดตั้ง dependencies (แนะนำใช้ venv)
python -m pip install -r requirements.txt

# รันแอปจากซอร์ส
python main.py

# สร้างไอคอนใหม่ (หลังแก้ icon_master.py)
python assets/icon_master.py && python assets/make_icon.py

# สร้างภาพประกอบเอกสารใหม่
python assets/make_docs_images.py

# แพ็ก EXE
python -m PyInstaller --clean --noconfirm VideoDownloaderGUI.spec
# ผลลัพธ์: dist/VideoDownloaderGUI.exe

# ทดสอบชุดโหมดสำรอง + GUI smoke test
python tests/run_tests.py

# ตรวจไวยากรณ์
python -m py_compile main.py html_media.py
```

## 4. ข้อตกลงและแนวปฏิบัติ

- **ภาษา UI**: ภาษาไทยทั้งหมดในส่วนติดต่อผู้ใช้; โค้ด/คอมเมนต์/ชื่อตัวแปรเป็นภาษาอังกฤษ
- **Threading**: ห้ามสั่งงาน tkinter จากเธรด worker — สื่อสารผ่าน `queue.Queue` และ `root.after()` เท่านั้น (ดู `HookBridge`, `App._poll_events`)
- **เบราว์เซอร์ในแอป**: pywebview บังคับ `webview.start()` บน MainThread ของโปรเซส จึงต้องรันเป็น**โปรเซสลูก** (EXE เรียกตัวเองซ้ำด้วย `--vdl-browser`, dev เรียก `browser_app.py`) และสั่งงานผ่าน TCP `127.0.0.1` (JSON หนึ่งบรรทัดต่อคำสั่ง: ping/url/navigate/scan/quit) — **ห้าม** import webview แล้ว start ในเธรดของแอปหลัก; `evaluate_js`/`load_url` ของ pywebview ปลอดภัยเมื่อเรียกจากเธรดอื่น (ใช้ Invoke ไป UI thread เอง)
- **การจับวีดีโอจากเบราว์เซอร์**: `JS_SCAN_MEDIA` อ่าน DOM (video.currentSrc/source/iframe) + `performance.getEntriesByType('resource')` — จุดนี้คือหัวใจ เพราะ manifest .m3u8 ที่ hls.js โหลดหลังกดเล่นจะปรากฏใน performance entries เท่านั้น; จัดลำดับใน `App.rank_browser_media` (เทสต์ offline ได้)
- **การยกเลิก**: ใช้ `stop_flag` (threading.Event) แล้ว raise `yt_dlp.utils.DownloadCancelled` ใน progress hook — ห้ามยิง signal ตรงจากเธรด UI
- **ffmpeg**: ตรวจจับลำดับ `imageio-ffmpeg` → ข้างๆ EXE → `_MEIPASS` → PATH; แสดง warning ใน UI ถ้าไม่พบ
- **เวอร์ชัน**: แก้ 3 จุดพร้อมกันเมื่อ bump เวอร์ชัน: `APP_VERSION` ใน `main.py`, `version_info.txt`, `docs/CHANGELOG.*`
- **โหมดสำรอง (fallback)**: ถ้า yt-dlp ล้มเหลว `App._fallback` จะเรียก `html_media.smart_download()` — ลำดับ: ไฟล์ .html ในเครื่อง → ลิงก์สื่อตรง → ดึงหน้าเว็บ (probe จาก Content-Type ถ้าไม่มีนามสกุล) → หาสื่อจาก `<video>/og:video/twitter:player:stream`, lazy-load (`data-*`), JSON/สคริปต์ → ลำดับถัดไปคือ manifest `.m3u8`/`.mpd` และ iframe player (ลึก 1 ระดับ, ≤5 iframe) ซึ่งส่งต่อให้ yt-dlp ผ่าน callback `strong_downloader` (`App._ydl_download`); โหลดสื่อจากหน้าจะแนบ Referer ของหน้าต้นทาง (รวมถึงตอนเรียก yt-dlp ผ่าน `http_headers` — yt-dlp merge กับ std_headers ให้เอง); ยกเลิกผ่าน `html_media.DownloadAborted` จาก stop_flag เดียวกัน
- **ขอบเขตการใช้งาน**: แอปนี้ไว้ดาวน์โหลดคอนเทนต์สาธารณะที่มีสิทธิ์ตามกฎหมาย/เงื่อนไขเว็บไซต์เท่านั้น — ไม่รับ feature ที่มุ่งเจาะจงเว็บผิดกฎหมายหรือละเมิดลิขสิทธิ์ และ**ไม่เขียน scraper เจาะจงเว็บที่เผยแพร่คอนเทนต์ส่วนบุคคลโดยไม่ได้รับความยินยอม (เช่น เว็บคลิปหลุด)** — ทดสอบด้วยวิดีโอตัวอย่างสาธารณะ (test-videos.co.uk) เท่านั้น ความสามารถของโหมดสำรองต้องเป็นกลาง/แบบ generic ไม่ hardcode โดเมนใด

## 5. การ release

1. `python scripts/bump.py X.Y.Z` (อัปเดต main.py, version_info.txt, build.gradle.kts, CHANGELOG อัตโนมัติ) และเพิ่มรายการใน `docs/CHANGELOG.md`
2. `git tag vX.Y.Z && git push origin vX.Y.Z`
3. GitHub Actions จะ build ทั้ง EXE (release.yml) และ APK แบบ signed (android.yml) พร้อม SHA256, artifact attestation และเขียน `docs/data/latest.json` กลับเข้า repo อัตโนมัติ
4. หน้าเว็บ Pages อ่าน `latest.json` แบบ same-origin (ไม่มี rate limit) — อัปเดตภายในไม่กี่นาที

## 6.1 แอป Android (android/)

- **เอนจิน**: NewPipeExtractor (YouTube/SoundCloud/Bandcamp) + **yt-dlp/ffmpeg จริงผ่าน youtubedl-android** (`io.github.junkfood02.youtubedl-android:library/ffmpeg:0.18.1` — แพ็ก Python+ffmpeg เป็น .so ต่อ ABI: arm64-v8a/armeabi-v7a/x86_64, APK ~156 MB)
- **ลำดับต่อลิงก์ใน MainActivity**: โดเมนรู้จัก → NewPipeExtractor (DownloadManager) → fallback เอนจิน yt-dlp (`YtDlpEngine.dumpJson` ให้เมทาดาทา/คุณภาพ) → fallback `PageScraper` แยกสื่อจากหน้าเว็บ → ลอง candidate ทีละตัวผ่านเอนจิน → ย้ายไฟล์เข้า Downloads ผ่าน MediaStore (Android 9 ลงไป: พาธตรง + ขอสิทธิ์ WRITE_EXTERNAL_STORAGE)
- **`YtDlpEngine.ensureInit`**: init ครั้งแรก (แตก Python ใช้เวลาสักครู่) + `updateYoutubeDL(STABLE)` อัตโนมัติ**ครั้งเดียวต่อการติดตั้ง** (จำใน SharedPreferences `engine_prefs` — เวอร์ชัน yt-dlp ที่แพ็กมากับไลบรารีเก่า ต้องอัปเดตถึงจะใช้กับเว็บปัจจุบันได้ดี)
- **`PageScraper`**: พอร์ตโหมดสำรองจาก html_media.py — เทสต์ JVM ที่ `app/src/test/java/com/nardech/videodownloader/PageScraperTest.kt` (รัน: `./gradlew testDebugUnitTest`)
- ห้าม hardcode โดเมนเว็บใดใน scraper — ต้องเป็น pattern กลางเหมือนฝั่งเดสก์ท็อป

## 6. การตั้งค่าผู้ใช้และ log (เดสก์ท็อป)

- บันทึกที่ `%APPDATA%/video-downloader/config.json` — โหลด/เซฟผ่าน `load_config()`/`save_config()` ใน main.py
- **Log**: `%APPDATA%/video-downloader/logs/vdl.log` (หมุนเวียน 1 MB × 5, DEBUG ทุกอย่าง) และ `vdl-browser.log` ของโปรเซสเบราว์เซอร์ — ตั้งค่าผ่าน `logger.setup_logging()`; แสดงคอนโซลเฉพาะตอนรันจากซอร์สหรือตั้ง `VDL_CONSOLE=1`; เปิดโฟลเดอร์จากเมนู ช่วยเหลือ → เปิดโฟลเดอร์ log…
- ค่า id ของคุณภาพ/ความเร็ว เป็นภาษากลาง (best/1080/720/480/mp3, unlimited/1m/5m/10m) — label แปลผ่าน `LANG` dict ตอนแสดงผล; ค่า legacy ภาษาไทยจะถูก migrate อัตโนมัติ

## 7. ข้อจำกัดที่ควรรู้

- EXE ขนาด ~80 MB เพราะ bundle Python + yt-dlp + ffmpeg (onefile จะแตกไฟล์ชั่วคราวตอนเปิด อาจช้า 2–5 วินาทีแรก); APK ~156 MB จาก Python/ffmpeg 3 ABI + เอนจินเริ่มใช้ครั้งแรกต้องแตกไฟล์และอัปเดต yt-dlp (ออนไลน์ครั้งแรก)
- yt-dlp เป็นแพ็กเกจที่ต้องอัปเดตบ่อยเมื่อเว็บไซต์เปลี่ยน — ถ้าดาวน์โหลดไม่ได้ ให้ลอง `pip install -U yt-dlp` หรือ build ใหม่
- บางเว็บ (เช่น Instagram/Facebook) อาจต้องใช้คุกกี้ล็อกอินสำหรับคอนเทนต์ที่ไม่สาธารณะ — ปัจจุบันแอปยังไม่รองรับการใส่คุกกี้ไฟล์ (มีแต่ดึงจากเบราว์เซอร์)
- โหมดสำรองอ่านเฉพาะ HTML ต้นฉบับ (static) — เว็บที่ inject สื่อด้วย JS ภายหลัง (XHR หลังหน้าเปิด) จับไม่ได้; สื่อแบบ blob: (MediaSource) ดาวน์โหลดตรงไม่ได้ แต่มักมี manifest .m3u8 ให้ yt-dlp จัดการแทน
- เบราว์เซอร์ในแอปต้องการ Microsoft Edge WebView2 Runtime (มีมาใน Win10/11 ส่วนใหญ่) — ถ้าไม่มี/ล้มเหลว แอปจะ fallback เปิดเบราว์เซอร์ระบบและแจ้งผู้ใช้; EXE จะใหญ่ขึ้นเพราะ bundle pywebview/WebView2 loader
- จับวีดีโอจากเบราว์เซอร์ใช้ได้เมื่อผู้ใช้**กดเล่นวีดีโอก่อน** (stream ถูกโหลดตอนกดเล่น จึงขึ้นใน performance entries) — หน้าที่วิดีโออยู่ใน iframe คนละโดเมน ระบบจะลอง yt-dlp กับ URL iframe เป็นตัวสำรอง
