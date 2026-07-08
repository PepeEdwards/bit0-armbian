# PICO-8 on the Bit0 (Armbian)

PICO-8 is proprietary (lexaloffle.com) and is **never committed to this
repository** — `userpatches/overlay/root/pico-8/` is gitignored. There are two
ways to get it onto the device; both use the same paths as the old Buildroot
image (`/root/pico-8/...`).

The image ships `libSDL2` (customize-image.sh), and the display is a DRM
device, so stock SDL2 renders via **kmsdrm** — no DirectFB, unlike the old
Buildroot image. The only file that differs from the old overlay is
`pico-8.sh` (same path; kmsdrm environment). Its canonical copy is tracked at
`scripts/pico-8.sh`.

## Option A — bake it into the image (build-time)

Before building, place your licensed Raspberry Pi build (needs `pico8_dyn`
and `pico8.dat`; carts/config.txt welcome) at:

```
userpatches/overlay/root/pico-8/
```

and put `scripts/pico-8.sh` in there as `pico-8.sh`. customize-image.sh
detects it and ships it; if the directory is absent it just logs and skips —
fresh clones still build fine, the launcher shows PICO-8 NOT INSTALLED.

## Option B — push to a running device over adb (no rebuild)

```bash
./scripts/install-pico8.sh [/path/to/pico-8]
```

Pushes the directory (default: the copy in the old Luckfox SDK overlay,
including carts and config.txt) to `/root/pico-8/` together with the kmsdrm
launch script. The launcher picks it up immediately — no reboot.

## How it runs

`/root/pico-8/pico-8.sh`:

```sh
export SDL_VIDEODRIVER=kmsdrm
export SDL_AUDIODRIVER=alsa
exec /root/pico-8/pico8_dyn -home /root/pico-8 \
        -windowed 0 -width 320 -height 240 -pixel_perfect 0
```

- Audio goes through the asound.conf softvol chain, so the launcher's VOL
  buttons and the keyboard volume keys affect PICO-8 too.
- Input: the uinput devices from uart-hid-bridge/touch-mouse are normal evdev
  keyboards/mice; SDL2 kmsdrm reads them directly.
- Only one DRM master at a time: the launcher hands the display over while
  PICO-8 runs (that's the normal `app` flow). If testing by hand over adb,
  `systemctl stop bit0-launcher` first.
- Carts read from the SPI SD card are cached in `/root/pico-8/carts/sdcard/`
  by the launcher's SD CARD flow.
