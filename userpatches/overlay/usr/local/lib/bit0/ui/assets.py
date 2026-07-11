"""Bitmap asset loading for the launcher UI (audit 6.1/6.3).

Icons are plain (P1) PBM files - an ASCII 0/1 grid, hand-editable in any
editor like the old in-code ASCII art - under /usr/local/share/bit0/icons/
(override with BIT0_ICONS_DIR for bench testing). Parsed with stdlib only
and cached. A missing or garbage file degrades to None and the caller
falls back to text or a built-in shape - an asset must never take the
boot UI down.
"""

import os

ICONS_DIR = os.environ.get('BIT0_ICONS_DIR', '/usr/local/share/bit0/icons')

_cache = {}


def parse_pbm(text):
    """Plain-PBM (P1) -> list of '#'/' ' row strings (the format the
    drawing code has always used). Raises ValueError on garbage."""
    tokens = []
    for line in text.splitlines():
        tokens += line.split('#', 1)[0].split()  # strip PBM comments
    if not tokens or tokens[0] != 'P1':
        raise ValueError('not a plain PBM (P1)')
    w, h = int(tokens[1]), int(tokens[2])
    bits = ''.join(tokens[3:])
    if w <= 0 or h <= 0 or len(bits) < w * h:
        raise ValueError('truncated PBM')
    return [''.join('#' if bits[r * w + c] == '1' else ' '
                    for c in range(w)) for r in range(h)]


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
