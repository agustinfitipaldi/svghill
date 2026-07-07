#!/usr/bin/env python3
"""Redact the browser toolbar (top strip) from every extracted frame.

The frames are full-screen OBS captures, so the top ~42px is the Chrome
address bar showing the HBO Max URL with its session UUIDs. This paints a
black rectangle over the top REDACT_H pixels of every clip*_frames/*.png,
in place, before the frames get pushed to a public repo.

REDACT_H (60) sits well below the toolbar (~42px) and well above where the
video picture begins (~110px) and the OCR crop region (y=170+), so the HUD is
untouched and extract.py keeps working. Running it again is harmless.
"""
import glob
import os
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw

REDACT_H = 60


def redact(path):
    im = Image.open(path)
    ImageDraw.Draw(im).rectangle([0, 0, im.width, REDACT_H], fill="black")
    im.save(path)


def main():
    frames = sorted(glob.glob(os.path.join("clip*_frames", "*.png")))
    print(f"Redacting top {REDACT_H}px of {len(frames)} frames...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        list(ex.map(redact, frames))
    print("Done.")


if __name__ == "__main__":
    main()
