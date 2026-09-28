#!/usr/bin/env python3
"""Draw the 1024x1024 master icon PNG with Pillow (anti-aliased shapes)."""
from PIL import Image, ImageDraw, ImageFilter
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "icon_master.png")

S = 1024
img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

# Vertical gradient background
grad = Image.new("RGBA", (S, S), (0, 0, 0, 0))
gd = ImageDraw.Draw(grad)
for y in range(S):
    t = y / (S - 1)
    r = int(94 + t * (231 - 94))
    g = int(118 + t * (48 - 118))
    b = int(211 + t * (26 - 211))
    gd.line([(0, y), (S, y)], fill=(r, g, b, 255))

# Rounded-square mask
mask = Image.new("L", (S, S), 0)
md = ImageDraw.Draw(mask)
md.rounded_rectangle([64, 64, 960, 960], radius=200, fill=255)
img.paste(grad, (0, 0), mask)

# Play triangle with soft shadow
shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
sd = ImageDraw.Draw(shadow)
sd.polygon([(430, 300), (430, 724), (770, 512)], fill=(0, 0, 0, 90))
shadow = shadow.filter(ImageFilter.GaussianBlur(14))
img.alpha_composite(shadow)

d = ImageDraw.Draw(img)
d.polygon([(410, 290), (410, 734), (750, 512)], fill=(255, 255, 255, 255))

# Progress bar
d.rounded_rectangle([210, 790, 814, 830], radius=20, fill=(255, 255, 255, 110))
d.rounded_rectangle([210, 790, 560, 830], radius=20, fill=(255, 255, 255, 255))

img.save(OUT)
print("wrote", OUT, img.size)
