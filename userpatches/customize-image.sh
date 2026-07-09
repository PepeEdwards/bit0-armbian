#!/bin/bash
# Armbian image customization hook — runs inside the target rootfs chroot.
# Overlay files are available at /tmp/overlay.
# Arguments: $1=RELEASE $2=LINUXFAMILY $3=BOARD $4=BUILD_DESKTOP
# Fail the build on any error: a bootable image with silently missing
# packages/files is worse than no image.
set -euo pipefail

RELEASE=$1
BOARD=$3

# Transplanted SDK adbd (see docs/BINARIES.md): verify provenance before it
# ships — a corrupted or swapped binary must fail the build, not the device.
ADBD_SHA256=e1a298ce71ed76c572ef87cea84e0f4c6a8f39079777dbcd0077cb4251b85e8f

Main() {
	[ "$BOARD" = "bit0" ] || return 0

	echo "bit0: installing packages" >&2
	apt-get -y -qq update
	# python3-serial: uart-hid-bridge; kbd: openvt/chvt for the launcher's
	# TERMINAL entry; triggerhappy: volume/power hotkeys; alsa-utils: amixer;
	# libssl3t64: libcrypto.so.3 for the transplanted SDK adbd binary;
	# libsdl2: for PICO-8 (installed separately, see docs/PICO8.md).
	# mesa/EGL/GLES: the RK3506 has no GPU — SDL2's kmsdrm backend cannot
	# present frames without EGL (verified on hardware: pico-8 ran with audio
	# but the plane kept scanning fbcon's framebuffer, and its rpi blit path
	# segfaulted). Mesa's kms_swrast + llvmpipe provide software GL over KMS.
	# The daemons themselves are stdlib-only Python (raw fb/uinput ioctls).
	apt-get -y -qq install --no-install-recommends \
		python3 python3-serial triggerhappy alsa-utils kbd libssl3t64 \
		libsdl2-2.0-0 libgl1-mesa-dri libegl1 libgles2

	echo "bit0: verifying adbd checksum" >&2
	echo "$ADBD_SHA256  /tmp/overlay/usr/local/bin/adbd" | sha256sum -c - || {
		echo "bit0: FATAL: adbd checksum mismatch (docs/BINARIES.md)" >&2
		exit 1
	}

	echo "bit0: installing overlay files" >&2
	cp -rv /tmp/overlay/usr /
	cp -rv /tmp/overlay/etc /
	chmod +x /usr/local/bin/*	# a lost exec bit = 203/EXEC at boot

	# Build-generated artifacts (audit 1.2/1.3): binaries with source in this
	# repo are compiled here, never committed. Sources ship in the image under
	# /usr/local/src so they can also be regenerated on-device.
	echo "bit0: compiling pico8-stretch.so" >&2
	apt-get -y -qq install --no-install-recommends gcc libc6-dev
	gcc -O2 -shared -fPIC -o /usr/local/lib/pico8-stretch.so \
		/usr/local/src/pico8-stretch.c -ldl
	apt-get -y -qq purge gcc libc6-dev
	apt-get -y -qq autoremove --purge

	# PICO-8 is proprietary and gitignored: it ships in the image only when
	# the builder has placed a licensed copy at overlay/root/pico-8/
	# (see docs/PICO8.md). Otherwise install later via install-pico8.sh.
	# All launch logic is in the image regardless (pico8-launch + the
	# pico8-stretch.so shim).
	if [ -f /tmp/overlay/root/pico-8/pico8_dyn ]; then
		echo "bit0: installing local pico-8 copy" >&2
		cp -r /tmp/overlay/root /
		chmod +x /root/pico-8/pico8_dyn
	else
		echo "bit0: no pico-8 in overlay, skipping (docs/PICO8.md)" >&2
	fi

	# Panel init firmware: generated from source (mipi-dbi-cmd format), and
	# fail the build loudly if it's missing — without it the display driver
	# cannot start.
	echo "bit0: generating panel firmware" >&2
	install -d /usr/lib/firmware
	python3 /usr/local/src/panel-firmware/mipi-dbi-cmd \
		"/usr/lib/firmware/bit0,ili9341.bin" \
		"/usr/local/src/panel-firmware/bit0,ili9341.txt"
	[ -f "/usr/lib/firmware/bit0,ili9341.bin" ] || {
		echo "bit0: FATAL: panel firmware missing" >&2
		exit 1
	}

	echo "bit0: enabling services" >&2
	systemctl enable uart-hid-bridge.service
	systemctl enable touch-mouse.service
	systemctl enable bit0-launcher.service
	systemctl enable triggerhappy.service
	systemctl enable bit0-alsa-init.service

	# USB gadget: adb only (configfs + the SDK's adbd), like the old image.
	# 'adb shell' / 'adb push' replace the earlier ttyGS0 serial console.
	systemctl enable bit0-usb-gadget.service

	# The launcher owns tty1; keep a getty only on the serial console.
	systemctl disable getty@tty1.service

	# Keep the kernel console OFF ttyS2 — that UART is the QMK keyboard
	# link. 'display' limits the boot script to console=tty1 (the LCD).
	if [ -f /boot/armbianEnv.txt ]; then
		grep -q '^console=' /boot/armbianEnv.txt ||
			echo 'console=display' >> /boot/armbianEnv.txt
	else
		echo "bit0: WARNING: /boot/armbianEnv.txt not present at customize time" >&2
	fi

	echo "bit0: customization done" >&2
}

Main "$@"
