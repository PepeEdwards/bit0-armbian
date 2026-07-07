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

## 2. The video backend problem

`pico8_dyn` renders through SDL2. On the SDK image it used
`SDL_VIDEODRIVER=directfb` with a `/root/.directfbrc` (fbdev system, cursor
off, input restricted to the Lyra uinput devices). **Debian's SDL2 has no
DirectFB backend** (DirectFB was dropped from Debian), and SDL2 has no fbdev
backend either, so the SDK launch script does not work as-is.

Options, best first:

### Option A — switch the display to the mainline DRM driver (recommended)

The kernel has a mainline **tinydrm** driver for this panel
(`drivers/gpu/drm/tiny/ili9341.c`, same `ilitek,ili9341` compatible). Using it
instead of our fbdev driver gives a real DRM device, and stock Debian SDL2
works out of the box with `SDL_VIDEODRIVER=kmsdrm`. fbcon still works through
the DRM fbdev emulation.

- kernel config: `CONFIG_DRM_ILI9341=m` (and drop `CONFIG_FB_ILI9341`)
- DTS: the node needs the mainline binding properties (`dc-gpios`,
  `reset-gpios`, `backlight` phandle) — small patch to
  `rk3506g-luckfox-lyra-sd.dts`
- lose: the custom driver's splash screen and dirty-line tuning;
  verify SPI throughput is acceptable at 80 MHz

### Option B — build DirectFB yourself (replicates the SDK exactly)

Compile legacy DirectFB 1.7.7 + SDL2 with `--enable-video-directfb` on the
device (or cross-compile), install to `/usr/local`, copy the SDK's
`/root/.directfbrc`. Heavyweight and unmaintained, but known-good on this
exact hardware.

### Option C — statically-bundled SDL

Build SDL2 with the legacy fbdev patchset, or run the pico8 static binary
against SDL1.2-compat. Fragile; last resort.

## 3. Audio and input

- Audio: `SDL_AUDIODRIVER=alsa` works unchanged (MAX98357A via asound.conf
  dmix/softvol).
- Input: the uinput devices from uart-hid-bridge/touch-mouse appear as normal
  evdev keyboards/mice; SDL2 kmsdrm reads them directly. The `.directfbrc`
  input restrictions are only needed with Option B.

## 4. Wire into the launcher

Nothing to do — once `/root/pico-8/pico-8.sh` exists the PICO-8 menu entry
launches it. Update `pico-8.sh`'s `SDL_VIDEODRIVER` to match the option you
chose (`kmsdrm` for Option A).
