# Binary provenance

Policy (see `audit.md`): nothing binary is committed if it can be built from
source in this repo — buildable artifacts are generated inside the image chroot
by `customize-image.sh`. The exceptions are third-party blobs that cannot be
rebuilt here; each one is recorded below with origin, license, and a sha256
that `customize-image.sh` verifies at build time (mismatch fails the build).

## `userpatches/overlay/usr/local/bin/adbd`

| | |
|---|---|
| What | ADB daemon serving the USB gadget (`bit0-usb-gadget.service`) |
| Origin | Transplanted from the private Luckfox Lyra Buildroot SDK image (Rockchip's prebuilt adbd for RK3506; see `docs/PORTING-NOTES.md`) |
| Upstream | AOSP `adbd` as packaged by Rockchip/Buildroot |
| License | Apache-2.0 (AOSP) |
| Format | ELF 32-bit armhf, dynamically linked (glibc), stripped |
| Runtime deps | `libcrypto.so.3` — provided by `libssl3t64`, installed by `customize-image.sh` |
| sha256 | `e1a298ce71ed76c572ef87cea84e0f4c6a8f39079777dbcd0077cb4251b85e8f` |

Note: this adbd performs **no authentication** — any USB host gets a root
shell. That is the intended development posture of the Bit0; see the security
note in the README.

If the file is ever replaced (e.g. rebuilt from Rockchip's buildroot package),
update the sha256 both here and in `ADBD_SHA256` in
`userpatches/customize-image.sh`.

## Not in this repo at all

- **PICO-8** (`pico8_dyn`, `pico8.dat`, carts) — proprietary, gitignored under
  `userpatches/overlay/root/pico-8/`; see `docs/PICO8.md`.
