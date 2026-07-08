#!/bin/sh
# Launch PICO-8 on the Bit0 (Armbian). Lives at /root/pico-8/pico-8.sh
# (installed from the build overlay or by scripts/install-pico8.sh); the
# launcher runs it via the PICO-8 button.
#
# The display is a DRM device (panel-mipi-dbi) and the RK3506 has no GPU:
# SDL2 kmsdrm presents through EGL, provided in software by Mesa's
# kms_swrast + llvmpipe (libgl1-mesa-dri/libegl1/libgles2 ship in the image).
# LIBGL_ALWAYS_SOFTWARE makes Mesa pick the software path deterministically.
export SDL_VIDEODRIVER=kmsdrm
export SDL_AUDIODRIVER=alsa
export LIBGL_ALWAYS_SOFTWARE=1

exec /root/pico-8/pico8_dyn -home /root/pico-8 \
	-windowed 0 -width 320 -height 240 -pixel_perfect 0
