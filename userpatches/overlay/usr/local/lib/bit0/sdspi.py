"""SPI SD card handling (on-demand bind) for the Bit0 launcher.

The SD slot sits on spi0 (CS2) sharing the bus with the display+touch.
Leaving mmc_spi bound makes it poll the card forever and stall the bus
(display freeze), so it lives UNBOUND. We bind it only to read a cart, then
unbind to free the bus before launching. Needs the DT mmc@2 node enabled
(status="okay") so the spi0.2 device exists; if it's disabled,
sd_slot_present() is False.
"""

import os
import shutil
import subprocess
import time

from .apps import run_pico8_cart
from .fb import fullscreen_message

SD_SPI      = 'spi0.2'
MMC_DRV     = '/sys/bus/spi/drivers/mmc_spi'
SD_DEV_SYS  = '/sys/bus/spi/devices/' + SD_SPI
SD_MOUNT    = '/mnt/sd'
SD_CACHE    = '/root/pico-8/carts/sdcard'


def _sysfs_write(path, val):
    try:
        with open(path, 'w') as f:
            f.write(val)
        return True
    except OSError:
        return False


def sd_slot_present():
    return os.path.exists(SD_DEV_SYS)


def sd_bound():
    return os.path.exists(SD_DEV_SYS + '/driver')


def sd_release():
    """Unbind mmc_spi so it stops polling the SPI bus."""
    if sd_bound():
        _sysfs_write(MMC_DRV + '/unbind', SD_SPI)


def sd_enable():
    if sd_slot_present() and not sd_bound():
        _sysfs_write(MMC_DRV + '/bind', SD_SPI)


def _mmcblk_base():
    try:
        return {d for d in os.listdir('/sys/block') if d.startswith('mmcblk')}
    except OSError:
        return set()


def _find_mount(dev):
    """Mountpoint of `dev` (e.g. mmcblk1) or any of its partitions, else None.
    The hotplug daemon auto-mounts cards under /media/<name>."""
    if not dev:
        return None
    try:
        with open('/proc/mounts') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2 and parts[0].startswith('/dev/' + dev):
                    return parts[1].replace('\\040', ' ')
    except OSError:
        pass
    return None


def run_sdcard(scr):
    """Bind the SPI SD card, copy any PICO-8 cart to the cache, unbind to free
    the bus, then launch the first cart found."""
    if not sd_slot_present():
        fullscreen_message(scr, 'SD SLOT DISABLED')
        time.sleep(2)
        return
    fullscreen_message(scr, 'READING SD...')
    sd_release()                              # clean state, so bind yields a new dev
    time.sleep(0.4)
    before = _mmcblk_base()
    sd_enable()

    dev = None
    for _ in range(40):                       # up to ~4s for the card to init
        time.sleep(0.1)
        new = sorted(d for d in (_mmcblk_base() - before) if 'p' not in d)
        if new:
            dev = new[0]
            break
    if not dev:
        fullscreen_message(scr, 'NO SD CARD')
        sd_release(); time.sleep(2)
        return

    # The hotplug daemon auto-mounts the card under /media/<name>. Wait for
    # that; only mount it ourselves if no automount appears.
    mountpoint = None
    own_mount = False
    for _ in range(30):                       # up to ~3s for the automount
        mountpoint = _find_mount(dev)
        if mountpoint:
            break
        time.sleep(0.1)
    if not mountpoint:
        node = '/dev/%sp1' % dev
        if not os.path.exists(node):
            node = '/dev/' + dev
        os.makedirs(SD_MOUNT, exist_ok=True)
        if any(subprocess.call(['mount', '-o', 'ro', '-t', fs, node, SD_MOUNT],
                               stderr=subprocess.DEVNULL) == 0
               for fs in ('exfat', 'vfat', 'auto')):
            mountpoint, own_mount = SD_MOUNT, True
    if not mountpoint:
        fullscreen_message(scr, 'CANT READ CARD')
        sd_release(); time.sleep(2)
        return

    found = []
    for root, _dirs, files in os.walk(mountpoint):
        if 'System Volume Information' in root:
            continue
        for fn in sorted(files):
            low = fn.lower()
            if low.endswith('.p8.png') or low.endswith('.p8'):
                found.append(os.path.join(root, fn))
        if len(found) >= 30:
            break

    cached = []
    if found:
        fullscreen_message(scr, 'COPYING...')
        os.makedirs(SD_CACHE, exist_ok=True)
        for src in found:
            dst = os.path.join(SD_CACHE, os.path.basename(src))
            try:
                shutil.copyfile(src, dst)
                cached.append(dst)
            except OSError:
                pass

    # Release the bus (unmount + unbind) BEFORE launching, as requested.
    subprocess.call(['umount', mountpoint], stderr=subprocess.DEVNULL)
    sd_release()

    if not cached:
        fullscreen_message(scr, 'NO PICO-8 GAME')
        time.sleep(2)
        return

    fullscreen_message(scr, 'LAUNCHING...')
    run_pico8_cart(cached[0])                 # extra carts stay in SD_CACHE
