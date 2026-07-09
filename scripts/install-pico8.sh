#!/usr/bin/env bash
# Install PICO-8 onto a running Bit0 over adb.
#
# PICO-8 is proprietary (lexaloffle.com) and is NOT in this repository.
# All launch logic ships in the image (/usr/local/bin/pico8-launch); the
# ONLY thing this script does is copy your licensed Raspberry Pi build:
#
#   ./scripts/install-pico8.sh /path/to/unpacked/pico-8
#
# The path may also come from the PICO8_SRC environment variable. Needs
# pico8_dyn + pico8.dat; carts/ and config.txt come along if present.
# Works from WSL (adb.exe interop) or any Linux with adb.
set -euo pipefail

SRC="${1:-${PICO8_SRC:-}}"
[ -n "$SRC" ] && [ -d "$SRC" ] || { echo "usage: install-pico8.sh /path/to/pico-8 (dir with pico8_dyn + pico8.dat; or set PICO8_SRC)" >&2; exit 1; }

ADB=adb
command -v adb >/dev/null 2>&1 || ADB=adb.exe

[ -f "$SRC/pico8_dyn" ] || { echo "error: $SRC/pico8_dyn not found (need the Raspberry Pi build)" >&2; exit 1; }
[ -f "$SRC/pico8.dat" ] || { echo "error: $SRC/pico8.dat not found" >&2; exit 1; }

echo "==> pushing PICO-8 to /root/pico-8"
"$ADB" shell mkdir -p /root/pico-8/carts
"$ADB" push "$SRC/pico8_dyn" /root/pico-8/
"$ADB" push "$SRC/pico8.dat" /root/pico-8/
[ -f "$SRC/config.txt" ] && "$ADB" push "$SRC/config.txt" /root/pico-8/
[ -d "$SRC/carts" ] && "$ADB" push "$SRC/carts" /root/pico-8/
[ -f "$SRC/license.txt" ] && "$ADB" push "$SRC/license.txt" /root/pico-8/
"$ADB" shell "chmod +x /root/pico-8/pico8_dyn"

echo "==> done. The launcher's PICO-8 button is live (no restart needed)."
