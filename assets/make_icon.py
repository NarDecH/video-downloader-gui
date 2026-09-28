#!/usr/bin/env python3
"""Generate assets/icon.ico (16,32,48,64,128,256 px) from a 1024x1024 master PNG."""
from PIL import Image, ImageDraw
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "icon.ico")
MASTER = os.path.join(HERE, "icon_master.png")

sizes = [16, 32, 48, 64, 128, 256]

img = Image.open(MASTER).convert("RGBA")
img.save(OUT, format="ICO", sizes=[(s, s) for s in sizes])
print("wrote", OUT, os.path.getsize(OUT), "bytes")
