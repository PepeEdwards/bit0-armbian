"""Launcher styling from one JSON file (audit 6.3).

/usr/local/share/bit0/theme.json (override with BIT0_THEME) holds colors
(RGB565 as "0xFD20" strings), metrics (tile size/gap, button geometry,
mascot strip height), feature toggles, and the whole splash screen.
Restyling or re-skinning the launcher = editing that one file in the
overlay; no widget hardcodes a color or size.

Loaded once at startup into the module singleton. Every key is validated
individually and falls back to its built-in default on missing/garbage
values - a hand-edited theme must never take the boot UI down; worst
case it logs and looks default.
"""

import json
import os
from dataclasses import dataclass, field

THEME_PATH = os.environ.get('BIT0_THEME', '/usr/local/share/bit0/theme.json')


@dataclass
class Theme:
    # colors (RGB565)
    bg: int = 0x18C3
    title: int = 0xFD20
    btn: int = 0x39E7
    btn_hi: int = 0xFD20
    text: int = 0xFFFF
    text_hi: int = 0x0000
    border: int = 0xFFFF
    # metrics
    tile_size: int = 80
    tile_gap: int = 14
    tiles_per_page: int = 3
    tile_label_scale_max: float = 1.5
    button_w: int = 260
    button_max_h: int = 48
    slider_h: int = 24
    mascot_strip: int = 66    # main-page bottom band for the mascot's
                              # sprite box + dialogue box (6.5)
    # feature toggles
    page_dots: bool = False   # AppGrid page indicator (unimplemented in v1)
    typewriter: bool = False  # mascot bubble reveal (6.5)
    # splash screen ([splash] section; duration_s 0 skips it entirely)
    splash_text: str = 'Bit-0'
    splash_duration_s: float = 2.2
    splash_font_scale: float = 6.0
    splash_text_color: int = 0xFFFF
    splash_bar_color: int = 0xFD20
    splash_bg_color: int = 0x0000
    splash_logo: str = ''     # icon filename drawn above/instead of the text
    # mascot ([mascot] section, 6.5). {USER}/{MASCOT} placeholders are
    # substituted from the device state (bit0.state) and mascot name.
    # onboarding: modal script after the first-boot chooser (6.5.2);
    # greeting: casual messages once per regular boot.
    mascot_enabled: bool = True
    mascot_onboarding: list = field(default_factory=lambda: [
        'HI {USER}. I AM {MASCOT}.',
        'WELCOME TO YOUR BIT-0.',
        'USE THE ARROWS OR THE TOUCH SCREEN TO MOVE AROUND.',
        'PRESS ENTER OR TAP A TILE TO LAUNCH AN APP.',
        'THE GEAR ON THE TOP RIGHT OPENS THE SETTINGS.',
        'PRESS SPACE OR CLICK TO CONTINUE. ESC SKIPS ME.'])
    mascot_greeting: list = field(default_factory=lambda: [
        'HELLO AGAIN {USER}.', 'PICK AN APP TO START.'])
    # resting phrases: the bubble never empties, it rotates through these
    # when the message queue runs out (empty list = bubble hides instead)
    mascot_idle: list = field(default_factory=lambda: [
        'IM HERE.', 'IM WAITING...', 'LET ME KNOW.'])


def _color(v):
    if isinstance(v, str):
        v = int(v, 16)
    if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v <= 0xFFFF:
        raise ValueError(f'not an RGB565 color: {v!r}')
    return v


def _num(v):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or v < 0:
        raise ValueError(f'not a non-negative number: {v!r}')
    return v


def _int(v):
    return int(_num(v))


def _bool(v):
    if not isinstance(v, bool):
        raise ValueError(f'not a boolean: {v!r}')
    return v


def _str(v):
    if not isinstance(v, str):
        raise ValueError(f'not a string: {v!r}')
    return v


def _strlist(v):
    if not isinstance(v, list) or not all(isinstance(s, str) for s in v):
        raise ValueError(f'not a list of strings: {v!r}')
    return v


# json section -> key -> (Theme attribute, validator)
_SCHEMA = {
    'colors': {k: (k, _color) for k in
               ('bg', 'title', 'btn', 'btn_hi', 'text', 'text_hi', 'border')},
    'metrics': {k: (k, _int) for k in
                ('tile_size', 'tile_gap', 'tiles_per_page', 'button_w',
                 'button_max_h', 'slider_h', 'mascot_strip')}
    | {'tile_label_scale_max': ('tile_label_scale_max', _num)},
    'features': {'page_dots': ('page_dots', _bool),
                 'typewriter': ('typewriter', _bool)},
    'mascot': {'enabled': ('mascot_enabled', _bool),
               'onboarding': ('mascot_onboarding', _strlist),
               'greeting': ('mascot_greeting', _strlist),
               'idle': ('mascot_idle', _strlist)},
    'splash': {
        'text': ('splash_text', _str),
        'duration_s': ('splash_duration_s', _num),
        'font_scale': ('splash_font_scale', _num),
        'text_color': ('splash_text_color', _color),
        'bar_color': ('splash_bar_color', _color),
        'bg_color': ('splash_bg_color', _color),
        'logo': ('splash_logo', _str),
    },
}

_current = Theme()


def current():
    return _current


def load(path=THEME_PATH):
    """Parse the theme file into the module singleton. Unknown sections/
    keys and invalid values log and are skipped; a missing or unparsable
    file leaves every default in place. Never raises."""
    global _current
    t = Theme()
    _current = t
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError('top level must be an object')
    except (OSError, ValueError) as exc:
        print(f'bit0 theme: {path}: {exc}; using defaults', flush=True)
        return t
    for sec, items in data.items():
        schema = _SCHEMA.get(sec)
        if schema is None or not isinstance(items, dict):
            print(f'bit0 theme: ignoring unknown section {sec!r}', flush=True)
            continue
        for key, val in items.items():
            spec = schema.get(key)
            if spec is None:
                print(f'bit0 theme: ignoring unknown key {sec}.{key}',
                      flush=True)
                continue
            attr, validate = spec
            try:
                setattr(t, attr, validate(val))
            except (ValueError, TypeError) as exc:
                print(f'bit0 theme: {sec}.{key}: {exc}; keeping default',
                      flush=True)
    return t
