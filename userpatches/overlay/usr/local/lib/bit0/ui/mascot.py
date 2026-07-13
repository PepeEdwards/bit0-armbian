"""Mascot companion, dating-sim style (audit 6.5, reworked on-device).

Bottom-right sprite box + a dialogue box beside it showing the mascot's
name and queued messages; ENTER/SPACE/click advance (Router overlay
precedence), ESC dismisses. Both boxes live inside the reserved
theme.mascot_strip band, so they never overlap page content.

Mascots are data: one directory per mascot under
/usr/local/share/bit0/mascots/<id>/ (override with BIT0_MASCOTS_DIR)
holding `mascot.toml` (name = "...") and one PBM/PGM sprite per emotion
(`idle.pbm` required; add `happy.pbm`, `talk.pbm`, `blink.pbm`, ... as
they get drawn - say(..., emotion=...) picks them up, and talk/blink
animate automatically when those sprites exist). Adding a mascot =
adding a directory; no code edit. The first-boot selection persists
in the device state JSON (bit0.state).
"""

import os
import time
import tomllib

from ..fb import GLYPH_W, GLYPH_H
from .core import Widget
from .assets import parse_pbm
from .theme import current as theme

MASCOTS_DIR = os.environ.get('BIT0_MASCOTS_DIR',
                             '/usr/local/share/bit0/mascots')


def _norm(rows):
    """Pad art rows to equal width (keeps hand-edited files forgiving)."""
    w = max(len(r) for r in rows)
    return [r.ljust(w) for r in rows]


def load_mascots():
    """Mascot pool sorted by directory name (the mascots dir is the only
    source - no in-code art). A broken mascot dir logs and is skipped;
    an empty pool disables the mascot entirely (the launcher guards)."""
    out = []
    try:
        names = sorted(os.listdir(MASCOTS_DIR))
    except OSError:
        names = []
    for d in names:
        path = os.path.join(MASCOTS_DIR, d)
        if not os.path.isdir(path):
            continue
        try:
            with open(os.path.join(path, 'mascot.toml'), 'rb') as f:
                name = tomllib.load(f)['name']
            if not isinstance(name, str) or not name:
                raise ValueError('name must be a non-empty string')
            sprites = {}
            for fn in sorted(os.listdir(path)):
                stem, ext = os.path.splitext(fn)
                if ext in ('.pbm', '.pgm'):
                    with open(os.path.join(path, fn)) as f:
                        sprites[stem] = _norm(parse_pbm(f.read()))
            if 'idle' not in sprites:
                raise ValueError('no idle sprite')
            out.append({'id': d, 'name': name, 'sprites': sprites})
        except (OSError, KeyError, ValueError, TypeError,
                tomllib.TOMLDecodeError) as exc:
            print(f'bit0 mascot: skipping {d}: {exc}', flush=True)
    return out


# pixel insets per row for the bubble's rounded corners (radius 6)
_CORNER = (6, 4, 3, 2, 1, 1)


def _rounded_rect(scr, x, y, w, h, color):
    """Comic-bubble body: a rect with pixel-art rounded corners."""
    for i in range(h):
        d = min(i, h - 1 - i)
        inset = _CORNER[d] if d < len(_CORNER) else 0
        scr.fill_rect(x + inset, y + i, w - 2 * inset, 1, color)


def personalize(msgs, user_name, mascot_name):
    """Substitute {USER} and {MASCOT} in message lists (theme.json
    onboarding/greeting). An empty user name drops the token together
    with its leading space so 'HI {USER}.' degrades to 'HI.'."""
    user = user_name.strip().upper()  # the 5x7 font is uppercase-only
    out = []
    for m in msgs:
        m = m.replace('{MASCOT}', mascot_name)
        if user:
            m = m.replace('{USER}', user)
        else:
            m = m.replace(' {USER}', '').replace('{USER}', '')
        out.append(' '.join(m.split()))
    return out


def _wrap(msg, maxc):
    lines, cur = [], ''
    for word in msg.split():
        cand = (cur + ' ' + word).strip()
        if len(cand) <= maxc:
            cur = cand
        else:
            if cur:
                lines.append(cur)
            cur = word[:maxc]
    if cur:
        lines.append(cur)
    return lines or ['']


class Mascot(Widget):
    """Sprite box (this widget's rect, bottom-right) + dialogue box drawn
    to its left while messages are queued."""

    focusable = False
    BLINK_EVERY, BLINK_LEN, TALK_STEP = 4.0, 0.15, 0.35

    # casual-message lifetime: base + per-character, clamped (audit 6.5.1)
    EXPIRE_BASE, EXPIRE_PER_CHAR = 1.5, 0.06
    EXPIRE_MIN, EXPIRE_MAX = 2.5, 7.0

    def __init__(self, definition, **rect):
        super().__init__(**rect)
        self.queue = []         # (text, modal) pairs; the head is shown
        self._cur = 'idle'      # sprite key currently shown
        self._emotion = None    # say()-requested sprite while speaking
        self._deadline = None   # next animation step, None = static
        self._expire = None     # casual head auto-dismiss time
        self._idle_i = -1       # rotates through theme.mascot_idle
        self.set_definition(definition)

    def set_definition(self, definition):
        self.name = definition['name']
        self.sprites = definition['sprites']
        self.mascot_id = definition['id']
        self._cur = 'idle'
        self._settle()
        self.dirty = True

    # ── message queue ────────────────────────────────────────────────────
    @property
    def bubble_visible(self):
        """True only for QUEUED messages. The resting phrase draws a
        bubble too but must never affect input."""
        return bool(self.queue)

    @property
    def locking(self):
        """True while the head message is modal (onboarding): the Router
        captures ALL input and the page gets the darkened cover."""
        return bool(self.queue) and self.queue[0][1]

    def current_text(self):
        """Queued message head, else the resting phrase (the mascot is
        never without a bubble), else None when the theme's idle list
        is emptied to opt out."""
        if self.queue:
            return self.queue[0][0]
        idle = theme().mascot_idle
        return idle[self._idle_i % len(idle)] if idle else None

    def say(self, msgs, emotion=None, modal=False):
        """Queue messages. modal=True (onboarding) locks the UI until
        advanced; the default is casual: no input capture, auto-dismiss
        on a length-scaled timer or a click on the bubble (audit 6.5.1).
        `emotion` picks that sprite while speaking (falls back to idle
        when the mascot doesn't have it)."""
        head_new = not self.queue
        self.queue.extend((m, modal) for m in msgs)
        self._emotion = emotion if emotion in self.sprites else None
        self._cur = self._emotion or 'idle'
        if 'talk' in self.sprites and not self._emotion:
            self._cur = 'talk'
            self._deadline = time.monotonic() + self.TALK_STEP
        if head_new:
            self._arm_head()
        self.dirty = True

    def advance(self):
        """Next message; the last one settles into a resting phrase."""
        if self.queue:
            self.queue.pop(0)
        if self.queue:
            self._arm_head()
        else:
            self._settle()
        self.dirty = True

    def _arm_head(self):
        """Start the auto-dismiss timer when the new head is casual."""
        if self.queue and not self.queue[0][1]:
            life = min(self.EXPIRE_MAX,
                       max(self.EXPIRE_MIN, self.EXPIRE_BASE
                           + self.EXPIRE_PER_CHAR * len(self.queue[0][0])))
            self._expire = time.monotonic() + life
        else:
            self._expire = None

    def hit_bubble(self, px, py):
        """Pointer over the bubble (casual click-to-dismiss target)."""
        dx, dy, dw, dh = self._dialogue_rect()
        return dx <= px < dx + dw and dy <= py < dy + dh

    def dismiss(self):
        self.queue.clear()
        self._settle()
        self.dirty = True

    def _settle(self):
        self._emotion = None
        self._cur = 'idle'
        self._expire = None
        self._idle_i += 1  # next resting phrase each time we go quiet
        self._deadline = (time.monotonic() + self.BLINK_EVERY
                          if 'blink' in self.sprites else None)

    # ── animation + casual-message expiry deadlines ──────────────────────
    def next_deadline(self):
        cands = [d for d in (self._deadline, self._expire) if d is not None]
        return min(cands) if cands else None

    def tick(self, now):
        if self._expire is not None and now >= self._expire:
            self.advance()  # casual head timed out
            return True
        if self._deadline is None or now < self._deadline:
            return False
        if self.bubble_visible and 'talk' in self.sprites \
                and not self._emotion:
            self._cur = 'idle' if self._cur == 'talk' else 'talk'
            self._deadline = now + self.TALK_STEP
        elif self._cur == 'blink':
            self._cur = 'idle'
            self._deadline = now + self.BLINK_EVERY
        elif 'blink' in self.sprites and not self.bubble_visible:
            self._cur = 'blink'
            self._deadline = now + self.BLINK_LEN
        else:
            self._deadline = None
            return False
        self.dirty = True
        return True

    # ── drawing ──────────────────────────────────────────────────────────
    def _dialogue_rect(self):
        return (4, self.y, self.x - 8, self.h)

    def flush_rects(self):
        rects = [(self.x, self.y, self.w, self.h)]
        if self.current_text() is not None:
            rects.append(self._dialogue_rect())
        return rects

    def _draw_sprite(self, scr, th):
        scr.fill_rect(self.x, self.y, self.w, self.h, th.border)
        scr.fill_rect(self.x + 1, self.y + 1, self.w - 2, self.h - 2, th.btn)
        rows = self.sprites.get(self._cur, self.sprites['idle'])
        ox = self.x + (self.w - len(rows[0])) // 2
        oy = self.y + (self.h - len(rows)) // 2
        for gy, line in enumerate(rows):
            for gx, ch in enumerate(line):
                if ch == '#':
                    scr.fill_rect(ox + gx, oy + gy, 1, 1, th.text)
                elif ch == '*':
                    scr.fill_rect(ox + gx, oy + gy, 1, 1, th.title)

    def draw(self, scr, focused):
        th = theme()
        if self.locking:
            # modal cover: darken the locked page above the band. Runs
            # only during a full compose (the launcher escalates every
            # redraw to full while locking), so it never double-darkens.
            scr.dim(0, max(0, self.y - 4))
        self._draw_sprite(scr, th)
        text = self.current_text()
        if text is None:
            return
        # comic speech bubble: rounded outline + white body, tail wedge
        # pointing at the sprite box; the whole rect (incl. the corner
        # cutouts and tail gap) is repainted per the flush invariant
        dx, dy, dw, dh = self._dialogue_rect()
        scr.fill_rect(dx, dy, dw, dh, th.bg)
        bw = dw - 8  # tail lives in the gap toward the sprite box
        _rounded_rect(scr, dx, dy, bw, dh, th.text_hi)          # outline
        _rounded_rect(scr, dx + 1, dy + 1, bw - 2, dh - 2, th.text)
        ty0 = dy + dh // 2 - 4
        for j in range(8):
            scr.fill_rect(dx + bw - 2, ty0 + j, 9 - j, 1, th.text)
        scr.text(self.name, dx + 9, dy + 6, 1, th.title)
        maxc = max(1, (bw - 18) // GLYPH_W)
        max_lines = (dh - (6 + GLYPH_H + 4) - 5) // (GLYPH_H + 2)
        lines = _wrap(text, maxc)[:max(1, max_lines)]
        ty = dy + 6 + GLYPH_H + 4
        for i, ln in enumerate(lines):
            scr.text(ln, dx + 9, ty + i * (GLYPH_H + 2), 1, th.text_hi)


class MascotCard(Widget):
    """First-boot chooser card: sprite on top, name below; activating it
    returns the picked definition to the launcher."""

    def __init__(self, definition, **rect):
        super().__init__(**rect)
        self.definition = definition

    def draw(self, scr, focused):
        th = theme()
        face = th.btn_hi if focused else th.btn
        fg = th.text_hi if focused else th.text
        scr.fill_rect(self.x, self.y, self.w, self.h, th.border)
        scr.fill_rect(self.x + 2, self.y + 2, self.w - 4, self.h - 4, face)
        rows = self.definition['sprites']['idle']
        ox = self.x + (self.w - len(rows[0])) // 2
        oy = self.y + (self.h - 24 - len(rows)) // 2
        for gy, line in enumerate(rows):
            for gx, ch in enumerate(line):
                if ch in '#*':
                    scr.fill_rect(ox + gx, oy + gy, 1, 1, fg)
        name = self.definition['name']
        s = 1.5
        tw = scr.text_width(name, s)
        scr.text(name, self.x + (self.w - tw) // 2,
                 self.y + self.h - round(GLYPH_H * s) - 8, s, fg)

    def on_click(self, px, py):
        return {'mascot': self.definition}
