# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Video Downloader GUI (Windows, onefile, windowed)."""
import os

import imageio_ffmpeg

block_cipher = None
HERE = os.path.abspath(SPECPATH)

ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

# Bundle the in-app browser engine (pywebview + WebView2 loader) when installed.
# Guarded so the build still works without it (browser feature degrades gracefully).
browser_datas: list = []
browser_binaries: list = []
browser_hidden: list = []
try:
    from PyInstaller.utils.hooks import collect_all

    for _pkg in ("webview", "clr_loader", "pythonnet"):
        try:
            _d, _b, _h = collect_all(_pkg)
        except Exception:  # noqa: BLE001 — package not installed
            continue
        browser_datas += _d
        browser_binaries += _b
        browser_hidden += _h
except ImportError:
    pass

a = Analysis(
    ["main.py"],
    pathex=[HERE],
    binaries=[(ffmpeg_bin, ".")] + browser_binaries,
    datas=[(os.path.join(HERE, "assets", "icon.ico"), "assets")] + browser_datas,
    hiddenimports=browser_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["matplotlib", "numpy", "pandas", "pytest"],
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="VideoDownloaderGUI",
    debug=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=False,
    icon=os.path.join(HERE, "assets", "icon.ico"),
    version=os.path.join(HERE, "version_info.txt"),
)
