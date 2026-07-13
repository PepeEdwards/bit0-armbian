"""Widgets for the Bit0 launcher (audit 6.1). Compose-only: no widget
writes to the framebuffer; the launcher's render tick flushes."""

from ..evdev import KEY_LEFT, KEY_RIGHT
from ..fb import GLYPH_W, GLYPH_H
from .core import Widget
from .assets import load_icon, load_color_icon
from .theme import current as theme


def vstack(widgets, x, w, top, bottom, gap_max=16.0, max_h=48):
    """Assign rects distributing widgets evenly down a vertical span
    (replaces the old hand-computed column_from math)."""
    n = len(widgets)
    slot = (bottom - top) / n
    gap = min(gap_max, slot * 0.28)
    h = min(int(slot - gap), max_h)
    for i, wd in enumerate(widgets):
        wd.x, wd.y, wd.w, wd.h = x, int(top + i * slot + (slot - h) / 2), w, h
    return widgets


def hstack(widgets, x, y, w, h, gap=8):
    """Assign rects splitting a horizontal span evenly."""
    n = len(widgets)
    bw = (w - gap * (n - 1)) // n
    for i, wd in enumerate(widgets):
        wd.x, wd.y, wd.w, wd.h = x + i * (bw + gap), y, bw, h
    return widgets


def draw_icon(scr, rows, ox, oy, color):
    for gy, line in enumerate(rows):
        for gx, ch in enumerate(line):
            if ch == '#':
                scr.fill_rect(ox + gx, oy + gy, 1, 1, color)


def icon_size(rows):
    return (len(rows[0]), len(rows)) if rows else (0, 0)


class Button(Widget):
    """Bordered button with a text label or icon; clicking returns its
    action dict to the launcher loop."""

    def __init__(self, label='', icon=None, action=None, **rect):
        super().__init__(**rect)
        self.label = label
        self.icon = icon
        self.action = action

    def draw(self, scr, focused):
        th = theme()
        face = th.btn_hi if focused else th.btn
        fg = th.text_hi if focused else th.text
        scr.fill_rect(self.x, self.y, self.w, self.h, th.border)
        scr.fill_rect(self.x + 2, self.y + 2, self.w - 4, self.h - 4, face)
        if self.icon:
            iw, ih = icon_size(self.icon)
            draw_icon(scr, self.icon, self.x + (self.w - iw) // 2,
                      self.y + (self.h - ih) // 2, fg)
        else:
            s = 2
            tw = scr.text_width(self.label, s)
            scr.text(self.label, self.x + (self.w - tw) // 2,
                     self.y + (self.h - GLYPH_H * s) // 2, s, fg)

    def on_click(self, px, py):
        return self.action


class LiveLabel(Widget):
    """Borderless centered text from a callable (a State-cache read)."""

    is_value = True
    focusable = False

    def __init__(self, fn, **rect):
        super().__init__(**rect)
        self.fn = fn

    def draw(self, scr, focused):
        th = theme()
        scr.fill_rect(self.x, self.y, self.w, self.h, th.bg)
        s = 2
        txt = self.fn()
        tw = scr.text_width(txt, s)
        scr.text(txt, self.x + (self.w - tw) // 2,
                 self.y + (self.h - GLYPH_H * s) // 2, s, th.text)


class Slider(Widget):
    """Track + fill + knob with the name inside the bar. Value comes from
    getter() (a cache read); taps/drags quantize to 5% and go through
    setter() (which defers the sysfs write to the render tick)."""

    is_value = True

    def __init__(self, name, getter, setter, **rect):
        super().__init__(**rect)
        self.name = name
        self.getter = getter
        self.setter = setter
        self._last_sent = None

    def flush_rect(self):
        # the knob overhangs the track by 3 px top/bottom
        return (self.x, self.y - 4, self.w + 4, self.h + 8)

    def pct_at(self, px):
        pct = (px - self.x) * 100.0 / max(1, self.w)
        return max(0, min(100, int(round(pct / 5.0) * 5)))

    def on_drag(self, px, py):
        target = self.pct_at(px)
        if target != self._last_sent:
            self.setter(target)
            self._last_sent = target
            self.dirty = True
        return True

    def on_key(self, code):
        # LEFT/RIGHT scrub by 5%; autorepeat gives hold-to-scrub
        if code not in (KEY_LEFT, KEY_RIGHT):
            return None
        step = -5 if code == KEY_LEFT else 5
        self.setter(max(0, min(100, self.getter() + step)))
        self._last_sent = None  # a following drag must not be deduped away
        self.dirty = True
        return True

    def draw(self, scr, focused):
        th = theme()
        pct = self.getter()
        bx, by, bw, bh = self.x, self.y, self.w, self.h
        # clear the FULL flush rect: the old knob position must not
        # survive a partial redraw as a border trace
        scr.fill_rect(*self.flush_rect(), th.bg)
        scr.fill_rect(bx, by, bw, bh, th.border)                # border
        scr.fill_rect(bx + 1, by + 1, bw - 2, bh - 2, th.btn)  # groove
        fillw = int((bw - 2) * pct / 100)
        if fillw > 0:
            scr.fill_rect(bx + 1, by + 1, fillw, bh - 2,
                          th.btn_hi if focused else th.title)
        kx = bx + min(fillw, bw - 4)
        scr.fill_rect(kx, by - 3, 4, bh + 6, th.border)         # knob
        # label inside the bar (above it, it collided with the back button)
        scr.text(self.name, bx + 8, by + (bh - GLYPH_H * 2) // 2, 2, th.text)
        txt = str(pct)
        scr.text(txt, bx + bw - scr.text_width(txt, 2) - 6,
                 by + (bh - GLYPH_H * 2) // 2, 2, th.text)


def _tile_icon(name):
    """Resolve an entry's icon field to Tile kwargs. A .565/.png names a
    color icon; anything else a mono .pbm. Missing/broken -> no icon
    (the tile falls back to the boxed text label)."""
    if not name:
        return {}
    if name.endswith(('.565', '.png')):
        return {'color': load_color_icon(name)}
    return {'icon': load_icon(name)}


def _wrap_label(label, maxc):
    lines, cur = [], ''
    for word in label.split():
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


class Tile(Widget):
    """Square app tile. With an icon (color .565 or mono .pbm): no box -
    the icon sits on top and the label goes under it in the small
    (scale-1) font. Without an icon: a bordered box with the label as
    big wrapped text. Entries work either way (audit 6.1/6.3)."""

    def __init__(self, entry, icon=None, color=None, **rect):
        super().__init__(**rect)
        self.entry = entry
        self.icon = icon      # mono row strings, or None
        self.color = color    # ColorIcon, or None

    def _label_layout(self):
        """(scale, lines): the largest font scale whose word-wrap fits the
        tile - never splits a word mid-line just to grow the text. The
        theme sets the ceiling (default 1.5: full 2x read oversized on
        the 2.4" panel)."""
        label = self.entry['label']
        for s in dict.fromkeys((theme().tile_label_scale_max, 1)):
            maxc = max(1, (self.w - 6) // round(GLYPH_W * s))
            if any(len(word) > maxc for word in label.split()):
                continue
            lines, cur = [], ''
            for word in label.split():
                cand = (cur + ' ' + word).strip()
                if len(cand) <= maxc:
                    cur = cand
                else:
                    lines.append(cur)
                    cur = word
            lines.append(cur)
            if len(lines) * (round(GLYPH_H * s) + 2) <= self.h - 6:
                return s, lines
        # pathological label (one huge word): clip hard at scale 1
        maxc = max(1, (self.w - 6) // GLYPH_W)
        return 1, [label[i:i + maxc] for i in range(0, len(label), maxc)][:4]

    def draw(self, scr, focused):
        th = theme()
        if self.color or self.icon:
            self._draw_icon_tile(scr, th, focused)
            return
        # icon-less: bordered box with the big wrapped label
        face = th.btn_hi if focused else th.btn
        fg = th.text_hi if focused else th.text
        scr.fill_rect(self.x, self.y, self.w, self.h, th.border)
        scr.fill_rect(self.x + 2, self.y + 2, self.w - 4, self.h - 4, face)
        s, lines = self._label_layout()
        lh = round(GLYPH_H * s) + 2
        ty = self.y + (self.h - len(lines) * lh) // 2
        for i, ln in enumerate(lines):
            tw = scr.text_width(ln, s)
            scr.text(ln, self.x + (self.w - tw) // 2, ty + i * lh, s, fg)

    def _draw_icon_tile(self, scr, th, focused):
        # focus shows a box outline over the plain bg (no fill colour), so
        # the icon's own colours are never tinted by a highlight
        scr.fill_rect(self.x, self.y, self.w, self.h, th.bg)
        if focused:
            scr.fill_rect(self.x, self.y, self.w, self.h, th.btn_hi)
            scr.fill_rect(self.x + 2, self.y + 2, self.w - 4, self.h - 4,
                          th.bg)
        fg = th.text
        iw, ih = (self.color.w, self.color.h) if self.color \
            else icon_size(self.icon)
        # small (scale-1) label under the icon, wrapped to the tile
        lines = _wrap_label(self.entry['label'], max(1, (self.w - 4) // GLYPH_W))
        lh = GLYPH_H + 1
        label_h = len(lines) * lh
        top = self.y + max(2, (self.h - ih - 3 - label_h) // 2)
        ix = self.x + (self.w - iw) // 2
        if self.color:
            self.color.draw(scr, ix, top)
        else:
            draw_icon(scr, self.icon, ix, top, fg)
        ty = top + ih + 3
        for i, ln in enumerate(lines):
            tw = scr.text_width(ln, 1)
            scr.text(ln, self.x + (self.w - tw) // 2, ty + i * lh, 1, fg)

    def on_click(self, px, py):
        return {'launch': self.entry}


class AppGrid(Widget):
    """Paged horizontal tile row for the main menu: square tiles,
    vertically centered, with arrow zones at the row ends that appear
    only when a previous/next page exists (audit 6.1). Tile size, gap,
    and tiles-per-page come from the theme (defaults: 3 x 80 px - 4 x
    56 px read too small/cramped on the 2.4" panel)."""

    ARROW_W = 20
    ARROW_PAD = 4

    def __init__(self, entries, tile=None, gap=None, per_page=None, **rect):
        super().__init__(**rect)
        th = theme()
        self.entries = entries
        self.tile = tile if tile is not None else th.tile_size
        self.gap = gap if gap is not None else th.tile_gap
        self.per_page = max(1, per_page if per_page is not None
                            else th.tiles_per_page)
        self.pageno = 0
        self._focus = None  # 'l' / 'r' / tile index / None (pointer + keyboard)
        self._tiles = []
        self._arrow_l = self._arrow_r = None
        self._rebuild()

    def _rebuild(self):
        start = self.pageno * self.per_page
        vis = self.entries[start:start + self.per_page]
        ts, gap = self.tile, self.gap
        row_w = len(vis) * ts + (len(vis) - 1) * gap
        x0 = self.x + (self.w - row_w) // 2
        ty = self.y + (self.h - ts) // 2
        self._tiles = [Tile(e, x=x0 + i * (ts + gap), y=ty, w=ts, h=ts,
                            **_tile_icon(e.get('icon')))
                       for i, e in enumerate(vis)]
        aw = self.ARROW_W
        self._arrow_l = (self.x, ty, aw, ts) if self.pageno > 0 else None
        self._arrow_r = (self.x + self.w - aw, ty, aw, ts) \
            if start + self.per_page < len(self.entries) else None

    def _target_at(self, px, py):
        for which, rect in (('l', self._arrow_l), ('r', self._arrow_r)):
            if rect and rect[0] <= px < rect[0] + rect[2] \
                    and rect[1] <= py < rect[1] + rect[3]:
                return which
        for i, t in enumerate(self._tiles):
            if t.contains(px, py):
                return i
        return None

    def on_pointer(self, px, py):
        new = self._target_at(px, py)
        if new != self._focus:
            self._focus = new
            return True
        return False

    def flip(self, step):
        """Page the grid by +-1 if a page exists in that direction."""
        new = self.pageno + step
        if 0 <= new * self.per_page < len(self.entries):
            self.pageno = new
            self._focus = None
            self._rebuild()
            self.dirty = True
            return True
        return False

    def on_click(self, px, py):
        t = self._target_at(px, py)
        if t == 'l':
            self.flip(-1)
            return None
        if t == 'r':
            self.flip(+1)
            return None
        if isinstance(t, int):
            return self._tiles[t].on_click(px, py)
        return None

    def on_key(self, code):
        """LEFT/RIGHT move focus across the tile row; moving past the
        row's edge pages the grid when another page exists (same effect
        as the arrow tile), else the key falls through to the page ring
        so keyboard focus can leave the grid (audit 6.4)."""
        if code not in (KEY_LEFT, KEY_RIGHT):
            return None
        i = self._focus if isinstance(self._focus, int) else 0
        step = -1 if code == KEY_LEFT else 1
        j = i + step
        if 0 <= j < len(self._tiles):
            self._focus = j
            self.dirty = True
            return True
        if self.flip(step):
            self._focus = len(self._tiles) - 1 if step < 0 else 0
            return True
        return None

    def on_focus(self, gained):
        if gained:
            if not isinstance(self._focus, int):
                self._focus = 0
        else:
            self._focus = None
        self.dirty = True

    def activate(self):
        if isinstance(self._focus, int) and self._focus < len(self._tiles):
            return self._tiles[self._focus].on_click(0, 0)
        return None

    def draw(self, scr, focused):
        th = theme()
        scr.fill_rect(self.x, self.y, self.w, self.h, th.bg)
        for i, t in enumerate(self._tiles):
            t.draw(scr, self._focus == i)
        for which, rect, name in (('l', self._arrow_l, 'left.pbm'),
                                  ('r', self._arrow_r, 'right.pbm')):
            rows = load_icon(name) if rect else None
            if not rows:
                continue
            iw, ih = icon_size(rows)
            color = th.btn_hi if self._focus == which else th.text
            draw_icon(scr, rows, rect[0] + (rect[2] - iw) // 2,
                      rect[1] + (rect[3] - ih) // 2, color)
