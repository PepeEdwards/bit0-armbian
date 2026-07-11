"""UI core for the Bit0 launcher (audit 6.1).

Widget: a rectangle that composes itself into the Screen's scene buffer
and never flushes - the launcher's render tick is the single flush point.
Page: an ordered widget list with one hover index (audit 6.4 grows this
into a keyboard focus ring). Router: a page stack (push/pop for settings).

Layout containers (vstack/hstack in widgets.py) assign widget rects up
front and pages hold the flattened list: on a 320x240 screen with no
nested scrolling, a recursive tree would only add recursive hit-testing
and dirty bookkeeping for nothing.
"""

from .theme import current as theme


class Widget:
    """Base widget. Subclasses override draw() (compose into the scene,
    never flush) and optionally the input hooks."""

    is_value = False  # True: redraws from the State cache (Slider/LiveLabel)

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

    def draw(self, scr, hover):
        raise NotImplementedError

    def on_click(self, px, py):
        """Returns an action dict for the launcher loop, or None."""
        return None

    def on_drag(self, px, py):
        """Pointer tapped/held at (px, py). True if consumed (no click)."""
        return False

    def on_pointer(self, px, py):
        """Pointer position update for widgets with internal hover state
        (AppGrid tiles); (-1, -1) means the pointer left the widget.
        Returns True if a repaint is needed."""
        return False


class Page:
    def __init__(self, name, title, widgets):
        self.name = name
        self.title = title
        self.widgets = widgets
        self.hover = -1

    def widget_at(self, px, py):
        for i, w in enumerate(self.widgets):
            if w.contains(px, py):
                return i
        return -1

    def hovered(self):
        return self.widgets[self.hover] if self.hover >= 0 else None

    def pointer(self, px, py):
        """Move hover to the widget under the pointer, forwarding the
        position to widgets with internal hover; marks affected widgets
        dirty."""
        idx = self.widget_at(px, py)
        if idx != self.hover:
            if self.hover >= 0:
                old = self.widgets[self.hover]
                old.on_pointer(-1, -1)
                old.dirty = True
            if idx >= 0:
                self.widgets[idx].dirty = True
            self.hover = idx
        if idx >= 0 and self.widgets[idx].on_pointer(px, py):
            self.widgets[idx].dirty = True

    def compose(self, scr):
        """Compose the full page (background, title, widgets) into the
        scene buffer; the caller flushes."""
        th = theme()
        scr.fill_rect(0, 0, scr.w, scr.h, th.bg)
        s = 2
        tw = scr.text_width(self.title, s)
        scr.text(self.title, (scr.w - tw) // 2, 12, s, th.title)
        for i, w in enumerate(self.widgets):
            w.draw(scr, i == self.hover)
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
    """Page stack; `page` is the top. push/pop reset hover and mark the
    new page for a full recompose."""

    def __init__(self, pages, root):
        self.pages = pages
        self.stack = [root]

    @property
    def page(self):
        return self.pages[self.stack[-1]]

    def _enter(self):
        p = self.page
        p.hover = -1
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
