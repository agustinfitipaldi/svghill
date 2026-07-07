#!/usr/bin/env python3
"""Raw MPH/RPM OCR for the two-driver (hill, svg) recordings. NO cleaning:
whatever tesseract reads is what lands in the CSV, so the charts show the
unvarnished truth and we can decide what repair (if any) is worth it.

Output: telemetry/<driver>/<lap>.csv  columns: frame,time_seconds,mph,rpm
A blank mph/rpm cell means tesseract returned no digits for that box.

Crop boxes come from boxcheck.py so there is one source of truth for them.
"""
import csv
import glob
import os
import re
import sys
from concurrent.futures import ThreadPoolExecutor

import pytesseract
from PIL import Image, ImageOps

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from boxcheck import BOXES  # {driver: {"mph": box, "rpm": box}}

FPS = 30.0
SCALE = 8
BORDER = 20   # black quiet-zone padding (in the upscaled crop) -- see ocr_number
# --psm 7 = "single text line". --psm 8 ("single word") mis-segments this
# broadcast font badly: it collapses 180 -> 1 or hallucinates a phantom digit
# (180 -> 1380, 7808 -> 78908). psm 7 + a quiet-zone border reads it cleanly.
TESS_CFG = "--psm 7 -c tessedit_char_whitelist=0123456789"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES_DIR = os.path.join(ROOT, "frames")
TELEMETRY_DIR = os.path.join(ROOT, "telemetry")


def ocr_number(im, box):
    """Upscale a grayscale crop and OCR it; return the raw digit string.

    Deliberately no hard threshold -- feeding grayscale lets tesseract do its
    own adaptive binarisation, which reads the stylised broadcast font better
    than a fixed cutoff (a cutoff thickens the italic strokes and fills the
    loops of an 8)."""
    c = im.crop(box).convert("L")
    img = c.resize((c.width * SCALE, c.height * SCALE), Image.LANCZOS)
    # Tesseract was trained on text with whitespace around it; a crop where the
    # digits touch the edge makes it drop or hallucinate a glyph at the margin.
    img = ImageOps.expand(img, border=BORDER, fill=0)
    raw = pytesseract.image_to_string(img, config=TESS_CFG)
    return re.sub(r"\D", "", raw)


def process_frame(args):
    path, driver = args
    im = Image.open(path)
    return {
        "frame": int(re.search(r"frame_(\d+)", os.path.basename(path)).group(1)),
        "mph": ocr_number(im, BOXES[driver]["mph"]),
        "rpm": ocr_number(im, BOXES[driver]["rpm"]),
    }


def process_lap(driver, lap_dir, out_csv):
    lap = os.path.basename(lap_dir)
    frames = sorted(glob.glob(os.path.join(lap_dir, "*.png")))
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(process_frame, [(p, driver) for p in frames]))
    rows.sort(key=lambda r: r["frame"])
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "time_seconds", "mph", "rpm"])
        for r in rows:
            w.writerow([r["frame"], round((r["frame"] - 1) / FPS, 3),
                        r["mph"], r["rpm"]])
    miss = sum(1 for r in rows if not r["mph"] or not r["rpm"])
    print(f"{driver}/{lap}: {len(rows)} frames, {miss} with a missing read -> {out_csv}")


def main():
    # args: driver names (hill/svg) and/or lap filters (lapNN). Anything
    # matching lap\d+ restricts which laps run; the rest select drivers.
    args = sys.argv[1:]
    lap_filter = {a for a in args if re.fullmatch(r"lap\d+", a)}
    drivers = [a for a in args if a not in lap_filter] or ["hill", "svg"]
    for driver in drivers:
        out_dir = os.path.join(TELEMETRY_DIR, driver)
        os.makedirs(out_dir, exist_ok=True)
        laps = sorted(glob.glob(os.path.join(FRAMES_DIR, driver, "lap*")))
        for lap_dir in laps:
            lap = os.path.basename(lap_dir)
            if lap_filter and lap not in lap_filter:
                continue
            process_lap(driver, lap_dir, os.path.join(out_dir, f"{lap}.csv"))


if __name__ == "__main__":
    main()
