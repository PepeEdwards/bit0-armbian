#!/usr/bin/env bash
# Build the Bit0 SD card image.
# Run on a native Ubuntu 24.04 x86_64 host (WSL2 works; no Docker needed).
# Build from a Linux filesystem (~), never from /mnt/c.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# The framework finds userpatches/ via the symlink build/userpatches -> ../userpatches
# (recreate if missing, e.g. after a checkout that dropped symlinks)
[ -e "$REPO_ROOT/build/userpatches" ] || ln -s ../userpatches "$REPO_ROOT/build/userpatches"

cd "$REPO_ROOT/build"
./compile.sh bit0 "$@"

echo
echo "Image ready:"
ls -1 "$REPO_ROOT"/build/output/images/*.img* 2>/dev/null
echo "Flash it with balenaEtcher/Rufus (copy it to Windows first if flashing from there)."
