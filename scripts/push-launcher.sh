#!/usr/bin/env bash
# Push the launcher stack to a running Bit0 over adb and restart it.
#
# Dev-iteration helper: copies the overlay files verbatim to their
# target-filesystem paths, so what you test is exactly what the next
# image build ships. Works from WSL (adb.exe interop) or any Linux
# with adb; the Bit0's USB gadget exposes an unauthenticated adbd
# (see docs/BINARIES.md).
#
#   ./scripts/push-launcher.sh
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OVL="$REPO/userpatches/overlay"

ADB=adb
command -v adb >/dev/null 2>&1 || ADB=adb.exe

echo "==> pushing launcher + helpers + lib"
"$ADB" push "$OVL/usr/local/bin/bit0-launcher" /usr/local/bin/
"$ADB" push "$OVL/usr/local/bin/bit0-vol" /usr/local/bin/
for f in "$OVL"/usr/local/lib/bit0/*.py; do
    "$ADB" push "$f" /usr/local/lib/bit0/
done
"$ADB" shell chmod +x /usr/local/bin/bit0-launcher /usr/local/bin/bit0-vol
# stale bytecode from the previous lib would shadow the pushed sources
"$ADB" shell rm -rf /usr/local/lib/bit0/__pycache__
"$ADB" shell systemctl restart bit0-launcher
echo "==> done; follow logs with: adb shell journalctl -u bit0-launcher -f"
