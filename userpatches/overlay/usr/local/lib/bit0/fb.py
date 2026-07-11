"""Framebuffer drawing for the Bit0 launcher: RGB565 scene buffer, 5x7
bitmap font, cursor/icons. No DirectFB/SDL dependency, so it coexists with
whatever the launched apps use."""

import functools
import struct

from .evdev import fb_size

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

# ── 5x7 font as ASCII art (6th column = spacing) ────────────────────────────
FONT = {
    'A': [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    'B': ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    'C': [" ####", "#    ", "#    ", "#    ", "#    ", "#    ", " ####"],
    'D': ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    'E': ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    'G': [" ####", "#    ", "#    ", "#  ##", "#   #", "#   #", " ####"],
    'H': ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    'I': [" ### ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    'L': ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    'M': ["#   #", "## ##", "# # #", "# # #", "#   #", "#   #", "#   #"],
    'N': ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    'O': [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    'P': ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    'R': ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    'S': [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    'T': ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    'U': ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    'W': ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
    'F': ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    'J': ["  ###", "   # ", "   # ", "   # ", "   # ", "#  # ", " ##  "],
    'K': ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    'Q': [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    'V': ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    'X': ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    'Y': ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    'Z': ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    '1': ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", " ### "],
    '2': [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    '3': [" ### ", "#   #", "    #", "  ## ", "    #", "#   #", " ### "],
    '4': ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    '5': ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    '6': [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    '7': ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    '9': [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    '_': ["     ", "     ", "     ", "     ", "     ", "     ", "#####"],
    '/': ["    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "],
    '0': [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    '8': [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    '-': ["     ", "     ", "     ", "#####", "     ", "     ", "     "],
    '+': ["     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "],
    '%': ["##   ", "##  #", "   # ", "  #  ", " #   ", "#  ##", "   ##"],
    '.': ["     ", "     ", "     ", "     ", "     ", "     ", "  #  "],
    'i': ["  #  ", "     ", " ##  ", "  #  ", "  #  ", "  #  ", " ### "],
    't': ["  #  ", "  #  ", "#####", "  #  ", "  #  ", "  #  ", "   ##"],
    ' ': ["     ", "     ", "     ", "     ", "     ", "     ", "     "],
}
GLYPH_W, GLYPH_H = 6, 7


@functools.lru_cache(maxsize=1024)
def _glyph_blits(ch, scale, color):
    """Pre-rendered opaque spans for one glyph at (scale, color): a list of
    (dy_px, dx_px, row_bytes) blitted with slice assignment. Only set pixels
    get spans, so text stays transparent over any background."""
    px = struct.pack('<H', color)
    blits = []
    for gy, line in enumerate(FONT.get(ch, FONT[' '])):
        gx = 0
        while gx < len(line):
            if line[gx] != '#':
                gx += 1
                continue
            start = gx
            while gx < len(line) and line[gx] == '#':
                gx += 1
            row = px * ((gx - start) * scale)
            for sy in range(scale):
                blits.append(((gy * scale + sy), start * scale, row))
    return blits

ARROW = [
    "#       ",
    "##      ",
    "#*#     ",
    "#**#    ",
    "#***#   ",
    "#****#  ",
    "#*****# ",
    "#******#",
    "#***####",
    "#*#**#  ",
    "## #**# ",
    "#   ##  ",
]
CUR_W, CUR_H = 8, 12

GEAR_ICON = [
    "     ###     ",
    "     ###     ",
    "   #######   ",
    "  #########  ",
    "  #########  ",
    "#####   #####",
    "#####   #####",
    "#####   #####",
    "  #########  ",
    "  #########  ",
    "   #######   ",
    "     ###     ",
    "     ###     ",
]

BACK_ICON = [
    "     #       ",
    "    ##       ",
    "   ###       ",
    "  ####       ",
    " ############",
    "#############",
    "#############",
    " ############",
    "  ####       ",
    "   ###       ",
    "    ##       ",
    "     #       ",
]


class Screen:
    def __init__(self):
        self.w, self.h = fb_size()
        self.fb = open(FBDEV, 'r+b', buffering=0)
        self.scene = bytearray(self.w * self.h * 2)

    def fill_rect(self, x, y, w, h, color):
        px = struct.pack('<H', color)
        row = px * w
        for r in range(y, y + h):
            off = (r * self.w + x) * 2
            self.scene[off:off + w * 2] = row

    def text(self, s, x, y, scale, color):
        for ch in s:
            for dy, dx, row in _glyph_blits(ch, scale, color):
                off = ((y + dy) * self.w + x + dx) * 2
                self.scene[off:off + len(row)] = row
            x += GLYPH_W * scale

    def text_width(self, s, scale):
        return len(s) * GLYPH_W * scale

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
        """Composite arrow over scene into a temp patch, write only that."""
        for gy, line in enumerate(ARROW):
            ry = cy + gy
            if not (0 <= ry < self.h):
                continue
            off = (ry * self.w + cx) * 2
            n = min(CUR_W, self.w - cx)
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
        self.flush(cx, min(cy, self.h - 1),
                   min(CUR_W, self.w - cx), min(CUR_H, self.h - cy))


def fullscreen_message(scr, msg):
    scr.fill_rect(0, 0, scr.w, scr.h, C_BLACK)
    s = 2
    tw = scr.text_width(msg, s)
    scr.text(msg, (scr.w - tw) // 2, (scr.h - GLYPH_H * s) // 2, s, C_WHITE)
    scr.flush()
