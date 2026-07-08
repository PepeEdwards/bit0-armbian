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
	cp -rv /tmp/overlay/lib /	# /lib/firmware/bit0,ili9341.bin (panel init)

	echo "bit0: enabling services" >&2
	systemctl enable uart-hid-bridge.service
	systemctl enable touch-mouse.service
	systemctl enable bit0-launcher.service
	systemctl enable triggerhappy.service

	# The launcher owns tty1; keep a getty only on the serial console.
	systemctl disable getty@tty1.service

	echo "bit0: customization done" >&2
}

Main "$@"
