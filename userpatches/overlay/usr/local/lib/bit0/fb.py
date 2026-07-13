"""Framebuffer drawing for the Bit0 launcher: RGB565 scene buffer, text
rendering, cursor. No DirectFB/SDL dependency, so it coexists with
whatever the launched apps use. Font/icon data lives in bit0.ui.assets
(audit 6.3); the default C_* colors survive here for standalone drawing
(fullscreen_message) - widgets style themselves from bit0.ui.theme."""

import functools
import struct

from .evdev import fb_size
from .ui.assets import FONT

FBDEV = '/dev/fb0'

# ── colors (RGB565) ──────────────────────────────────────────────────────────
C_BG     = 0x18C3  # dark gray
C_TITLE  = 0xFD20  # orange
C_BTN    = 0x39E7  # button face
C_BTNHI  = 0xFD20  # hovered button face
C_TEXT   = 0xFFFF
C_TEXTHI = 0x0000
C_BLACK  = 0x0000
C_WHITE  = 0xFFFF

GLYPH_W, GLYPH_H = 6, 7


@functools.lru_cache(maxsize=1024)
def _glyph_blits(ch, scale, color):
    """Pre-rendered opaque spans for one glyph at (scale, color): a list of
    (dy_px, dx_px, row_bytes) blitted with slice assignment. Only set pixels
    get spans, so text stays transparent over any background. scale may be
    fractional (e.g. 1.5): glyph pixels map to rounded bounds, so identical
    to the integer path when scale is whole."""
    px = struct.pack('<H', color)
    blits = []
    for gy, line in enumerate(FONT.get(ch, FONT[' '])):
        y0, y1 = round(gy * scale), round((gy + 1) * scale)
        gx = 0
        while gx < len(line):
            if line[gx] != '#':
                gx += 1
                continue
            start = gx
            while gx < len(line) and line[gx] == '#':
                gx += 1
            x0 = round(start * scale)
            row = px * (round(gx * scale) - x0)
            for sy in range(y0, y1):
                blits.append((sy, x0, row))
    return blits

class Screen:
    def __init__(self):
        self.w, self.h = fb_size()
        self.fb = open(FBDEV, 'r+b', buffering=0)
        self.scene = bytearray(self.w * self.h * 2)
        # cursor comes from icons/cursor.pgm via set_cursor at startup;
        # until then (or if the asset is missing) there is simply none
        self.cursor = None
        self.cur_w = self.cur_h = 0

    def set_cursor(self, rows):
        """Cursor sprite as ' '/'#'/'*' rows (the assets.parse_pbm PGM
        format); None/empty keeps the current one."""
        if rows:
            self.cursor = rows
            self.cur_w, self.cur_h = len(rows[0]), len(rows)

    def fill_rect(self, x, y, w, h, color):
        px = struct.pack('<H', color)
        row = px * w
        for r in range(y, y + h):
            off = (r * self.w + x) * 2
            self.scene[off:off + w * 2] = row

    def text(self, s, x, y, scale, color):
        adv = round(GLYPH_W * scale)
        for ch in s:
            for dy, dx, row in _glyph_blits(ch, scale, color):
                off = ((y + dy) * self.w + x + dx) * 2
                self.scene[off:off + len(row)] = row
            x += adv

    def text_width(self, s, scale):
        return len(s) * round(GLYPH_W * scale)

    def dim(self, y0, y1):
        """Darken scene rows [y0, y1) to ~50%: RGB565 halving via
        (v >> 1) & 0x7BEF on every pixel. Done as one big-int shift +
        mask over the contiguous region (little-endian keeps the u16s
        adjacent; the mask's cleared top bit drops the neighbor's
        carried-in LSB), so it runs at C speed on the Cortex-A7."""
        a, b = y0 * self.w * 2, y1 * self.w * 2
        buf = self.scene[a:b]
        mask = int.from_bytes(b'\xef\x7b' * (len(buf) // 2), 'little')
        n = (int.from_bytes(buf, 'little') >> 1) & mask
        self.scene[a:b] = n.to_bytes(len(buf), 'little')

    def flush(self, x=0, y=0, w=None, h=None):
        w = self.w if w is None else w
        h = self.h if h is None else h
        if x == 0 and w == self.w:
            # full-width region is contiguous: one write, no partial states
            off = y * self.w * 2
            self.fb.seek(off)
            self.fb.write(self.scene[off:off + h * self.w * 2])
            return
        for r in range(y, y + h):
            off = (r * self.w + x) * 2
            self.fb.seek(off)
            self.fb.write(self.scene[off:off + w * 2])

    def draw_cursor(self, cx, cy):
        """Composite the cursor over scene into a temp patch, write only
        that. No-op until a cursor sprite is set (icons/cursor.pgm)."""
        if not self.cursor:
            return
        for gy, line in enumerate(self.cursor):
            ry = cy + gy
            if not (0 <= ry < self.h):
                continue
            off = (ry * self.w + cx) * 2
            n = min(self.cur_w, self.w - cx)
            patch = bytearray(self.scene[off:off + n * 2])
            for gx in range(n):
                c = line[gx]
                if c == '#':
                    patch[gx * 2:gx * 2 + 2] = struct.pack('<H', C_BLACK)
                elif c == '*':
                    patch[gx * 2:gx * 2 + 2] = struct.pack('<H', C_WHITE)
            self.fb.seek(off)
            self.fb.write(patch)

    def erase_cursor(self, cx, cy):
        if not self.cursor:
            return
        self.flush(cx, min(cy, self.h - 1),
                   min(self.cur_w, self.w - cx), min(self.cur_h, self.h - cy))


def fullscreen_message(scr, msg):
    scr.fill_rect(0, 0, scr.w, scr.h, C_BLACK)
    s = 2
    tw = scr.text_width(msg, s)
    scr.text(msg, (scr.w - tw) // 2, (scr.h - GLYPH_H * s) // 2, s, C_WHITE)
    scr.flush()
