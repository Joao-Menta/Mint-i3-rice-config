"""Slider de bloques estilo doty: una fila de rectángulos que se llenan
según el valor, como en el volume_popup de doty. También sirve como barra
continua (blocks=None) para el progreso del reproductor.

- Clic/arrastre/rueda para cambiar el valor.
- on_set(pct) se llama cuando el usuario cambia el valor (0-100).
"""

from gi.repository import Gdk, Gtk


def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16) / 255.0,
            int(h[2:4], 16) / 255.0,
            int(h[4:6], 16) / 255.0)


class SegBar(Gtk.DrawingArea):
    def __init__(self, theme_colors, height=5, blocks=15, on_set=None,
                 drag_emit=True):
        super().__init__()
        self.colors = theme_colors
        self.height = max(2, int(height))
        self.blocks = blocks          # None → barra continua
        self.on_set = on_set
        self.drag_emit = drag_emit    # False → emite solo al soltar (seek)
        self.value = 0.0              # 0..100
        self._dragging = False
        self._last_emitted = 0.0

        self.set_size_request(-1, self.height + 6)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.SCROLL_MASK)
        self.connect("draw", self._draw)
        self.connect("button-press-event", self._on_press)
        self.connect("button-release-event", self._on_release)
        self.connect("motion-notify-event", self._on_motion)
        self.connect("scroll-event", self._on_scroll)
        self.connect("realize", self._on_realize)

    # ------------------------------------------------------ público
    def set_value(self, v):
        v = max(0.0, min(100.0, float(v)))
        if v != self.value:
            self.value = v
            self.queue_draw()

    def set_sensitive_bar(self, sensitive):
        self.set_sensitive(sensitive)

    # ------------------------------------------------------- eventos
    def _on_realize(self, _w):
        try:
            self.get_window().set_cursor(
                Gdk.Cursor.new_for_display(self.get_display(),
                                           Gdk.CursorType.HAND2))
        except Exception:
            pass

    def _fraction(self, x):
        alloc = self.get_allocation()
        w = max(1, alloc.width)
        return max(0.0, min(1.0, x / float(w)))

    def _emit(self):
        if self.on_set and self.value != self._last_emitted:
            self._last_emitted = self.value
            self.on_set(int(round(self.value)))

    def _apply(self, x, emit=True):
        pct = int(round(self._fraction(x) * 100))
        if pct != self.value:
            self.value = pct
            self.queue_draw()
            if emit:
                self._emit()

    def _on_press(self, _w, ev):
        self._dragging = True
        self._apply(ev.x)
        return True

    def _on_motion(self, _w, ev):
        if self._dragging:
            self._apply(ev.x, emit=self.drag_emit)
            return True
        return False

    def _on_release(self, _w, _ev):
        self._dragging = False
        if not self.drag_emit:
            self._emit()
        return False

    def _on_scroll(self, _w, ev):
        if ev.direction == Gdk.ScrollDirection.UP:
            delta = +2
        elif ev.direction == Gdk.ScrollDirection.DOWN:
            delta = -2
        else:
            return True
        new = max(0, min(100, int(self.value) + delta))
        if new != self.value:
            self.value = new
            self.queue_draw()
            self._emit()
        return True

    # --------------------------------------------------------- dibujo
    def _draw(self, w, cr):
        alloc = w.get_allocation()
        ww, hh = alloc.width, alloc.height
        bh = self.height
        y = max(0, (hh - bh) // 2)
        accent = _rgb(self.colors.get("accent", "#dcc66e"))
        track = _rgb(self.colors.get("bg_light", "#4b4739"))

        if self.blocks:
            n = self.blocks
            spacing = 1
            block_w = (ww - spacing * (n - 1)) / float(n)
            filled = int(round(self.value / 100.0 * n))
            x = 0.0
            for i in range(n):
                bx = int(x)
                bw = max(1, int(x + block_w) - bx)
                if i < filled:
                    cr.set_source_rgb(*accent)
                else:
                    cr.set_source_rgb(*track)
                cr.rectangle(bx, y, bw, bh)
                cr.fill()
                x += block_w + spacing
        else:
            fill = ww * (self.value / 100.0)
            cr.set_source_rgb(*track)
            cr.rectangle(0, y, ww, bh)
            cr.fill()
            cr.set_source_rgb(*accent)
            cr.rectangle(0, y, max(0, int(fill)), bh)
            cr.fill()
        return False