"""Data-driven app registry for the launcher main menu (audit 6.1).

One TOML file per menu entry under /usr/local/share/bit0/apps/ (override
with BIT0_APPS_DIR for bench testing); the leading number in the filename
sets menu order. Adding or removing an app = adding or removing a file in
the overlay - no code edit. Built-ins that need Python logic are merged
in by the launcher using the same entry-dict shape ('app' callable
instead of 'exec').

Entry keys: label (required), exec (required argv list), requires
(optional path; when absent the launch shows the NOT INSTALLED message),
icon (optional PBM filename in the icons dir), kill_stale (optional list
of process names to kill before launch).
"""

import os
import tomllib

APPS_DIR = os.environ.get('BIT0_APPS_DIR', '/usr/local/share/bit0/apps')


def _order(fn):
    head = fn.split('-', 1)[0]
    return int(head) if head.isdigit() else 50


def load_apps():
    """Registry entries sorted by menu order. A broken file logs and is
    skipped - a hand-edited registry must never take the boot UI down."""
    entries = []
    try:
        names = sorted(os.listdir(APPS_DIR))
    except OSError:
        return entries
    for fn in names:
        if not fn.endswith('.toml'):
            continue
        try:
            with open(os.path.join(APPS_DIR, fn), 'rb') as f:
                data = tomllib.load(f)
            label = data['label']
            argv = data['exec']
            if not isinstance(label, str) or not label:
                raise ValueError('label must be a non-empty string')
            if (not isinstance(argv, list) or not argv
                    or not all(isinstance(a, str) for a in argv)):
                raise ValueError('exec must be a list of strings')
            entries.append({
                'order': _order(fn),
                'label': label,
                'exec': argv,
                'requires': data.get('requires'),
                'icon': data.get('icon'),
                'kill_stale': data.get('kill_stale', []),
            })
        except (OSError, KeyError, ValueError, TypeError,
                tomllib.TOMLDecodeError) as exc:
            print(f'bit0 registry: skipping {fn}: {exc}', flush=True)
    entries.sort(key=lambda e: (e['order'], e['label']))
    return entries
