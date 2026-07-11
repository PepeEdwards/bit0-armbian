"""Bitmap asset loading + font for the launcher UI (audit 6.1/6.3).

Icons are plain (P1) PBM files - an ASCII 0/1 grid, hand-editable in any
editor like the old in-code ASCII art - under /usr/local/share/bit0/icons/
(override with BIT0_ICONS_DIR for bench testing). Two-tone assets that
need a mid tone (the cursor's white fill) are plain (P2) PGM files with
the convention 0 = transparent, low half = dark '#', high half = light
'*'. Parsed with stdlib only and cached. A missing or garbage file
degrades to None and the caller falls back to text or a built-in shape -
an asset must never take the boot UI down.

The 5x7 font lives here too (moved out of fb.py): editing assets no
longer means editing the drawing module.
"""

import os

ICONS_DIR = os.environ.get('BIT0_ICONS_DIR', '/usr/local/share/bit0/icons')

_cache = {}


def parse_pbm(text):
    """Plain PBM (P1) or PGM (P2) -> list of row strings in the format
    the drawing code has always used: ' ' transparent, '#' dark, '*'
    light. Raises ValueError on garbage."""
    tokens = []
    for line in text.splitlines():
        tokens += line.split('#', 1)[0].split()  # strip comments
    if not tokens or tokens[0] not in ('P1', 'P2'):
        raise ValueError('not a plain PBM/PGM (P1/P2)')
    if tokens[0] == 'P1':
        w, h = int(tokens[1]), int(tokens[2])
        vals = ''.join(tokens[3:])
        if w <= 0 or h <= 0 or len(vals) < w * h:
            raise ValueError('truncated PBM')
        return [''.join('#' if vals[r * w + c] == '1' else ' '
                        for c in range(w)) for r in range(h)]
    w, h, maxv = int(tokens[1]), int(tokens[2]), int(tokens[3])
    vals = [int(v) for v in tokens[4:]]
    if w <= 0 or h <= 0 or maxv <= 0 or len(vals) < w * h:
        raise ValueError('truncated PGM')

    def ch(v):
        return ' ' if v == 0 else ('#' if v <= maxv // 2 else '*')

    return [''.join(ch(vals[r * w + c]) for c in range(w)) for r in range(h)]


def load_icon(name):
    """Icon rows by filename (cached); None if missing or invalid."""
    if name not in _cache:
        rows = None
        try:
            with open(os.path.join(ICONS_DIR, name)) as f:
                rows = parse_pbm(f.read())
        except (OSError, ValueError, IndexError) as exc:
            print(f'bit0 ui: icon {name}: {exc}', flush=True)
        _cache[name] = rows
    return _cache[name]


# In-code fallbacks so navigation survives missing/broken icon files
# (the .pbm in the icons dir is the editable authority).
GEAR_FALLBACK = [
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

BACK_FALLBACK = [
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
