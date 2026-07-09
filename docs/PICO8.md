# PICO-8 on the Bit0 (Armbian)

PICO-8 is proprietary (lexaloffle.com) and is **never committed to this
repository** — `userpatches/overlay/root/pico-8/` is gitignored. Everything
else (launch logic, GL workarounds, the stretch shim) ships in the image, so
"installing pico-8" is nothing more than copying your licensed
**Raspberry Pi** build (`pico8_dyn` + `pico8.dat`, plus your carts/config):

## Option A — bake into the image (build-time)

Place the files at `userpatches/overlay/root/pico-8/` before running
`./scripts/build.sh`. customize-image.sh detects and ships them; absent, it
skips cleanly and the launcher shows PICO-8 NOT INSTALLED.

## Option B — push to a running device (no rebuild)

```bash
./scripts/install-pico8.sh /path/to/unpacked/pico-8
```

The launcher's PICO-8 button works immediately.

---

## How it works (and why) — the debugging story

The launcher runs `/usr/local/bin/pico8-launch`, which is the product of a
long on-device debugging session. The RK3506 has **no GPU**, and the display
is a DRM device (`panel-mipi-dbi`). The chain that works:

1. **SDL kmsdrm + Mesa software GL.** Debian SDL2's kmsdrm backend cannot
   present frames without EGL. The image ships `libgl1-mesa-dri` (kms_swrast
   + llvmpipe), `libegl1`, `libgles2`; `LIBGL_ALWAYS_SOFTWARE=1` selects the
   CPU renderer. (Verified healthy end-to-end with a standalone EGL smoke
   test: clear-to-red reached the panel.)

2. **`-pixel_perfect 1` and `SDL_RENDER_DRIVER=opengles2`, never
   `pixel_perfect 0`.** At `pixel_perfect 0` the raspi build switches to its
   own "rpi" blitter, which calls desktop-GL functions on a GLES2 context —
   `glEnable(GL_TEXTURE_2D)`, `glTexImage2D(GL_BGRA, UNSIGNED_INT_8_8_8_8_REV)`.
   The Pi's Broadcom driver tolerates that; Mesa's strict GLES2 rejects every
   call (`MESA_DEBUG=1` shows the GL_INVALID_ENUM storm) and the screen stays
   black — it even segfaults if EGL is missing entirely. The SDL-renderer
   path (`pixel_perfect 1`) uses SDL's own battle-tested GLES2 code and works.

3. **`pico8-stretch.so` (LD_PRELOAD).** The surviving path integer-scales:
   on a 240-px-tall panel that's 1× = a tiny 128×128 square. The shim
   (source: `userpatches/overlay/usr/local/src/pico8-stretch.c`) intercepts
   `SDL_RenderCopy` and rewrites the destination rect of pico-8's 128×128
   back-page texture. Geometry comes from `PICO8_DRAW_RECT` ("x,y,w,h"):
   - default `40,0,240,240` — square pixels, centered, thin side bars
   - `0,0,320,240` — full-stretch (slightly wide pixels)
   Set it in `pico8-launch` or the environment to taste.

   The `.so` is never committed: `customize-image.sh` compiles it inside the
   image chroot (gcc is installed for the build and purged again). The source
   also ships on-device at `/usr/local/src/pico8-stretch.c`, so with gcc
   installed it can be rebuilt there:
   `gcc -O2 -shared -fPIC -o /usr/local/lib/pico8-stretch.so /usr/local/src/pico8-stretch.c -ldl`

Audio goes through the asound.conf softvol chain (launcher VOL buttons and
keyboard volume keys work inside pico-8). Input: the uinput keyboard/mouse
devices are read by SDL directly. Carts from the SPI SD card are cached in
`/root/pico-8/carts/sdcard/` by the launcher's SD CARD flow, which launches
them through the same `pico8-launch -run <cart>`.
