# Bit0 launcher UI — contributor guide

The launcher is the menu you see on the Bit0's 320×240 screen. This
guide explains how the code is organized and how to do the three most
common jobs — **add an app to the menu**, **edit an icon**, and **add or
edit a mascot**.

Everything below lives in `userpatches/overlay/`, which is copied
verbatim into the image at build time. Paths in this document are the
*target* paths (what you see on a running device); prefix them with
`userpatches/overlay/` when editing in the repo.

During development you don't need to rebuild the image: with the device
connected over USB, `./scripts/push-launcher.sh` pushes the launcher,
libraries, and all assets, then restarts the UI.

## The screen

- 320 × 240 pixels, RGB565 color, drawn directly to `/dev/fb0`.
- The panel hangs off a slow SPI link — a full frame is ~150 KB — so the
  UI redraws only what changed. If you add drawing code, follow the rule
  documented in `ui/core.py`: widgets compose into the scene buffer and
  never write to the framebuffer themselves.
- Text uses a built-in 5×7 pixel font. Only these characters exist:
  **uppercase A–Z, digits 0–9, and `. - + % / _` (plus lowercase
  `i`/`t`)**. Keep app labels, mascot names, and mascot messages inside
  that set — unknown characters render as blanks.

## File structure

```
/usr/local/bin/bit0-launcher          entry point: startup guards, page
                                      construction, input/render loop
/usr/local/lib/bit0/
  fb.py          framebuffer: scene buffer, text rendering, cursor
  evdev.py       input-device constants and IO (shared with the daemons)
  apps.py        app launching, volume/brightness helpers
  registry.py    loads the TOML app registry (below)
  state.py       persistent device state (/var/lib/bit0/state.json)
  ui/
    core.py      Widget / Page / Router (focus ring, page stack)
    widgets.py   Button, Slider, Tile, AppGrid, layout helpers
    assets.py    PBM/PGM icon parser + cache, the 5x7 font
    theme.py     theme.json loading and defaults
    mascot.py    mascot widget, speech bubble, first-boot chooser
/usr/local/share/bit0/
  theme.json     all colors, sizes, toggles, splash and mascot text
  apps/          one .toml file per main-menu app entry
  icons/         UI icons (.pbm/.pgm, plain-text bitmaps)
  mascots/       one directory per mascot
```

Two rules keep the system robust, and your changes should preserve them:

1. **Assets and registry entries are data.** Adding an app, icon, or
   mascot never requires a code change.
2. **Broken data never breaks the boot.** A bad TOML file or corrupt
   bitmap logs a warning and is skipped; the launcher falls back to a
   built-in default. If your new file doesn't show up, check the logs:
   `adb shell journalctl -u bit0-launcher -n 50`.

## Adding an app to the main menu

Drop one TOML file into `/usr/local/share/bit0/apps/`. The leading
number in the filename sets the menu order (built-ins: TERMINAL = 10,
SD CARD = 90).

```toml
# 40-doom.toml
label      = "DOOM"                     # tile text (see font charset above)
exec       = ["/usr/local/bin/doom-launch"]   # argv list, never a shell string
requires   = "/root/doom/doom.wad"      # optional: if missing, the launcher
                                        # shows "DOOM NOT INSTALLED" instead
                                        # of a broken launch
icon       = "doom.pbm"                 # optional: file in the icons dir;
                                        # without it the tile shows the label
kill_stale = ["doom"]                   # optional: process names killed
                                        # before launching (single-stream
                                        # audio: an orphan mutes everything)
```

That's it. The main menu shows 3 tiles per page and grows paging arrows
automatically when there are more entries.

## Icon and sprite files

All bitmaps are **plain-text Netpbm** files you can edit in any text
editor, and every real pixel-art tool can export them (GIMP exports
P1/P2 directly; from Aseprite/Piskel export PNG and convert with
`magick sprite.png -compress none sprite.pbm` or GIMP).

- **`.pbm` (P1)** — 1-bit. `1` = pixel on (drawn in the theme's text
  color), `0` = transparent.
- **`.pgm` (P2)** — used when an asset needs two tones plus
  transparency. Convention: `0` = transparent, low half = dark,
  high half = light. The cursor is the example: `2` (light) fill with
  `1` (dark) outline, maxval 2.

Format by example (`#` comments are allowed):

```
P1
# 4x3 example: a hollow box
4 3
1 1 1 1
1 0 0 1
1 1 1 1
```

### Pixel budgets

Icons are drawn 1:1 (no scaling) and centered in their box. These are
the boxes as configured by the default `theme.json`; "budget" is the
largest size that fits without touching the border, and "shipped" shows
what the current assets use as a reference for visual weight.

| Asset | File(s) | Box (px) | Budget (px) | Shipped |
|---|---|---|---|---|
| App tile icon | `icons/<name>.pbm` (named in the app's TOML) | 80×80 tile, 2 px border | **≤ 72×72**, ~40–56 looks right | — (tiles currently use text labels) |
| Settings gear | `icons/gear.pbm` | 30×26 button | **≤ 24×20** | 13×13 |
| Back arrow | `icons/back.pbm` | 30×26 button | **≤ 24×20** | 13×12 |
| Grid paging arrows | `icons/left.pbm`, `icons/right.pbm` | 20 px-wide zone | **≤ 16×72** (keep it small) | 7×13 |
| Mouse cursor | `icons/cursor.pgm` | — | keep near shipped size | 8×12 |
| Mascot sprite | `mascots/<id>/idle.pbm` etc. | 60×60 box, 1 px border | **≤ 56×56** | 31×25, 29×20 |
| Splash logo | any name, set as `splash.logo` in theme.json | full screen | **≤ 300×150** practical | — |

Notes:

- The mascot's `idle` sprite is also shown on the first-boot chooser
  card, which has more room — but the 60×60 sprite box is the binding
  constraint, so stay ≤ 56×56.
- Icons inherit their color from the theme (white on the default
  theme, inverted when a tile/button is highlighted). Multi-color
  sprites aren't supported yet; if you need one, that's the build-time
  PNG→RGB565 path reserved in audit 6.3 — ask before inventing a new
  mechanism.

## Mascots

A mascot is a directory under `/usr/local/share/bit0/mascots/`:

```
mascots/
  robo/
    mascot.toml     name = "ROBO"      (uppercase, font charset)
    idle.pbm        required, <= 56x56
    talk.pbm        optional: mouth-open frame; if present the mascot
                    animates automatically while speaking
    blink.pbm       optional: eyes-closed frame; enables idle blinking
    happy.pbm       optional: any other name becomes an emotion usable
                    from code via mascot.say([...], emotion="happy")
```

Adding a directory adds the mascot to the pool.

### Device state and onboarding

Runtime configuration lives in `/var/lib/bit0/state.json` (never part
of the image — a fresh flash has no file, which *is* the first-boot
signal):

```json
{
  "user_name": "PEPE",     // used by the {USER} placeholder, may be ""
  "mascot": "pixel",       // chosen mascot id (directory name)
  "onboarded": true        // false/missing -> onboarding runs at boot
}
```

While `onboarded` is false the launcher boots into the **CHOOSE YOUR
MASCOT** screen; picking one saves the state and plays the onboarding
script from `theme.json` (`mascot.onboarding`) as *modal* messages.
Message lists support `{USER}` and `{MASCOT}` placeholders; an empty
user name drops the token cleanly ("HI {USER}." becomes "HI.").

To re-run onboarding during development:
`adb shell rm /var/lib/bit0/state.json` and restart the launcher.
There is no name-entry screen yet — set `user_name` by editing the
JSON (uppercase, font charset).

The speech bubble draws itself and wraps text — there is no bubble
asset. The mascot's greeting and its resting phrases ("IM HERE." etc.)
are plain text in `theme.json` under `mascot`.

Messages come in two classes (`mascot.say(msgs, modal=...)`):

- **Modal** (`modal=True`, e.g. the first-boot onboarding): locks the
  UI — the page above the mascot band is darkened, every key and click
  is captured (ENTER/SPACE/click advance, ESC skips the queue).
- **Casual** (the default, for personality/flavor lines): never blocks
  anything; each message auto-dismisses after a delay scaled by its
  length (~2.5–7 s), or earlier if the user clicks the bubble itself.

## Theme

`/usr/local/share/bit0/theme.json` holds every color (RGB565 as
`"0xFD20"` strings), the layout metrics (tile size and count per page,
button sizes, the 66 px mascot band), the splash screen (text, colors,
duration — `"duration_s": 0` skips it, `logo` names an icon file), and
the mascot text. Every key is validated one by one: a typo falls back
to the built-in default with a log line rather than breaking the boot.

## Testing your change

```sh
python3 -m py_compile userpatches/overlay/usr/local/bin/bit0-launcher   # if you touched code
./scripts/push-launcher.sh        # push everything + restart the UI
adb shell journalctl -u bit0-launcher -f   # watch for "skipping ..." warnings
```

For bench-testing asset/registry parsing off-device, the loaders honor
`BIT0_ICONS_DIR`, `BIT0_APPS_DIR`, `BIT0_MASCOTS_DIR`, and `BIT0_THEME`
environment variable overrides.
