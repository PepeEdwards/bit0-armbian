# Installing PICO-8 on the Bit0 (Armbian)

PICO-8 is proprietary and is **not** shipped in the image. The launcher's
PICO-8 button shows `PICO-8 NOT INSTALLED` until the files below exist.

## 1. Copy the PICO-8 files

Buy/download the **Raspberry Pi** build from lexaloffle.com (armhf — matches
this armhf image) and unpack it to `/root/pico-8/` on the device so that:

```
/root/pico-8/pico8_dyn        # dynamically-linked binary (the one we use)
/root/pico-8/pico8.dat
/root/pico-8/pico-8.sh        # launch script, see below
/root/pico-8/config.txt
/root/pico-8/carts/
```

The launcher checks for `/root/pico-8/pico-8.sh` and runs it; carts read from
the SPI SD card are cached in `/root/pico-8/carts/sdcard/`.

Config that worked on the SDK build (window 256x320, fullscreen, ALSA audio)
is preserved in the old overlay: `Lyra-sdk/buildroot/board/rockchip/rk3506/
spi-display-overlay/root/pico-8/{config.txt,pico-8.sh}` — copy both.

## 2. Video backend: kmsdrm (already solved by the image)

`pico8_dyn` renders through SDL2. On the SDK image it needed
`SDL_VIDEODRIVER=directfb` plus a hand-built DirectFB stack, because the
display was a plain fbdev device. **This image drives the panel with the
mainline DRM driver (`panel-mipi-dbi`)**, so there is a real DRM device and
stock Debian SDL2 works directly:

```sh
apt-get install libsdl2-2.0-0
```

and in `/root/pico-8/pico-8.sh` replace the old environment with:

```sh
export SDL_VIDEODRIVER=kmsdrm
export SDL_AUDIODRIVER=alsa
~/pico-8/pico8_dyn -home /root/pico-8 -windowed 0 -width 240 -height 320 -pixel_perfect 0
```

No DirectFB, no `.directfbrc`. Note: stop the launcher first if testing by
hand (`systemctl stop bit0-launcher`) — only one DRM master at a time.

## 3. Audio and input

- Audio: `SDL_AUDIODRIVER=alsa` works unchanged (MAX98357A via asound.conf
  dmix/softvol).
- Input: the uinput devices from uart-hid-bridge/touch-mouse appear as normal
  evdev keyboards/mice; SDL2 kmsdrm reads them directly.

## 4. Wire into the launcher

Nothing else to do — once `/root/pico-8/pico-8.sh` exists the PICO-8 menu
entry launches it.
