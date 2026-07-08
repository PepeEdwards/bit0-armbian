#!/bin/bash
# Armbian image customization hook — runs inside the target rootfs chroot.
# Overlay files are available at /tmp/overlay.
# Arguments: $1=RELEASE $2=LINUXFAMILY $3=BOARD $4=BUILD_DESKTOP

RELEASE=$1
BOARD=$3

Main() {
	[ "$BOARD" = "bit0" ] || return 0

	echo "bit0: installing packages" >&2
	apt-get -y -qq update
	# python3-serial: uart-hid-bridge; kbd: openvt/chvt for the launcher's
	# TERMINAL entry; triggerhappy: volume/power hotkeys; alsa-utils: amixer.
	# The daemons themselves are stdlib-only Python (raw fb/uinput ioctls).
	apt-get -y -qq install --no-install-recommends \
		python3 python3-serial triggerhappy alsa-utils kbd

	echo "bit0: installing overlay files" >&2
	cp -rv /tmp/overlay/usr /
	cp -rv /tmp/overlay/etc /

	# Panel init firmware: explicit install (a bare 'cp -r .../lib /' proved
	# unreliable with the usrmerge /lib symlink), and fail the build loudly
	# if it's missing — without it the display driver cannot start.
	install -D -m 0644 "/tmp/overlay/lib/firmware/bit0,ili9341.bin" \
		"/usr/lib/firmware/bit0,ili9341.bin"
	[ -f "/usr/lib/firmware/bit0,ili9341.bin" ] || {
		echo "bit0: FATAL: panel firmware missing" >&2
		exit 1
	}

	echo "bit0: enabling services" >&2
	systemctl enable uart-hid-bridge.service
	systemctl enable touch-mouse.service
	systemctl enable bit0-launcher.service
	systemctl enable triggerhappy.service

	# Login console on the USB gadget serial port (g_serial -> ttyGS0).
	# Plug the Lyra's USB into a PC and it appears as a COM port.
	systemctl enable serial-getty@ttyGS0.service

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
