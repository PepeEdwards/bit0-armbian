#!/usr/bin/env bash
# Build the Bit0 SD card image.
# Run on a native Ubuntu 24.04 x86_64 host (WSL2 works; no Docker needed there).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WINDOWS_DEST="/mnt/c/Users/jflir/bit0"

# The framework finds userpatches/ via the symlink build/userpatches -> ../userpatches
# (created on clone by git; recreate if missing, e.g. after a clean checkout on Windows)
[ -e "$REPO_ROOT/build/userpatches" ] || ln -s ../userpatches "$REPO_ROOT/build/userpatches"

cd "$REPO_ROOT/build"
./compile.sh bit0 "$@"

# Copy the image to the Windows filesystem so it can be flashed with balenaEtcher/Rufus
if [ -d /mnt/c ]; then
    mkdir -p "$WINDOWS_DEST"
    cp -v output/images/*.img.xz "$WINDOWS_DEST"/ 2>/dev/null ||
        cp -v output/images/*.img "$WINDOWS_DEST"/
    echo "Image copied to $WINDOWS_DEST — flash from Windows with balenaEtcher or Rufus."
else
    echo "Image ready in build/output/images/"
fi
