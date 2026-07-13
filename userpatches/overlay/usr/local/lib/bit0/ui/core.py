"""UI core for the Bit0 launcher (audit 6.1).

Widget: a rectangle that composes itself into the Screen's scene buffer
and never flushes - the launcher's render tick is the single flush point.
Page: an ordered widget list with one focus index shared by pointer
hover and keyboard navigation (audit 6.4) - one concept, so highlight
code can't disagree. Router: a page stack (push/pop for settings).

Layout containers (vstack/hstack in widgets.py) assign widget rects up
front and pages hold the flattened list: on a 320x240 screen with no
nested scrolling, a recursive tree would only add recursive hit-testing
and dirty bookkeeping for nothing.
"""

from ..evdev import KEY_ENTER, KEY_KPENTER, KEY_SPACE, KEY_ESC
from .theme import current as theme


class Widget:
    """Base widget. Subclasses override draw() (compose into the scene,
    never flush) and optionally the input hooks."""

    is_value = False   # True: redraws from the State cache (Slider/LiveLabel)
    focusable = True   # False: skipped by the focus ring and pointer focus

    def __init__(self, x=0, y=0, w=0, h=0):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.dirty = True

    def contains(self, px, py):
        return (self.x <= px < self.x + self.w
                and self.y <= py < self.y + self.h)

    def flush_rect(self):
        """Rect the render tick flushes after draw(); overridden by widgets
        that compose outside their body (slider knob overhang). Invariant:
        draw() must fully repaint this rect - anything ever painted outside
        what is repainted becomes a stale trace when flushed alone."""
        return (self.x, self.y, self.w, self.h)

    def flush_rects(self):
        """Flush rectangles for this widget - a list so disjoint regions
        (mascot sprite + floating bubble) don't force one union rect
        whose margins would overpaint other widgets. The repaint
        invariant of flush_rect applies to each rect."""
        return [self.flush_rect()]

    def draw(self, scr, focused):
        raise NotImplementedError

    def on_click(self, px, py):
        """Returns an action dict for the launcher loop, or None."""
        return None

    def on_drag(self, px, py):
        """Pointer tapped/held at (px, py). True if consumed (no click)."""
        return False

    def on_pointer(self, px, py):
        """Pointer position update for widgets with internal focus state
        (AppGrid tiles); (-1, -1) means the pointer left the widget.
        Returns True if a repaint is needed."""
        return False

    def on_key(self, code):
        """Key hook for the focused widget, tried before page-level
        navigation. Returns an action dict, True if consumed, or
        None/False if unhandled."""
        return None

    def on_focus(self, gained):
        """Keyboard focus entered/left this widget (pointer moves go
        through on_pointer instead)."""

    def activate(self):
        """ENTER on the focused widget: same code path as a click."""
        return self.on_click(self.x, self.y)


class Page:
    def __init__(self, name, title, widgets):
        self.name = name
        self.title = title
        self.widgets = widgets
        self.focus = -1

    def widget_at(self, px, py):
        for i, w in enumerate(self.widgets):
            if w.contains(px, py):
                return i
        return -1

    def focused(self):
        return self.widgets[self.focus] if self.focus >= 0 else None

    def pointer(self, px, py):
        """Re-derive focus from hit-testing (pointer motion), forwarding
        the position to widgets with internal focus; marks affected
        widgets dirty."""
        idx = self.widget_at(px, py)
        if idx >= 0 and not self.widgets[idx].focusable:
            idx = -1
        if idx != self.focus:
            if self.focus >= 0:
                old = self.widgets[self.focus]
                old.on_pointer(-1, -1)
                old.dirty = True
            if idx >= 0:
                self.widgets[idx].dirty = True
            self.focus = idx
        if idx >= 0 and self.widgets[idx].on_pointer(px, py):
            self.widgets[idx].dirty = True

    def focus_step(self, step):
        """Move keyboard focus along the ring of focusable widgets,
        ordered by (y, x), wrapping at the ends."""
        ring = sorted((i for i, w in enumerate(self.widgets) if w.focusable),
                      key=lambda i: (self.widgets[i].y, self.widgets[i].x))
        if not ring:
            return
        if self.focus in ring:
            new = ring[(ring.index(self.focus) + step) % len(ring)]
        else:
            new = ring[0] if step > 0 else ring[-1]
        if new == self.focus:
            return
        if self.focus >= 0:
            old = self.widgets[self.focus]
            old.on_focus(False)
            old.dirty = True
        self.focus = new
        self.widgets[new].on_focus(True)
        self.widgets[new].dirty = True

    def compose(self, scr):
        """Compose the full page (background, title, widgets) into the
        scene buffer; the caller flushes."""
        th = theme()
        scr.fill_rect(0, 0, scr.w, scr.h, th.bg)
        s = 2
        tw = scr.text_width(self.title, s)
        scr.text(self.title, (scr.w - tw) // 2, 12, s, th.title)
        for i, w in enumerate(self.widgets):
            w.draw(scr, i == self.focus)
            w.dirty = False

    def mark_all(self):
        for w in self.widgets:
            w.dirty = True

    def mark_values(self):
        """Mark widgets that render State-cache values (volume %,
        brightness) for redraw."""
        for w in self.widgets:
            if w.is_value:
                w.dirty = True

    def dirty_widgets(self):
        return [w for w in self.widgets if w.dirty]


class Router:
    """Page stack; `page` is the top. push/pop reset focus and mark the
    new page for a full recompose.

    `overlay` (the mascot) gets input precedence per message class
    (audit 6.5.1): a modal (onboarding) head locks the UI - ALL keys are
    captured (ENTER/SPACE advance, ESC skips the queue, everything else
    is swallowed) and clicks anywhere advance. A casual head never
    captures keys and only a click ON the bubble dismisses it; the rest
    of the page stays live. The rules live here so widgets never need
    to know about the bubble."""

    def __init__(self, pages, root, overlay=None):
        self.pages = pages
        self.stack = [root]
        self.overlay = overlay

    def _overlay_active(self):
        o = self.overlay
        return o if (o and o.bubble_visible and o in self.page.widgets) \
            else None

    def intercept_key(self, code):
        """True if the overlay consumed the key (caller: full redraw)."""
        o = self._overlay_active()
        if not (o and o.locking):
            return False  # casual messages never capture keys
        if code in (KEY_ENTER, KEY_KPENTER, KEY_SPACE):
            o.advance()
        elif code == KEY_ESC:
            o.dismiss()
        return True  # modal: the UI is locked, swallow everything else

    def intercept_click(self, px, py):
        """True if the overlay consumed a click at (px, py)."""
        o = self._overlay_active()
        if not o:
            return False
        if o.locking:
            o.advance()  # modal: click anywhere advances
            return True
        if o.hit_bubble(px, py):
            o.advance()  # casual: only the bubble itself is a target
            return True
        return False

    @property
    def page(self):
        return self.pages[self.stack[-1]]

    def _enter(self):
        p = self.page
        p.focus = -1
        p.mark_all()
        return p

    def push(self, name):
        self.stack.append(name)
        return self._enter()

    def pop(self):
        if len(self.stack) > 1:
            self.stack.pop()
        return self._enter()

    def reset(self):
        """Back to the root page (after an app returns)."""
        del self.stack[1:]
        return self._enter()
