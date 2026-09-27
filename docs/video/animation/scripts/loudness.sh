#!/usr/bin/env bash
# Normalise a rendered video's soundtrack to -16 LUFS (true peak -1.5 dB), the usual level for
# online video; the video stream is copied unchanged. Usage: scripts/loudness.sh out/file.mp4
set -euo pipefail
in=$1
tmp="${in%.mp4}.norm.mp4"
npx remotion ffmpeg -hide_banner -v error -y -i "$in" -c:v copy \
  -af loudnorm=I=-16:TP=-1.5:LRA=11 -ar 48000 -c:a aac -b:a 192k "$tmp"
mv "$tmp" "$in"
echo "loudness normalised: $in"
