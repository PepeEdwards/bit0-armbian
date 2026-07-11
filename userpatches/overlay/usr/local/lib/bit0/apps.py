"""App launching and system controls (volume/brightness) for the Bit0
launcher."""

import os
import shutil
import subprocess
import time

from .fb import fullscreen_message

VOL_HELPER = '/usr/local/bin/bit0-vol'
BL_DIR = '/sys/class/backlight/backlight'


def kill_stale(*names):
    # The MAX98357A amp is a single-stream PCM (no mixing): a leftover/orphaned
    # instance holding /dev/snd/pcmC0D0p blocks the next app's audio entirely.
    # Clear any stragglers before (re)launching.
    for n in names:
        subprocess.call(['killall', n],
                        stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


def run_pico8(scr=None):
    # pico-8 is proprietary and only present if it was in the build overlay
    # or pushed with install-pico8.sh; see docs/PICO8.md. All launch logic
    # (env, GL workarounds, stretch shim) lives in /usr/local/bin/pico8-launch.
    if not os.path.exists('/root/pico-8/pico8_dyn'):
        if scr:
            fullscreen_message(scr, 'PICO-8 NOT INSTALLED')
            time.sleep(2.5)
        return
    kill_stale('pico8_dyn')
    subprocess.call(['/usr/local/bin/pico8-launch'],
                    env=dict(os.environ, HOME='/root'))


def run_pico8_cart(cart):
    kill_stale('pico8_dyn')
    subprocess.call(['/usr/local/bin/pico8-launch', '-run', cart],
                    env=dict(os.environ, HOME='/root'))


def run_terminal():
    # fbcon renders the VT on fb0; the Lyra UART Keyboard has a kbd handler,
    # so it types straight into the console. Exiting the shell returns here.
    # -c 2 is mandatory: busybox openvt's free-VT query asks /dev/console,
    # which is the serial port on this board, and fails with "can't find
    # open VT". -f forces reuse of VT2 on repeated launches.
    # Plain non-login shell: `sh -l` would source /root/.profile, which
    # chains into bash and whatever its rc files start.
    if shutil.which('fbterm'):
        cmd = ['openvt', '-f', '-c', '2', '-s', '-w', '--', 'fbterm']
    else:
        cmd = ['openvt', '-f', '-c', '2', '-s', '-w', '--', '/bin/sh']
    subprocess.call(cmd, env=dict(os.environ, HOME='/root', TERM='linux'))
    subprocess.call(['chvt', '1'])  # make sure the VT with our fb is active
    time.sleep(0.2)  # let fbcon finish repainting tty1 before we draw over it
    # (without this the console repaint lands after our menu redraw and
    #  leaves text fragments on screen)


def run_calibrate():
    subprocess.call(['systemctl', 'stop', 'touch-mouse'])
    subprocess.call(['/usr/local/bin/touch-cal'])
    subprocess.call(['systemctl', 'start', 'touch-mouse'])
    time.sleep(2)  # let the uinput device reappear before reopening inputs


# ── volume (via bit0-vol, the single owner of the amixer invocation) ─────────

VOL_STATE = '/run/bit0-vol.pct'  # bit0-vol publishes the pct here on change


def vol_state_read():
    """(mtime_ns, pct) from the state file bit0-vol publishes after every
    volume change; None until the first change. Lets the launcher notice
    hotkey volume changes (consumed inside uart-hid-bridge, so no input
    event reaches it) without spawning a process. mtime is taken before
    the read so a racing write is caught on the next poll."""
    try:
        mt = os.stat(VOL_STATE).st_mtime_ns
        with open(VOL_STATE) as f:
            txt = f.read().strip()
        return (mt, int(txt)) if txt else None
    except (OSError, ValueError):
        return None


def get_volume():
    try:
        out = subprocess.check_output([VOL_HELPER, 'get'],
                                      stderr=subprocess.DEVNULL)
        return int(out.strip() or 0)
    except (OSError, ValueError, subprocess.CalledProcessError):
        return 0


def vol_set(pct, wait=True):
    """Set volume via bit0-vol; returns the clamped pct so callers can
    update a cached value optimistically. wait=False fires the helper
    without blocking the UI (subprocess reaps abandoned children on the
    next spawn, so no zombies accumulate)."""
    pct = max(0, min(100, int(pct)))
    argv = [VOL_HELPER, 'set', str(pct)]
    if wait:
        subprocess.call(argv, stderr=subprocess.DEVNULL)
    else:
        subprocess.Popen(argv, stderr=subprocess.DEVNULL)
    return pct


# ── brightness (pwm-backlight via sysfs) ─────────────────────────────────────

def _bl_read(name):
    with open(f'{BL_DIR}/{name}') as f:
        return int(f.read())


_bl_max = 0  # max_brightness never changes; read sysfs once


def _bl_max_cached():
    global _bl_max
    if not _bl_max:
        try:
            _bl_max = _bl_read('max_brightness') or 255
        except (OSError, ValueError):
            _bl_max = 255
    return _bl_max


def get_brightness():
    try:
        return max(0, min(100, round(_bl_read('brightness') * 100
                                     / _bl_max_cached())))
    except (OSError, ValueError):
        return 100


def set_brightness(pct):
    # 5% floor: brightness 0 switches the panel backlight fully OFF and the
    # user would be stuck dragging a slider on an invisible screen.
    pct = max(5, min(100, int(pct)))
    try:
        with open(f'{BL_DIR}/brightness', 'w') as f:
            f.write(str(max(1, round(pct * _bl_max_cached() / 100))))
    except OSError:
        pass
    return pct
