#!/usr/bin/env bash
# Turn animated GIFs into animated WebP, about a tenth of the size, for the
# README (GitHub plays them just the same). Needs ffmpeg.
#
#   scripts/gif_to_webp.sh "docs/images/my card.gif" [more.gif ...]
#
# Writes my card.webp beside each GIF and leaves the GIF alone: link the
# .webp in the README and keep the GIF out of the repo. QUALITY=92 by
# default (white paper's faint shading goes blotchy much below 90).
set -euo pipefail
for gif in "$@"; do
    out="${gif%.*}.webp"
    ffmpeg -v error -y -i "$gif" -c:v libwebp_anim -lossless 0 -q:v "${QUALITY:-92}" \
        -compression_level 6 -loop 0 -an "$out"
    echo "$out: $(du -h "$gif" | cut -f1) -> $(du -h "$out" | cut -f1)"
done
