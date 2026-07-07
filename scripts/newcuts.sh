#!/usr/bin/env bash
# Cut the 7 lap clips out of each fresh recording (hill.mov, svg.mov).
# Timestamps came from DaVinci Resolve as [MM:]SS:FF where FF is a frame count
# out of 60, so the frame component is divided by 60 to get decimal seconds.
# Each clip is 10s long — lap47 needs the extra length to capture the sync
# point where SVG crosses Hill's hood.
#
# Unlike the old cuts.sh, we re-encode instead of -c copy: the sync point is
# frame-sensitive and stream-copy only cuts on keyframes. -ss before -i does a
# fast seek, re-encoding makes the output start exactly on the requested frame.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# "source start_seconds lapname"
cuts=(
  # hill: 41 53:13  42 1:24:49  43 1:56:22  44 2:28:12  45 3:00:11  46 3:31:58  47 4:03:54
  "hill 53.2167  lap41"
  "hill 84.8167  lap42"
  "hill 116.3667 lap43"
  "hill 148.2000 lap44"
  "hill 180.1833 lap45"
  "hill 211.9667 lap46"
  "hill 243.9000 lap47"
  # svg: 41 21:55  42 53:46  43 1:25:31  44 1:57:15  45 2:28:59  46 3:00:59  47 3:32:46
  "svg  21.9167  lap41"
  "svg  53.7667  lap42"
  "svg  85.5167  lap43"
  "svg  117.2500 lap44"
  "svg  148.9833 lap45"
  "svg  180.9833 lap46"
  "svg  212.7667 lap47"
)

for cut in "${cuts[@]}"; do
  read -r src start name <<< "$cut"
  outdir="$ROOT/clips/$src"
  mkdir -p "$outdir"
  ffmpeg -y -ss "$start" -i "$ROOT/${src}.mov" -t 10 \
    -c:v libx264 -crf 18 -preset veryfast -an \
    "$outdir/${name}.mov"
done
