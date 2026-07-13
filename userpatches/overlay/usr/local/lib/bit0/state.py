"""Persistent device/UI state (audit 6.5.2).

/usr/local/share/bit0/state.json (override with BIT0_STATE) holds the
configuration the UI accumulates at runtime - the user's name, the
chosen mascot, and whether onboarding already ran. The overlay ships
the file next to theme.json, pre-populated with only the defaults that
drive first boot (mascot + onboarded: false), so it is always there
and easy to find and hand-edit; the launcher rewrites it in place as
the user onboards.

Every key is type-checked individually against DEFAULTS, so a
hand-edited or truncated file degrades per key instead of crashing the
boot UI. Writes are atomic (tmp file + fsync + rename): a power cut
mid-write must never leave 0xFF flash garbage where the state was.
"""

import json
import os

STATE_PATH = os.environ.get('BIT0_STATE', '/usr/local/share/bit0/state.json')

DEFAULTS = {
    'user_name': '',     # shown via the {USER} placeholder in messages
    'mascot': '',        # chosen mascot id (directory name)
    'onboarded': False,  # False -> chooser + modal onboarding on boot
}


def load():
    """State dict (a copy of DEFAULTS overlaid with valid stored keys).
    A missing or unreadable file means pure defaults, which re-runs
    onboarding. Never raises."""
    st = dict(DEFAULTS)
    try:
        with open(STATE_PATH) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError('top level must be an object')
        for k, d in DEFAULTS.items():
            v = data.get(k, d)
            if type(v) is type(d):
                st[k] = v
            else:
                print(f'bit0 state: {k}: bad value {v!r}; using default',
                      flush=True)
    except (OSError, ValueError) as exc:
        print(f'bit0 state: {STATE_PATH}: {exc}; using defaults', flush=True)
    return st


def save(st):
    """Atomic persist: tmp + fsync + rename, so an unclean power-off
    can only ever leave the old file or the new one, never garbage."""
    try:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        tmp = STATE_PATH + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(st, f, indent=2)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, STATE_PATH)
    except OSError as exc:
        print(f'bit0 state: cannot persist: {exc}', flush=True)
