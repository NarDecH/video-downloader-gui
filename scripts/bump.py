#!/usr/bin/env python3
"""Bump เวอร์ชันโปรเจกต์จากที่เดียว

ใช้: python scripts/bump.py 1.3.0
อัปเดต: main.py (APP_VERSION), version_info.txt, android/app/build.gradle.kts
        (versionCode +1 อัตโนมัติ, versionName), docs/CHANGELOG.* หัวข้อ Unreleased
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]

ROOT = Path(__file__).resolve().parent.parent


def sub_file(path: Path, pattern: str, repl: str, must: bool = True) -> None:
    text = path.read_text(encoding="utf-8")
    new, n = re.subn(pattern, repl, text, count=1)
    if must and n == 0:
        sys.exit(f"ERROR: pattern not found in {path}: {pattern}")
    path.write_text(new, encoding="utf-8")
    print(f"  ✓ {path.name}")


def main() -> None:
    if len(sys.argv) != 2 or not re.match(r"^\d+\.\d+\.\d+$", sys.argv[1]):
        print(__doc__)
        sys.exit("ระบุเวอร์ชันแบบ X.Y.Z เช่น: python scripts/bump.py 1.3.0")
    ver = sys.argv[1]
    parts = [int(x) for x in ver.split(".")]

    print(f"Bump เวอร์ชัน → {ver}")

    sub_file(ROOT / "main.py", r'APP_VERSION = "[\d.]+"', f'APP_VERSION = "{ver}"')
    sub_file(
        ROOT / "version_info.txt",
        r"filevers=\([\d, ]+\),\s*\n\s*prodvers=\([\d, ]+\)",
        f"filevers=({parts[0]}, {parts[1]}, {parts[2]}, 0),\n    prodvers=({parts[0]}, {parts[1]}, {parts[2]}, 0)",
    )
    sub_file(ROOT / "version_info.txt", r'StringStruct\("FileVersion", "[\d.]+"\)', f'StringStruct("FileVersion", "{ver}.0")')
    sub_file(ROOT / "version_info.txt", r'StringStruct\("ProductVersion", "[\d.]+"\)', f'StringStruct("ProductVersion", "{ver}.0")')

    gradle = ROOT / "android" / "app" / "build.gradle.kts"
    gtext = gradle.read_text(encoding="utf-8")
    m = re.search(r"versionCode = (\d+)", gtext)
    if not m:
        sys.exit("ERROR: versionCode not found")
    code = int(m.group(1)) + 1
    sub_file(gradle, r"versionCode = \d+", f"versionCode = {code}")
    sub_file(gradle, r'versionName = "[\d.]+"', f'versionName = "{ver}"')

    for name in ("docs/CHANGELOG.md", "docs/CHANGELOG.html"):
        p = ROOT / name
        if p.exists():
            text = p.read_text(encoding="utf-8")
            text = text.replace("## [Unreleased]", f"## [{ver}] — วันที่นี้ถูกตั้งตอน release")
            p.write_text(text, encoding="utf-8")
            print(f"  ✓ {p.name} (Unreleased → {ver})")

    print("\nเสร็จ — อย่าลืมเพิ่มรายการใหม่ใน CHANGELOG และรันเทสต์ก่อน tag")


if __name__ == "__main__":
    main()
