# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for Video Downloader GUI (Windows, onefile, windowed)."""
import os

import imageio_ffmpeg

block_cipher = None
HERE = os.path.abspath(SPECPATH)

ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

a = Analysis(
    ["main.py"],
    pathex=[HERE],
    binaries=[(ffmpeg_bin, ".")],
    datas=[(os.path.join(HERE, "assets", "icon.ico"), "assets")],
    hiddenimports=[],
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
