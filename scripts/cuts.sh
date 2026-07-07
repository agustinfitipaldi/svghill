#!/usr/bin/env bash
# Cut the 7 lap clips out of the source recording. Run from anywhere; paths
# resolve to the repo root. mother.mov and the clips/ output are gitignored.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
mkdir -p "$ROOT/clips"

cuts=(
  "42.4 50.4 clip1"
  "74.08 82.08 clip2"
  "105.6 113.6 clip3"
  "137.5 145.5 clip4"
  "169.47 177.47 clip5"
  "201.2 209.2 clip6"
  "233.2 241.2 clip7"
)

for cut in "${cuts[@]}"; do
  read -r start end name <<< "$cut"
  ffmpeg -i "$ROOT/mother.mov" -ss "$start" -to "$end" -c copy "$ROOT/clips/${name}.mov"
done