#!/usr/bin/env python3
"""Eyeball HUD crop boxes. Edit BOXES, run, look in boxcheck/.

    python3 scripts/boxcheck.py                  # hill lap41 frame 1
    python3 scripts/boxcheck.py svg lap41 1      # svg   lap41 frame 1
    python3 scripts/boxcheck.py hill lap47 299   # hill  low-speed frame

Outputs per run (in boxcheck/):
  strip_<driver>.png   wide context with every box for that driver drawn on it
  box_<field>.png      each box cropped and scaled 8x so you can see the margin
"""
import os
import sys
from PIL import Image, ImageDraw

# (left, top, right, bottom) per driver+field. Tweak these.
BOXES = {
    "hill": {"mph": (466, 84, 520, 110), "rpm": (588, 80, 672, 116)},
    "svg":  {"mph": (620, 80, 675, 116), "rpm": (745, 80, 820, 116)},
}

# wide strip drawn around the whole readout, per driver
STRIP = {"hill": (400, 55, 720, 150), "svg": (560, 55, 880, 150)}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "boxcheck")


def main():
    driver = sys.argv[1] if len(sys.argv) > 1 else "hill"
    lap = sys.argv[2] if len(sys.argv) > 2 else "lap41"
    frame = int(sys.argv[3]) if len(sys.argv) > 3 else 1
    os.makedirs(OUT, exist_ok=True)

    path = os.path.join(ROOT, "frames", driver, lap, f"frame_{frame:04d}.png")
    im = Image.open(path).convert("RGB")
    print(f"{driver} {lap} frame_{frame:04d}")

    # each box cropped + zoomed 8x
    for field, box in BOXES[driver].items():
        c = im.crop(box)
        c = c.resize((c.width * 8, c.height * 8), Image.LANCZOS)
        c.save(os.path.join(OUT, f"box_{driver}_{field}.png"))
        print(f"  {field}: {box}")

    # wide strip with all boxes outlined (green), zoomed 4x
    reg = STRIP[driver]
    Z = 4
    strip = im.crop(reg).resize(((reg[2]-reg[0])*Z, (reg[3]-reg[1])*Z), Image.LANCZOS)
    d = ImageDraw.Draw(strip)
    for box in BOXES[driver].values():
        d.rectangle([(box[0]-reg[0])*Z, (box[1]-reg[1])*Z,
                     (box[2]-reg[0])*Z-1, (box[3]-reg[1])*Z-1],
                    outline=(60, 255, 60), width=2)
    strip.save(os.path.join(OUT, f"strip_{driver}.png"))
    print(f"  -> {OUT}/")


if __name__ == "__main__":
    main()
