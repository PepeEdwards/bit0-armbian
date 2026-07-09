# Porting notes: Luckfox SDK → Armbian

Where every piece of the bit0 came from, and what changed in the move.

## Framework mapping

| Luckfox Buildroot SDK | bit0-armbian |
|---|---|
| private repo-tool workspace (32 GB, `ssh://192.168.10.75`) | `armbian/build` submodule + this repo's `userpatches/` |
| `kernel-6.1/` (Rockchip BSP 6.1, rkr4.2-era) | `armbian/linux-rockchip` @ `rk-6.1-rkr5.1` (same lineage; the Lyra dtsi is byte-identical) |
| `buildroot/configs/rockchip_rk3506_luckfox_defconfig` | Debian trixie minimal (`BUILD_MINIMAL=yes`) + `customize-image.sh` |
| `device/rockchip/` build scripts, `build.sh`, rkflash | `./compile.sh bit0` — output is one flashable SD image |
| U-Boot `rk3506_luckfox` (Rockchip fork) | mainline-WIP U-Boot (kwiboo's rk3506 branch, pinned by Armbian), `luckfox-lyra-rk3506_defconfig` |
| `rkbin` blobs from private mirror | same blobs via Armbian's `rkbin-tools` (public `rockchip-linux/rkbin`) |

## Kernel changes (userpatches/kernel/rk35xx-vendor-6.1/)

| SDK change | Armbian equivalent |
|---|---|
| edits to `rk3506-luckfox-lyra.dtsi` + `rk3506g-luckfox-lyra-sd.dts` | patch 0001: single new self-contained `rk3506g-luckfox-lyra-sd.dts` (the shared dtsi is untouched, so Lyra Plus / Zero W images are unaffected) |
| out-of-tree `custom_driver/ili9341_display_driver/ili9341_fb.ko`, insmod'ed by `S09spi-display` | **no driver code at all** — mainline `panel-mipi-dbi` DRM driver (`CONFIG_DRM_PANEL_MIPI_DBI=m`); the panel init sequence lives in `/lib/firmware/bit0,ili9341.bin`, generated at image build from source + compiler in `userpatches/overlay/usr/local/src/panel-firmware/` (also shipped on-device). fbcon/`/dev/fb0` via DRM fbdev emulation. Backlight GPIO became a standard `gpio-backlight` node. |
| `ads7846.c` poll period 5→20 ms | patch 0002, identical |
| `rk3506_luckfox_defconfig` + `rk3506-display.config` additions | `userpatches/linux-rockchip-vendor.config` (Armbian's config + bit0 block at the end) |
| in-kernel `lyra_i2c_keyboard.c` (I2C 0x20) | **not ported** — the bit0 uses the UART2 HID bridge |
| kernel-embedded splash (`splash_data.h`) | **dropped** — the launcher draws its own splash a few seconds later; add an early fb-blit service if boot-time splash is wanted |

## Userspace changes (userpatches/overlay/ + customize-image.sh)

| SDK (SysV init, Buildroot) | Armbian (systemd, Debian) |
|---|---|
| `S09spi-display` (insmod ili9341_fb.ko) | gone — `panel_mipi_dbi` autoloads via DT; also listed in `modules-load.d/bit0.conf` |
| `S49hidg` (modprobe uinput) | `modules-load.d/bit0.conf` |
| `S50uart-hid` | `uart-hid-bridge.service` |
| `S51touch-mouse` | `touch-mouse.service` (`ConditionPathExists=/etc/touch-mouse.cal`) |
| `S52triggerhappy` | Debian's own `triggerhappy.service`; confs moved to `/etc/triggerhappy/triggers.d/` |
| `S99bit0-launcher` respawn loop | `bit0-launcher.service` with `Restart=always`; `getty@tty1` disabled (launcher owns tty1; serial getty on ttyFIQ0 remains) |
| `lyra-volume-handler` Buildroot package | dropped — duplicate of the triggerhappy audio conf |
| daemons in `/usr/bin` | `/usr/local/bin`; launcher's calibrate flow now uses `systemctl stop/start touch-mouse` |
| `.directfbrc`, `/root/pico-8/` | not shipped — see `PICO8.md` |
| `S10firstboot`, inittab tweaks | not needed (systemd; Armbian has its own firstboot) |

## Known risks / first-boot watchlist

- **U-Boot**: `luckfox-lyra-rk3506_defconfig` is validated on the Lyra Plus, not the base Lyra. Watch the serial console (`ttyFIQ0`, 1500000 baud) on first boot.
- **UART2 tty name**: the bridge expects `/dev/ttyS2`. Same kernel as the SDK so it should hold, but verify with `ls /dev/ttyS*` if the keyboard is dead.
- **event device numbering**: `touch-mouse` grabs `/dev/input/event0` by default; Debian udev may order devices differently than Buildroot did.
- **fbcon**: `console=tty1 fbcon=font:VGA8x8` is in the DTS bootargs, but Armbian's boot.cmd/armbianEnv.txt may append its own `console=`. If the LCD console is missing, check `/boot/armbianEnv.txt` (`extraargs=fbcon=map:0 fbcon=font:VGA8x8`).
- **Display flush rate**: the old driver throttled to 30 fps and tracked dirty lines; DRM flushes damage rects on demand instead. If touch feels starved under heavy screen updates, that's the shared-SPI contention to revisit (the ads7846 20 ms patch is the main mitigation).
- **Panel init**: if colors/orientation are off, edit `bit0,ili9341.txt` (e.g. MADCTL `0x36`, inversion `0x20/0x21`) — source + compiler live in `userpatches/overlay/usr/local/src/panel-firmware/` and ship on-device at `/usr/local/src/panel-firmware/`, so regenerate with `python3 mipi-dbi-cmd /usr/lib/firmware/bit0,ili9341.bin bit0,ili9341.txt` right on the device — no kernel or image rebuild needed.
- **128 MB RAM**: keep `BUILD_MINIMAL=yes`; think twice before apt-installing anything heavy.

## Not ported (still in the SDK if ever needed)

- `custom_driver/i2c_keyboard/` + `lyra_i2c_keyboard.c` (I2C keyboard path)
- `ili9488_fb.c` (unused display variant)
- `fs-overlay/` RkLunch hooks, PulseAudio config
