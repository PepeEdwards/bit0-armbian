# bit0-armbian

Armbian port of the **Bit0** handheld — a [Luckfox Lyra](https://wiki.luckfox.com/Luckfox-Lyra/) (Rockchip RK3506) with:

- ILI9341 SPI display (320×240) + TSC2046 resistive touch
- QMK keyboard connected over UART2 (HID bridge → uinput)
- MAX98357A I2S audio
- SD-over-SPI expansion slot

Everything custom lives in `userpatches/` (the official Armbian out-of-tree customization mechanism). The Armbian build framework is a git submodule — no fork to maintain.

## Layout

| Path | What |
|---|---|
| `build/` | git submodule → [armbian/build](https://github.com/armbian/build) |
| `userpatches/config/boards/bit0.conf` | board definition (base Lyra is not upstream in Armbian) |
| `userpatches/kernel/rk35xx-vendor-6.1/` | kernel patches: bit0 DTS, ILI9341 fbdev driver, ads7846 tuning |
| `userpatches/overlay/` | rootfs files: input daemons, bit0 UI, systemd units |
| `userpatches/customize-image.sh` | image chroot hook: apt packages, service enablement |
| `scripts/build.sh` | build wrapper (run on a supported host, see below) |
| `docs/` | porting notes, pico-8 install guide, launcher UI guide (`UI.md`: adding apps, icons/sprites, mascots) |

## Building

Requires a native Ubuntu 24.04 x86_64 host (WSL2 works, no Docker needed):

```bash
git clone --recurse-submodules <this repo>
cd bit0-armbian
./scripts/build.sh KERNEL_GIT=shallow
```

The finished SD card image lands in `build/output/images/`. Flash it with
balenaEtcher or Rufus — the image contains the full GPT layout including
U-Boot, no extra flashing tools required. On WSL, copy the image to the
Windows side first if you flash from there. Serial console for debugging:
`ttyFIQ0` @ 1500000.

Note: always clone/build on the Linux filesystem (`~`), never under `/mnt/c` —
the rootfs build needs real ext4 semantics and 9P is painfully slow.

## Security posture

This is a development handheld: the USB OTG port runs an **unauthenticated
adb daemon as root** — anyone with a cable gets a root shell. That's
intentional (it replaces the old serial console). To disable it, create
`/boot/bit0-no-adb` on the device and reboot. Provenance and checksum of the
adbd binary are recorded in `docs/BINARIES.md` and verified at image build.

## Origin

Ported from the private Luckfox Buildroot SDK. See `docs/PORTING-NOTES.md` for
the mapping of what came from where.
