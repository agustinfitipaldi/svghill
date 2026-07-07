#!/usr/bin/env python3
"""Plot MPH and RPM over time for each clip as two stacked charts (shared
time axis): MPH on top, RPM below. Reads the per-clip telemetry CSVs.

Frames whose value was auto-corrected (see *_corrected columns) are marked so
interpolated stretches are visually distinguishable from clean OCR reads.
"""
import csv
import glob
import os
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from matplotlib.lines import Line2D

# repo root = parent of the scripts/ dir this file lives in
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TELEMETRY_DIR = os.path.join(ROOT, "telemetry")
CHARTS_DIR = os.path.join(ROOT, "charts")

MPH_COLOR = "#1f77b4"   # blue
RPM_COLOR = "#d62728"   # red

CONTACT_TIME = 6.0      # seconds — moment of contact in the collision (clip7)


def mark_contact(ax, pos=CONTACT_TIME, label=False):
    """Draw the big red 'contact' marker at time `pos` on an axis."""
    ax.axvline(pos, color="red", lw=3, alpha=0.8, zorder=5,
               label="contact" if label else None)


def _signed(x, _pos=None):
    """Axis tick formatter: 0 at contact, +/- on either side."""
    return "0" if abs(x) < 1e-9 else f"{x:+.0f}"


def load(csv_path):
    t, mph, rpm, mfix, rfix = [], [], [], [], []
    with open(csv_path) as f:
        for r in csv.DictReader(f):
            t.append(float(r["time_seconds"]))
            mph.append(int(r["mph"]))
            rpm.append(int(r["rpm"]))
            mfix.append(bool(r["mph_corrected"]))
            rfix.append(bool(r["rpm_corrected"]))
    return t, mph, rpm, mfix, rfix


def plot_clip(csv_path, out_png):
    t, mph, rpm, mfix, rfix = load(csv_path)
    clip = re.search(r"clip\d+", csv_path).group()

    fig, (ax_mph, ax_rpm) = plt.subplots(
        2, 1, figsize=(11, 7), sharex=True,
        gridspec_kw={"hspace": 0.12})

    ax_mph.plot(t, mph, color=MPH_COLOR, lw=1.8)
    ax_mph.scatter([t[i] for i in range(len(t)) if mfix[i]],
                   [mph[i] for i in range(len(t)) if mfix[i]],
                   s=14, color=MPH_COLOR, alpha=0.35, zorder=3,
                   label="corrected")
    ax_mph.set_ylabel("MPH", color=MPH_COLOR, fontweight="bold")
    ax_mph.tick_params(axis="y", labelcolor=MPH_COLOR)

    ax_rpm.plot(t, rpm, color=RPM_COLOR, lw=1.8)
    ax_rpm.scatter([t[i] for i in range(len(t)) if rfix[i]],
                   [rpm[i] for i in range(len(t)) if rfix[i]],
                   s=14, color=RPM_COLOR, alpha=0.35, zorder=3,
                   label="corrected")
    ax_rpm.set_ylabel("RPM", color=RPM_COLOR, fontweight="bold")
    ax_rpm.tick_params(axis="y", labelcolor=RPM_COLOR)
    ax_rpm.set_xlabel("Time (seconds)")

    for ax in (ax_mph, ax_rpm):
        ax.grid(True, alpha=0.25)
        ax.margins(x=0.01)
        if any(m for m in (mfix if ax is ax_mph else rfix)):
            ax.legend(loc="lower right", fontsize=8, framealpha=0.7)

    if clip == "clip7":
        mark_contact(ax_mph)
        mark_contact(ax_rpm)
        ax_mph.annotate("contact", xy=(CONTACT_TIME, ax_mph.get_ylim()[1]),
                        xytext=(3, -3), textcoords="offset points",
                        ha="left", va="top", color="red", fontsize=9,
                        fontweight="bold")

    ax_mph.set_title(f"{clip} — Austin Hill #33 telemetry", fontweight="bold")
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"{csv_path} -> {out_png}")


# distinct categorical colors for the 7 clips overlaid together
CLIP_COLORS = ["#4e79a7", "#59a14f", "#e6a23c", "#2f6b34",
               "#4b4bd6", "#d1495b", "#e377c2"]


# clip N corresponds to lap 40 + N (clip1 = lap 41 ... clip7 = lap 47)
LAP_OFFSET = 40


def smooth(vals, win=15):
    """Centered moving average to iron out the HUD's staircase plateaus into a
    readable curve. Window shrinks near the ends so the line still spans fully."""
    n = len(vals)
    out = []
    half = win // 2
    for i in range(n):
        lo, hi = max(0, i - half), min(n, i + half + 1)
        out.append(sum(vals[lo:hi]) / (hi - lo))
    return out


def plot_all(out_png, xlim=None, smoothed=False, highlight=False, figsize=(12, 8)):
    """Overlay all 7 laps on shared MPH (top) and RPM (bottom) axes.

    xlim=(lo, hi) zooms the shared time axis to that window.
    smoothed=True irons the HUD's staircase plateaus into readable curves.
    highlight=True greys out laps 41-46 so the collision lap (47) pops.
    figsize sets the overall figure proportions."""
    prep = smooth if smoothed else (lambda v: v)
    paths = sorted(glob.glob(os.path.join(TELEMETRY_DIR, "clip*_telemetry.csv")),
                   key=lambda x: int(re.search(r"\d+", x).group()))
    fig, (ax_mph, ax_rpm) = plt.subplots(
        2, 1, figsize=figsize, sharex=True,
        gridspec_kw={"hspace": 0.12})

    for p in paths:
        n = int(re.search(r"clip(\d+)", p).group(1))
        t, mph, rpm, _, _ = load(p)
        # re-zero time so contact is 0, earlier is negative, later positive
        t = [x - CONTACT_TIME for x in t]
        lap = f"Lap {LAP_OFFSET + n}"
        # emphasise the collision lap (47) so it stands out from the pack
        collision = (n == 7)
        if highlight and not collision:
            color = "#8f8f8f"
        else:
            color = CLIP_COLORS[(n - 1) % len(CLIP_COLORS)]
        lw = 3.2 if collision else 1.4
        alpha = 1.0 if collision else (0.55 if highlight else 0.75)
        z = 6 if collision else 3
        ax_mph.plot(t, prep(mph), color=color, lw=lw, label=lap, alpha=alpha, zorder=z)
        ax_rpm.plot(t, prep(rpm), color=color, lw=lw, label=lap, alpha=alpha, zorder=z)

    mark_contact(ax_mph, pos=0)
    mark_contact(ax_rpm, pos=0)

    ax_mph.set_ylabel("MPH", fontweight="bold")
    ax_rpm.set_ylabel("RPM", fontweight="bold")
    ax_rpm.set_xlabel("Time from contact (seconds)")
    for ax in (ax_mph, ax_rpm):
        ax.grid(True, alpha=0.25)
        ax.xaxis.set_major_locator(MultipleLocator(1))
        ax.xaxis.set_major_formatter(_signed)
        if xlim:
            ax.set_xlim(xlim[0] - CONTACT_TIME, xlim[1] - CONTACT_TIME)
        else:
            ax.margins(x=0.01)
    # place the contact label using the (possibly zoomed) axis limits
    ax_rpm.annotate("contact with #97", xy=(0, ax_rpm.get_ylim()[1]),
                    xytext=(3, -3), textcoords="offset points",
                    ha="left", va="top", color="red", fontsize=9,
                    fontweight="bold")
    if highlight:
        handles = [Line2D([0], [0], color="#8f8f8f", lw=1.4, label="Laps 41–46"),
                   Line2D([0], [0], color=CLIP_COLORS[6], lw=3.2, label="Lap 47")]
        ax_mph.legend(handles=handles, ncol=2, loc="lower center", fontsize=9,
                      bbox_to_anchor=(0.5, 1.02), frameon=False)
    else:
        ax_mph.legend(ncol=7, loc="lower center", fontsize=9,
                      bbox_to_anchor=(0.5, 1.02), frameon=False)
    ax_mph.set_title(
        "Austin Hill in Lap 47 vs. baseline in Turn 3",
        fontweight="bold", pad=28)
    fig.savefig(out_png, dpi=120, bbox_inches="tight")
    plt.close(fig)
    print(f"-> {out_png}")


def main():
    os.makedirs(CHARTS_DIR, exist_ok=True)
    out = lambda name: os.path.join(CHARTS_DIR, name)
    for csv_path in sorted(glob.glob(os.path.join(TELEMETRY_DIR, "clip*_telemetry.csv")),
                           key=lambda x: int(re.search(r"\d+", x).group())):
        n = re.search(r"clip(\d+)", csv_path).group(1)
        plot_clip(csv_path, out(f"clip{n}_telemetry.png"))
    plot_all(out("all_laps_telemetry.png"))
    plot_all(out("all_laps_telemetry_smooth.png"), smoothed=True)
    plot_all(out("all_laps_telemetry_3-7s.png"), xlim=(3, 7))
    plot_all(out("all_laps_telemetry_3-7s_smooth.png"), xlim=(3, 7), smoothed=True)
    plot_all(out("all_laps_telemetry_smooth_highlight.png"), smoothed=True, highlight=True,
             figsize=(9, 9))
    plot_all(out("all_laps_telemetry_3-7s_smooth_highlight.png"),
             xlim=(3, 7), smoothed=True, highlight=True, figsize=(9, 9))


if __name__ == "__main__":
    main()
