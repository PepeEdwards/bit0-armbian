#!/usr/bin/env bash
# Install PICO-8 onto the Bit0 over adb.
#
# PICO-8 is proprietary (lexaloffle.com) and is deliberately NOT in this
# repository. Point this script at an unpacked **Raspberry Pi** build:
#
#   ./scripts/install-pico8.sh /path/to/unpacked/pico-8
#
# With no argument it uses the copy living in the old Luckfox SDK overlay
# (pepe's machine). The dir must contain pico8_dyn and pico8.dat. Works from
# WSL (uses adb.exe via Windows interop) or any Linux with adb.
set -euo pipefail

SDK_PICO8=/home/<user>/Lyra-sdk/buildroot/board/rockchip/rk3506/spi-display-overlay/root/pico-8
SRC="${1:-$SDK_PICO8}"
[ -d "$SRC" ] || { echo "usage: install-pico8.sh /path/to/pico-8 (dir with pico8_dyn + pico8.dat)" >&2; exit 1; }
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

echo "==> installing launch script (kmsdrm)"
"$ADB" push "$HERE/pico-8.sh" /root/pico-8/pico-8.sh
"$ADB" shell "chmod +x /root/pico-8/pico8_dyn /root/pico-8/pico-8.sh"

echo "==> checking SDL2 on the device"
if ! "$ADB" shell "ldconfig -p 2>/dev/null | grep -q libSDL2-2.0" ; then
	echo "WARNING: libSDL2 not found on the device."
	echo "  Images built after this commit include it (customize-image.sh);"
	echo "  rebuild + reflash, or install the .deb manually via adb push + dpkg."
fi

echo "==> done. The launcher's PICO-8 button is live (no restart needed)."
