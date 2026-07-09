"""evdev constants and event IO shared by the Bit0 daemons."""

import os
import struct

# event types
EV_SYN, EV_KEY, EV_REL, EV_ABS = 0x00, 0x01, 0x02, 0x03
SYN_REPORT = 0

# relative axes
REL_X, REL_Y = 0x00, 0x01
REL_HWHEEL, REL_WHEEL = 0x06, 0x08

# absolute axes
ABS_X, ABS_Y = 0x00, 0x01

# buttons / keys
BTN_LEFT, BTN_RIGHT, BTN_MIDDLE = 0x110, 0x111, 0x112
BTN_SIDE, BTN_EXTRA = 0x113, 0x114
BTN_TOUCH = 0x14a
KEY_ESC = 1

BUS_USB = 0x03

# struct input_event on 32-bit ARM: timeval (2 x long) + type + code + value.
# EVENT_SIZE is 16 on the target; computed so the format stays authoritative.
EVENT_FORMAT = 'llHHi'
EVENT_SIZE = struct.calcsize(EVENT_FORMAT)

EVIOCGRAB = 0x40044590


def send_event(fd, ev_type, code, value):
    os.write(fd, struct.pack(EVENT_FORMAT, 0, 0, ev_type, code, value))


def unpack_event(data):
    """One EVENT_SIZE record -> (type, code, value); timestamp discarded."""
    _, _, t, code, v = struct.unpack(EVENT_FORMAT, data)
    return t, code, v


def find_event(name):
    """Path of the /dev/input/eventN whose device name matches, else None."""
    base = '/sys/class/input'
    try:
        nodes = sorted(os.listdir(base))
    except OSError:
        return None
    for n in nodes:
        if not n.startswith('event'):
            continue
        try:
            with open(f'{base}/{n}/device/name') as f:
                if f.read().strip() == name:
                    return f'/dev/input/{n}'
        except OSError:
            continue
    return None


def fb_size(default=(320, 240)):
    """(width, height) of fb0, or `default` when the fb isn't up yet."""
    try:
        with open('/sys/class/graphics/fb0/virtual_size') as f:
            w, h = map(int, f.read().split(','))
        return w, h
    except (OSError, ValueError):
        return default
