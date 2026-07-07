"""Per-lap raw telemetry charts, one PNG per lap per driver. MPH on top
(blue), RPM below (red), shared time axis. Missing OCR reads leave gaps and
junk reads spike -- that is the point: the chart is how we eyeball errors.

    ./venv/bin/python scripts/plot_raw.py            # both drivers
    ./venv/bin/python scripts/plot_raw.py hill       # one driver
"""
import csv
import glob
import math
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MultipleLocator


def _signed(x, _pos=None):
    """X-tick formatter for collision-relative axes: 0 at collision, +/- around."""
    return "0" if abs(x) < 1e-9 else f"{x:+.0f}"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELEMETRY_DIR = os.path.join(ROOT, "telemetry")
CHARTS_DIR = os.path.join(ROOT, "charts")

MPH_COLOR = "#1f77b4"   # blue
RPM_COLOR = "#d62728"   # red
NAN = float("nan")

# Range filter: anything outside the plausible band is a misread -- blank it, no
# interpolation. Normal racing laps (41-46) use a tight green-flag band. lap47 is
# the crash lap, where RPM/MPH legitimately fall far below the green-flag floor
# (engine near-stall, car spinning), so it gets a wider low bound. Upper bounds
# stay put -- phantom high spikes are always junk. (lo_mph, hi_mph, lo_rpm, hi_rpm)
RANGE_DEFAULT = (130, 199, 5000, 8999)
RANGE_BY_LAP = {"lap47": (60, 199, 20, 8999)}

# Moment of the SVG/Hill collision, in seconds into each driver's lap47 clip.
# From new cuts.txt: (collision timestamp - lap47 clip start), each MM:SS:FF /60.
#   hill: 4:10:18 - 4:03:54 = 250.300 - 243.900 = 6.400 s
#   svg:  3:38:56 - 3:32:46 = 218.933 - 212.767 = 6.167 s
COLLISION = {"hill": 6.400, "svg": 6.167}

LAPS = [f"lap{n}" for n in range(41, 48)]
GREY = "#83888d"        # baseline laps 41-46 (15% darker than #9aa0a6)
# Crash lap (47) is drawn in each driver's colour so the two read apart on the omni.
DRIVER_COLOR = {"hill": "#ff8c00",   # orange
                "svg":  "#32cd32"}   # lime green
COLLISION_COLOR = "red"


def clean_series(vals, lo, hi):
    """Blank readings outside [lo, hi]. vals is a list of int-or-None; returns
    (same-length int-or-None list, dropped count)."""
    out = [None] * len(vals)
    dropped = 0
    for i, v in enumerate(vals):
        if v is None:
            continue
        if lo <= v <= hi:
            out[i] = v
        else:
            dropped += 1
    return out, dropped


def csv_for(driver, lap):
    """Resolve a lap to its telemetry CSV, preferring a hand-corrected
    `<lap>edited.csv` over the script-generated `<lap>.csv` when it exists. Lets
    manual fixes survive re-runs of ocr_raw.py, which only writes `<lap>.csv`."""
    edited = os.path.join(TELEMETRY_DIR, driver, f"{lap}edited.csv")
    return edited if os.path.exists(edited) else \
        os.path.join(TELEMETRY_DIR, driver, f"{lap}.csv")


def load(csv_path, lap):
    lo_m, hi_m, lo_r, hi_r = RANGE_BY_LAP.get(lap, RANGE_DEFAULT)
    t, mph, rpm = [], [], []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            t.append(float(r["time_seconds"]))
            mph.append(int(r["mph"]) if r["mph"] else None)
            rpm.append(int(r["rpm"]) if r["rpm"] else None)
    # A hand-corrected `edited` CSV is ground truth: take it verbatim, no range
    # filter. Only the raw OCR output gets the automatic gate.
    if csv_path.endswith("edited.csv"):
        md = rd = 0
    else:
        mph, md = clean_series(mph, lo_m, hi_m)
        rpm, rd = clean_series(rpm, lo_r, hi_r)
    mph = [v if v is not None else NAN for v in mph]
    rpm = [v if v is not None else NAN for v in rpm]
    return t, mph, rpm, md, rd


def plot_lap(csv_path, out_png, driver, lap):
    t, mph, rpm, md, rd = load(csv_path, lap)
    # lap47 gets a collision-relative x-axis (0 = collision); baseline laps have
    # no collision reference, so they stay in raw clip seconds.
    collided = lap == "lap47"
    off = COLLISION[driver] if collided else 0.0
    t = [x - off for x in t]

    fig, (ax_mph, ax_rpm) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True, gridspec_kw={"hspace": 0.12})

    # marker on every point so single-frame junk reads are visible, not hidden
    ax_mph.plot(t, mph, color=MPH_COLOR, lw=1.4, marker=".", ms=4)
    ax_mph.set_ylabel("MPH", color=MPH_COLOR, fontweight="bold")
    ax_mph.tick_params(axis="y", labelcolor=MPH_COLOR)

    ax_rpm.plot(t, rpm, color=RPM_COLOR, lw=1.4, marker=".", ms=4)
    ax_rpm.set_ylabel("RPM", color=RPM_COLOR, fontweight="bold")
    ax_rpm.tick_params(axis="y", labelcolor=RPM_COLOR)
    ax_rpm.set_xlabel("Seconds from collision" if collided else "Time (seconds)")

    for ax in (ax_mph, ax_rpm):
        ax.grid(True, alpha=0.25)
        ax.margins(x=0.01)
        ax.xaxis.set_major_locator(MultipleLocator(1))   # a tick every second
        if collided:
            ax.xaxis.set_major_formatter(_signed)

    if collided:
        for ax in (ax_mph, ax_rpm):
            ax.axvline(0, color=COLLISION_COLOR, lw=2, alpha=0.85, zorder=6)
        ax_mph.annotate("collision", xy=(0, ax_mph.get_ylim()[1]),
                        xytext=(4, -4), textcoords="offset points",
                        ha="left", va="top", color=COLLISION_COLOR,
                        fontsize=9, fontweight="bold")

    subtitle = ("edited (ground truth)" if csv_path.endswith("edited.csv")
                else f"range-filtered (dropped {md} mph, {rd} rpm)")
    ax_mph.set_title(f"{driver} — {lap} — {subtitle}", fontweight="bold")
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"{csv_path} -> {out_png}  (dropped {md} mph, {rd} rpm)")


def smooth(vals, win=15):
    """Centered moving average that irons the HUD's staircase plateaus into a
    readable curve. NaN-aware (skips gaps) and the window shrinks near the ends
    so the line still spans the full series."""
    n = len(vals)
    half = win // 2
    out = []
    for i in range(n):
        xs = [vals[j] for j in range(max(0, i - half), min(n, i + half + 1))
              if not math.isnan(vals[j])]
        out.append(sum(xs) / len(xs) if xs else NAN)
    return out


def _overlay_metric(ax, driver, which, smoothed=False, xlim=None):
    """Plot one driver's `which` ('mph'|'rpm') for all 7 laps onto `ax`, baseline
    laps 41-46 greyed and crash lap 47 pink, with time re-zeroed so 0 = collision.
    Draws the collision line at x=0. Every clip starts at the lap timing point, so
    subtracting the collision time aligns the collision across drivers (which is
    what lets the omni chart stack them). `smoothed` applies a moving average;
    `xlim` (in collision-relative seconds) zooms the time window."""
    c = COLLISION[driver]
    for lap in LAPS:
        csv_path = csv_for(driver, lap)
        if not os.path.exists(csv_path):
            continue
        t, mph, rpm, _, _ = load(csv_path, lap)
        t = [x - c for x in t]
        vals = mph if which == "mph" else rpm
        if smoothed:
            vals = smooth(vals)
        crash = lap == "lap47"
        ax.plot(t, vals, color=DRIVER_COLOR[driver] if crash else GREY,
                lw=2.4 if crash else 1.0, alpha=1.0 if crash else 0.5,
                zorder=5 if crash else 2)
    # When zoomed, rescale y to just the data visible in the window (otherwise the
    # off-screen crash tail leaves the panel mostly empty). Do this before drawing
    # the collision line so its blended-coord points don't skew the range.
    if xlim:
        lo, hi = xlim
        ys = [y for ln in ax.get_lines() for x, y in zip(ln.get_xdata(), ln.get_ydata())
              if lo <= x <= hi and not math.isnan(y)]
        if ys:
            pad = (max(ys) - min(ys)) * 0.05 or 1
            ax.set_ylim(min(ys) - pad, max(ys) + pad)
    ax.axvline(0, color=COLLISION_COLOR, lw=2, alpha=0.85, zorder=6)
    ax.grid(True, alpha=0.25)
    ax.xaxis.set_major_locator(MultipleLocator(1))
    ax.xaxis.set_major_formatter(_signed)
    if xlim:
        ax.set_xlim(*xlim)
    else:
        ax.margins(x=0.01)


def overlay_legend(driver):
    return [Line2D([0], [0], color=GREY, lw=1.4, label="Laps 41–46"),
            Line2D([0], [0], color=DRIVER_COLOR[driver], lw=2.4, label="Lap 47 (crash)"),
            Line2D([0], [0], color=COLLISION_COLOR, lw=2, label="collision")]


OMNI_LEGEND = [Line2D([0], [0], color=GREY, lw=1.4, label="Laps 41–46"),
               Line2D([0], [0], color=DRIVER_COLOR["hill"], lw=2.4, label="Hill lap 47"),
               Line2D([0], [0], color=DRIVER_COLOR["svg"], lw=2.4, label="SVG lap 47"),
               Line2D([0], [0], color=COLLISION_COLOR, lw=2, label="collision")]


def _suffix(smoothed, xlim):
    bits = []
    if smoothed:
        bits.append("smoothed")
    if xlim:
        bits.append(f"{xlim[0]:+g} to {xlim[1]:+g}s")
    return f" ({', '.join(bits)})" if bits else ""


def plot_overlay(driver, out_png, smoothed=False, xlim=None,
                 title=None, contact_label=None):
    """All 7 laps overlaid on a collision-relative axis: baseline laps greyed,
    crash lap 47 pink, collision at 0. `smoothed` and `xlim` optional.
    `title` overrides the auto title; `contact_label`, when given, renames the
    red-line callout and moves it to the RPM panel (matching the old
    all_laps_telemetry_smooth_highlight layout)."""
    fig, (ax_mph, ax_rpm) = plt.subplots(
        2, 1, figsize=(9, 9), sharex=True, gridspec_kw={"hspace": 0.12})
    _overlay_metric(ax_mph, driver, "mph", smoothed, xlim)
    _overlay_metric(ax_rpm, driver, "rpm", smoothed, xlim)
    ax_mph.set_ylabel("MPH", fontweight="bold")
    ax_rpm.set_ylabel("RPM", fontweight="bold")
    ax_rpm.set_xlabel("Seconds from collision")
    ann_ax = ax_rpm if contact_label else ax_mph
    ann_ax.annotate(contact_label or "collision", xy=(0, ann_ax.get_ylim()[1]),
                    xytext=(4, -4), textcoords="offset points", ha="left",
                    va="top", color=COLLISION_COLOR, fontsize=9, fontweight="bold")
    ax_mph.legend(handles=overlay_legend(driver), ncol=3, loc="lower center", fontsize=9,
                  bbox_to_anchor=(0.5, 1.02), frameon=False)
    ax_mph.set_title(title or f"{driver} — laps 41–47 overlay{_suffix(smoothed, xlim)}",
                     fontweight="bold", pad=28)
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"overlay {driver} -> {out_png}")


def plot_omni(out_png, smoothed=False, xlim=None):
    """Four stacked panels aligned on the collision (x=0): Hill MPH, SVG MPH,
    Hill RPM, SVG RPM. Each panel is a full laps-41-47 overlay so the crash lap
    (pink) reads against its own baseline, and the shared collision-zeroed axis
    lines the two drivers up by their red bars. `smoothed` and `xlim` optional."""
    panels = [("hill", "mph"), ("hill", "rpm"), ("svg", "mph"), ("svg", "rpm")]
    fig, axes = plt.subplots(4, 1, figsize=(12, 13), sharex=True,
                             gridspec_kw={"hspace": 0.18})
    for ax, (driver, which) in zip(axes, panels):
        _overlay_metric(ax, driver, which, smoothed, xlim)
        ax.set_ylabel(f"{driver}\n{which.upper()}", fontweight="bold")
    axes[-1].set_xlabel("Seconds from collision")
    axes[0].annotate("collision", xy=(0, axes[0].get_ylim()[1]),
                     xytext=(4, -4), textcoords="offset points", ha="left",
                     va="top", color=COLLISION_COLOR, fontsize=9, fontweight="bold")
    axes[0].legend(handles=OMNI_LEGEND, ncol=4, loc="lower center", fontsize=9,
                   bbox_to_anchor=(0.5, 1.04), frameon=False)
    axes[0].set_title(f"Hill vs SVG — MPH & RPM aligned on collision{_suffix(smoothed, xlim)}",
                      fontweight="bold", pad=30)
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"omni -> {out_png}")


def main():
    import re
    args = sys.argv[1:]
    lap_filter = {a for a in args if re.fullmatch(r"lap\d+", a)}
    drivers = [a for a in args if a not in lap_filter] or ["hill", "svg"]
    for driver in drivers:
        out_dir = os.path.join(CHARTS_DIR, driver)
        os.makedirs(out_dir, exist_ok=True)
        base = sorted(p for p in glob.glob(os.path.join(TELEMETRY_DIR, driver, "lap*.csv"))
                      if not os.path.basename(p).endswith("edited.csv"))
        for csv_path in base:
            lap = os.path.splitext(os.path.basename(csv_path))[0]
            if lap_filter and lap not in lap_filter:
                continue
            plot_lap(csv_for(driver, lap), os.path.join(out_dir, f"{lap}.png"), driver, lap)
        if not lap_filter:
            plot_overlay(driver, os.path.join(out_dir, "overlay.png"))
            plot_overlay(driver, os.path.join(out_dir, "overlay_smooth.png"),
                         smoothed=True)
            plot_overlay(driver, os.path.join(out_dir, "overlay_smooth_zoom.png"),
                         smoothed=True, xlim=(-3, 1))
            # Hill's wide chart mirrors the old all_laps_telemetry_smooth_highlight
            # title + contact callout; svg's stays with the generic labelling.
            wide_kw = dict(title="Austin Hill in Lap 47 vs. baseline in Turn 3",
                           contact_label="contact with #97") if driver == "hill" else {}
            plot_overlay(driver, os.path.join(out_dir, "overlay_smooth_wide.png"),
                         smoothed=True, xlim=(-6, 1.5), **wide_kw)
    if not lap_filter and set(drivers) >= {"hill", "svg"}:
        plot_omni(os.path.join(CHARTS_DIR, "omni.png"))
        plot_omni(os.path.join(CHARTS_DIR, "omni_smooth_zoom.png"),
                  smoothed=True, xlim=(-3, 1))


if __name__ == "__main__":
    main()
