"""Widgets for the Bit0 launcher (audit 6.1). Compose-only: no widget
writes to the framebuffer; the launcher's render tick flushes."""

from ..fb import GLYPH_W, GLYPH_H
from .core import Widget
from .assets import load_icon
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

    def draw(self, scr, hover):
        th = theme()
        face = th.btn_hi if hover else th.btn
        fg = th.text_hi if hover else th.text
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

    def __init__(self, fn, **rect):
        super().__init__(**rect)
        self.fn = fn

    def draw(self, scr, hover):
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

    def draw(self, scr, hover):
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
                          th.btn_hi if hover else th.title)
        kx = bx + min(fillw, bw - 4)
        scr.fill_rect(kx, by - 3, 4, bh + 6, th.border)         # knob
        # label inside the bar (above it, it collided with the back button)
        scr.text(self.name, bx + 8, by + (bh - GLYPH_H * 2) // 2, 2, th.text)
        txt = str(pct)
        scr.text(txt, bx + bw - scr.text_width(txt, 2) - 6,
                 by + (bh - GLYPH_H * 2) // 2, 2, th.text)


class Tile(Widget):
    """Square app tile: centered PBM icon, or the label as wrapped text
    when the entry has no icon - entries work either way (audit 6.1)."""

    def __init__(self, entry, icon=None, **rect):
        super().__init__(**rect)
        self.entry = entry
        self.icon = icon

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

    def draw(self, scr, hover):
        th = theme()
        face = th.btn_hi if hover else th.btn
        fg = th.text_hi if hover else th.text
        scr.fill_rect(self.x, self.y, self.w, self.h, th.border)
        scr.fill_rect(self.x + 2, self.y + 2, self.w - 4, self.h - 4, face)
        if self.icon:
            iw, ih = icon_size(self.icon)
            draw_icon(scr, self.icon, self.x + (self.w - iw) // 2,
                      self.y + (self.h - ih) // 2, fg)
        else:
            s, lines = self._label_layout()
            lh = round(GLYPH_H * s) + 2
            ty = self.y + (self.h - len(lines) * lh) // 2
            for i, ln in enumerate(lines):
                tw = scr.text_width(ln, s)
                scr.text(ln, self.x + (self.w - tw) // 2, ty + i * lh, s, fg)

    def on_click(self, px, py):
        return {'launch': self.entry}


# code fallbacks if the arrow PBMs are missing: solid < / > triangles
_TRI_L = [' ' * abs(6 - r) + '#' * (7 - abs(6 - r)) for r in range(13)]
_TRI_R = ['#' * (7 - abs(6 - r)) + ' ' * abs(6 - r) for r in range(13)]


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
        self._hover = None  # 'l' / 'r' / tile index / None
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
        self._tiles = [
            Tile(e, icon=load_icon(e['icon']) if e.get('icon') else None,
                 x=x0 + i * (ts + gap), y=ty, w=ts, h=ts)
            for i, e in enumerate(vis)
        ]
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
        if new != self._hover:
            self._hover = new
            return True
        return False

    def flip(self, step):
        """Page the grid by +-1 if a page exists in that direction."""
        new = self.pageno + step
        if 0 <= new * self.per_page < len(self.entries):
            self.pageno = new
            self._hover = None
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

    def draw(self, scr, hover):
        th = theme()
        scr.fill_rect(self.x, self.y, self.w, self.h, th.bg)
        for i, t in enumerate(self._tiles):
            t.draw(scr, self._hover == i)
        for which, rect, name, fb in (('l', self._arrow_l, 'left.pbm', _TRI_L),
                                      ('r', self._arrow_r, 'right.pbm', _TRI_R)):
            if not rect:
                continue
            rows = load_icon(name) or fb
            iw, ih = icon_size(rows)
            color = th.btn_hi if self._hover == which else th.text
            draw_icon(scr, rows, rect[0] + (rect[2] - iw) // 2,
                      rect[1] + (rect[3] - ih) // 2, color)
