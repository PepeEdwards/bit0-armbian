# Installing PICO-8 on the Bit0 (Armbian)

PICO-8 is proprietary and is **deliberately not in this repository** — do not
commit `pico8_dyn` / `pico8.dat` here. The launcher's PICO-8 button shows
`PICO-8 NOT INSTALLED` until the files exist on the device.

## Install (one command, over adb)

The image already ships `libSDL2` (customize-image.sh), and the display is a
DRM device, so stock SDL2 renders via **kmsdrm** — no DirectFB, unlike the old
Buildroot image.

With the device connected over USB (adb):

```bash
./scripts/install-pico8.sh /path/to/unpacked/pico-8
```

The source dir must contain `pico8_dyn` and `pico8.dat` from the
**Raspberry Pi** build (lexaloffle.com). With no argument the script uses the
copy in the old Luckfox SDK overlay
(`Lyra-sdk/buildroot/board/rockchip/rk3506/spi-display-overlay/root/pico-8/`),
including your carts and tuned `config.txt`.

The script pushes everything to `/root/pico-8/`, installs the kmsdrm launch
script (`scripts/pico-8.sh` → `/root/pico-8/pico-8.sh`) and sets permissions.
The launcher picks it up immediately — no reboot.

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
