#!/usr/bin/env bash
# Explode every lap clip into PNG frames for OCR.
# The fresh hill.mov/svg.mov recordings are natively 30fps, so we take EVERY
# frame -- no every-other-frame dedup like the old 60fps OBS workflow.
# Output: frames/<driver>/<lap>/frame_XXXX.png  (~300 frames per clip)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

for src in hill svg; do
  for clip in "$ROOT/clips/$src"/*.mov; do
    lap="$(basename "$clip" .mov)"
    outdir="$ROOT/frames/$src/$lap"
    mkdir -p "$outdir"
    ffmpeg -y -loglevel error -i "$clip" "$outdir/frame_%04d.png"
    echo "$src/$lap: $(ls "$outdir" | wc -l | tr -d ' ') frames"
  done
done
