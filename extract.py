#!/usr/bin/env python3
"""Extract MPH and RPM from the NASCAR driver-cam HUD in every frame.

Cheap-and-cheerful approach: grayscale-threshold each fixed crop, OCR with
tesseract (digits only), then clean up using the known valid ranges
(MPH 0-220, RPM 0-10000). We keep the raw OCR string alongside the cleaned
value so bad reads can be eyeballed / hand-corrected later.
"""
import csv
import glob
import os
import re
from concurrent.futures import ThreadPoolExecutor

import pytesseract
from PIL import Image

# Fixed HUD crop boxes (left, top, right, bottom) in the 1920x1080 frame.
# The overlay never moves, so these are constant across all clips/frames.
MPH_BOX = (526, 170, 600, 206)
RPM_BOX = (642, 170, 720, 206)

MPH_MIN, MPH_MAX = 0, 220
RPM_MIN, RPM_MAX = 0, 10000

# Excursion-detection thresholds: a plateau that jumps away from BOTH
# neighbours by more than this (in the SAME direction) is a misread spike, not
# a real change. Real deceleration is a monotonic staircase whose steps are
# opposite-signed w.r.t. their neighbours, so it is never flagged regardless of
# threshold -- which lets us set these low enough to catch small misreads in
# the low-RPM post-collision idle regime (e.g. 74 among ~786).
MPH_THR = 15
RPM_THR = 600

FPS = 30.0
SCALE = 8
TESS_CFG = "--psm 8 -c tessedit_char_whitelist=0123456789"


def ocr_number(im, box):
    """Upscale a grayscale crop and OCR it. Returns the raw digit string.

    We deliberately do NOT hard-threshold: a fixed binary threshold thickens
    the stylised italic strokes and fills the loops of an '8', which tesseract
    then reads as '9' (or '3'). Feeding grayscale and letting tesseract do its
    own adaptive binarisation reads the broadcast font correctly."""
    c = im.crop(box).convert("L")
    img = c.resize((c.width * SCALE, c.height * SCALE), Image.LANCZOS)
    raw = pytesseract.image_to_string(img, config=TESS_CFG)
    return re.sub(r"\D", "", raw)


def _median(xs):
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def resolve_reads(raws, lo, hi, window=7):
    """Turn raw OCR strings into best-guess integers, repairing phantom-digit
    reads instead of discarding them so real per-frame gradation is preserved.

    The common failure is a spurious digit -- the gauge arc bleeds a leading
    '1' ('1158' -> 158) or a trailing zero sneaks in ('1220' -> 122). When a
    read is out of range (or 4+ digits), we generate every candidate formed by
    deleting one digit, keep the in-range ones, and pick whichever is closest
    to the local median of the trusted in-range reads. This recovers the exact
    value and, crucially, keeps the out-of-range junk out of the neighbour
    statistics the outlier detectors rely on. Unrecoverable reads become None."""
    n = len(raws)
    ints = [int(s) if s else None for s in raws]
    trusted = [v if (v is not None and lo <= v <= hi and len(raws[i]) <= len(str(hi)))
               else None for i, v in enumerate(ints)]
    out = list(trusted)
    for i, s in enumerate(raws):
        if trusted[i] is not None:
            continue
        cands = set()
        if s:
            for k in range(len(s)):
                t = s[:k] + s[k + 1:]
                if t and lo <= int(t) <= hi:
                    cands.add(int(t))
            if lo <= int(s) <= hi:
                cands.add(int(s))
        if not cands:
            out[i] = None
            continue
        nb = [trusted[j] for j in range(max(0, i - window), min(n, i + window + 1))
              if trusted[j] is not None]
        out[i] = min(cands, key=lambda c: abs(c - _median(nb))) if nb else None
    return out


def _segments(vals):
    """Compress a series into runs of consecutive-equal values (None groups
    with None). Returns list of [value, start_idx, end_idx_inclusive]."""
    segs = []
    i = 0
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        segs.append([vals[i], i, j])
        i = j + 1
    return segs


def find_outliers(vals, thr):
    """Flag frames whose plateau is an excursion spike (a misread), leaving
    real monotonic staircases (e.g. a collision's RPM decay) untouched.

    A plateau is a spike if it differs from BOTH its nearest non-None
    neighbouring plateaus by more than `thr` in the SAME direction. A genuine
    step down sits between its neighbours (opposite signs) and is kept. None
    reads are always flagged for interpolation."""
    segs = _segments(vals)
    flagged = set()
    for k, (v, s, e) in enumerate(segs):
        if v is None:
            flagged.update(range(s, e + 1))
            continue
        pv = next((segs[p][0] for p in range(k - 1, -1, -1)
                   if segs[p][0] is not None), None)
        nv = next((segs[p][0] for p in range(k + 1, len(segs))
                   if segs[p][0] is not None), None)
        if pv is not None and nv is not None:
            spike = abs(v - pv) > thr and abs(v - nv) > thr and (v - pv) * (v - nv) > 0
        elif pv is not None:            # last plateau: edge spike
            spike = abs(v - pv) > thr
        elif nv is not None:            # first plateau: edge spike
            spike = abs(v - nv) > thr
        else:
            spike = False               # whole series is one value
        if spike:
            flagged.update(range(s, e + 1))
    return flagged


def find_cluster_outliers(vals, thr, w=10, max_iter=6):
    """Second-line detector for clusters of misreads that shield each other
    from the segment detector (e.g. 8079,1,91,1,911,8105 or a run of 8099->099
    dropped-digit reads).

    Compares each frame to the median of the window on its left and on its
    right separately. A misread departs from the stable surroundings on both
    sides in the SAME direction; a real monotonic step sits between its two
    one-sided medians (opposite signs) and is kept -- so the clip7 collision
    decay is never flagged, regardless of threshold or iteration count.

    Iterates with removal: once the frames it can see are flagged, they are
    excluded from the medians and it runs again, progressively peeling a large
    junk cluster whose own members would otherwise poison the neighbour median
    (esp. near a clip boundary where one side has little clean context)."""
    n = len(vals)
    flagged = {i for i in range(n) if vals[i] is None}
    for _ in range(max_iter):
        added = False
        for i in range(n):
            if i in flagged:
                continue
            left = [vals[j] for j in range(max(0, i - w), i)
                    if vals[j] is not None and j not in flagged]
            right = [vals[j] for j in range(i + 1, min(n, i + w + 1))
                     if vals[j] is not None and j not in flagged]
            if not left or not right:
                continue
            lm, rm, v = _median(left), _median(right), vals[i]
            if abs(v - lm) > thr and abs(v - rm) > thr and (v - lm) * (v - rm) > 0:
                flagged.add(i)
                added = True
        if not added:
            break
    return flagged


def interpolate(vals, flagged):
    """Replace flagged (or None) frames by linear interpolation between the
    nearest kept values; extend the ends with the nearest kept value."""
    out = list(vals)
    keep = [i for i in range(len(vals)) if i not in flagged and vals[i] is not None]
    if not keep:
        return out
    for i in range(len(out)):
        if i in flagged or out[i] is None:
            out[i] = None
    for i in range(keep[0]):
        out[i] = vals[keep[0]]
    for i in range(keep[-1] + 1, len(out)):
        out[i] = vals[keep[-1]]
    for a, b in zip(keep, keep[1:]):
        if b - a > 1:
            for i in range(a + 1, b):
                f = (i - a) / (b - a)
                out[i] = round(vals[a] + f * (vals[b] - vals[a]))
    return out


def process_frame(path):
    im = Image.open(path)
    mph_raw = ocr_number(im, MPH_BOX)
    rpm_raw = ocr_number(im, RPM_BOX)
    return {
        "file": os.path.basename(path),
        "mph_raw": mph_raw,
        "rpm_raw": rpm_raw,
    }


def process_clip(clip_dir, out_csv):
    frames = sorted(glob.glob(os.path.join(clip_dir, "*.png")))
    with ThreadPoolExecutor(max_workers=8) as ex:
        rows = list(ex.map(process_frame, frames))

    # Stage 1: repair phantom-digit reads (recovers exact values, de-poisons
    # the neighbour statistics). Stage 2: flag anything still anomalous with two
    # detectors -- segment-excursion (spikes and long uniform misread runs) and
    # cluster-median (short runs of differing misreads that shield each other).
    # Real in-range monotonic motion (incl. the clip7 collision) survives both.
    mph_v = resolve_reads([r["mph_raw"] for r in rows], MPH_MIN, MPH_MAX)
    rpm_v = resolve_reads([r["rpm_raw"] for r in rows], RPM_MIN, RPM_MAX)
    mph_bad = find_outliers(mph_v, MPH_THR) | find_cluster_outliers(mph_v, MPH_THR)
    rpm_bad = find_outliers(rpm_v, RPM_THR) | find_cluster_outliers(rpm_v, RPM_THR)
    mph_i = interpolate(mph_v, mph_bad)
    rpm_i = interpolate(rpm_v, rpm_bad)

    def changed(raw, final):
        return raw == "" or final is None or int(raw) != final

    mph_c = rpm_c = 0
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["frame", "time_seconds", "mph", "rpm",
                    "mph_raw", "rpm_raw", "mph_corrected", "rpm_corrected"])
        for i, r in enumerate(rows):
            mc = changed(r["mph_raw"], mph_i[i])
            rc = changed(r["rpm_raw"], rpm_i[i])
            mph_c += mc
            rpm_c += rc
            w.writerow([i + 1, round(i / FPS, 3),
                        mph_i[i], rpm_i[i],
                        r["mph_raw"], r["rpm_raw"],
                        "yes" if mc else "", "yes" if rc else ""])
    print(f"{clip_dir}: {len(rows)} frames, "
          f"{mph_c} mph + {rpm_c} rpm corrected -> {out_csv}")
    return list(zip([i / FPS for i in range(len(rows))], mph_i, rpm_i))


def main():
    clips = sorted(glob.glob("clip*_frames"))
    for cd in clips:
        n = re.search(r"clip(\d+)", cd).group(1)
        process_clip(cd, f"clip{n}_telemetry.csv")


if __name__ == "__main__":
    main()
