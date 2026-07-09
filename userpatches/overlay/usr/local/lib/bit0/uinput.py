"""uinput device creation (raw ioctls; ARM 32-bit Linux)."""

import fcntl
import os
import struct
import subprocess

from .evdev import EV_SYN, EV_KEY, EV_REL, EV_ABS, BUS_USB

UINPUT = '/dev/uinput'

UI_SET_EVBIT  = 0x40045564
UI_SET_KEYBIT = 0x40045565
UI_SET_RELBIT = 0x40045566
UI_SET_ABSBIT = 0x40045567
UI_DEV_CREATE = 0x5501


def create_device(name, product, keys=(), rels=(), abs_max=None, vendor=0x1234):
    """Create a uinput device and return its fd (O_WRONLY | O_NONBLOCK).

    keys: key/button codes; rels: REL_* axes; abs_max: {ABS_*: max} for
    absolute axes (min is 0). Callers that need the node to settle before
    writing events sleep after this returns.
    """
    subprocess.call(['modprobe', 'uinput'],
                    stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
    fd = os.open(UINPUT, os.O_WRONLY | os.O_NONBLOCK)
    fcntl.ioctl(fd, UI_SET_EVBIT, EV_SYN)
    if keys:
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_KEY)
        for k in keys:
            fcntl.ioctl(fd, UI_SET_KEYBIT, k)
    if rels:
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_REL)
        for r in rels:
            fcntl.ioctl(fd, UI_SET_RELBIT, r)
    absmax = [0] * 64
    if abs_max:
        fcntl.ioctl(fd, UI_SET_EVBIT, EV_ABS)
        for axis, mx in abs_max.items():
            fcntl.ioctl(fd, UI_SET_ABSBIT, axis)
            absmax[axis] = mx
    # struct uinput_user_dev: name[80], input_id, ff_effects_max,
    #                         absmax[64], absmin[64], absfuzz[64], absflat[64]
    uud = struct.pack('80sHHHHI' + '64i' * 4,
                      name.encode(), BUS_USB, vendor, product, 1, 0,
                      *(absmax + [0] * 192))
    os.write(fd, uud)
    fcntl.ioctl(fd, UI_DEV_CREATE)
    return fd
