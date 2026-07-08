#!/bin/sh
# Launch PICO-8 on the Bit0 (Armbian). Installed to /root/pico-8/pico-8.sh
# by scripts/install-pico8.sh; the launcher runs it via the PICO-8 button.
#
# The display is a DRM device (panel-mipi-dbi), so stock Debian SDL2 renders
# through kmsdrm — no DirectFB, no .directfbrc, unlike the old Buildroot image.
export SDL_VIDEODRIVER=kmsdrm
export SDL_AUDIODRIVER=alsa

exec /root/pico-8/pico8_dyn -home /root/pico-8 \
	-windowed 0 -width 320 -height 240 -pixel_perfect 0
