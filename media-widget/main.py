#!/usr/bin/env python3
"""Panel de control de audio estilo doty (volume_popup) para polybar/i3.

Secciones (replicadas del volume_popup/shell.qml de doty):
  0. Media       — portada 48px, título + cubos por reproductor, artista,
                   prev/play/next/intercambio-fuente, duración con barra.
  1. Output      — icono + "Output: N%" y Mute/Unmute; barra de bloques
                   (15 rectángulos que se llenan; clic/arrastre/rueda).
  2. Input       — igual para el micrófono.
  (App Volumes)  — barras de bloques por aplicación (sink-inputs).
  (Bluetooth)    — controles del reproductor BT si el sink es bluez.
  3. Devices     — desplegable con flecha  ▾ / ▸, Outputs y Inputs.
  (Diagnostics)  — servidor de audio, tasa de muestreo, salida.

Navegación por teclado (Tab cambia de sección, flechas/Enter/Esc) igual
que en doty, con el mismo highlight de foco.
"""

import hashlib
import json
import os
import signal
import subprocess
import sys
import threading
import time
import urllib.request
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk, Pango

import theme as theme_mod
from mpris import Mpris
from pulse import PactlWatcher, Pulse
from segbar import SegBar

DIR = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(os.path.expanduser("~"), ".cache", "media-widget")
COVERS = os.path.join(CACHE, "covers")
FOCUS_FILE = os.path.join(CACHE, "focus.json")
LOG = "/tmp/media-widget.log"
DEBUG = os.environ.get("MEDIA_WIDGET_DEBUG") == "1"


def dlog(msg):
    if DEBUG:
        sys.stderr.write("[debug] " + msg + "\n")
        sys.stderr.flush()

# Glifos exactos del volume_popup de doty (Material Design en FiraCode Nerd)
GLY_ART = "\uf0386"           # 󰎆 nota (fallback de portada)
GLY_SWITCH = "\uf0456"        # 󰑖 cambiar fuente
GLY_MUTED = "\uf075f"         # 󰝟 audio silenciado
GLY_BT = "\uf02cb"            # 󰋋 bluetooth
GLY_VOL = "\uf057e"           # 󰕾 volumen
GLY_MIC = "\uf036c"           # 󰍬 micrófono
GLY_MIC_MUTED = "\uf036d"     # 󰍭 micrófono silenciado
GLY_CHEV_DOWN = "\uf0140"     # 󰅀 flecha abajo (devices abierto)
GLY_CHEV_RIGHT = "\uf0142"    # 󰅂 flecha derecha (devices cerrado)
GLY_BT_PREV = "\uf0663"       # 󰙣 prev (bt)
GLY_BT_PLAY = "\uf040a"       # 󰐊 play (bt)
GLY_BT_NEXT = "\uf0661"       # 󰙡 next (bt)

SHORT_DURATION = 120          # ms intro (doty)
EXIT_DURATION = 100           # ms salida (doty)
MEDIA_ANIM_STEP = 16          # ms por frame de animaciones de media


def fmt_time(secs):
    if secs is None or secs < 0:
        return "0:00"
    m = int(secs // 60)
    s = int(secs % 60)
    return "%d:%02d" % (m, s)


def load_settings():
    path = os.path.join(DIR, "settings.json")
    defaults = {
        "width": 240,
        "position": "top-right",
        "margin_x": 8,
        "margin_y": 34,
    }
    try:
        with open(path) as f:
            data = json.load(f)
        for k in defaults:
            if k in data:
                defaults[k] = data[k]
    except (OSError, ValueError):
        pass
    return defaults


class MediaWidget(Gtk.Window):
    def __init__(self, settings, theme):
        # TOPLEVEL (no POPUP): con i3 una ventana POPUP nunca recibe foco de
        # teclado; una ventana normal+flotante (regla i3) sí.
        super().__init__(type=Gtk.WindowType.TOPLEVEL)
        self.settings = settings
        self.theme = theme
        self.colors = theme["colors"]

        self.pulse = Pulse()
        self.mpris = Mpris(self._on_players_changed)

        # estado de media
        self._players = []
        self._media = None
        self._media_t0 = time.time()
        self._cover_url = None
        self._cover_shown = None
        self._media_refresh_due = 0.0
        self._position_updates = 0

        # estado de audio
        self._pulse_last = 0.0
        self._pulse_force = False
        self._pulse_event_due = False
        self.pending = {"sink": None, "source": None, "apps": {}}
        self._sent = {"sink": None, "source": None, "apps": {}}
        self._pending_last = 0.0
        self._verify_due = False

        # navegación de teclado
        self.active_section = 0
        self.active_sub = 0
        self._focus_widget = None
        self._focus_applied = False
        self.devices_open = False
        self._closing = False
        self._opened = False
        self._intro_started = False
        self._shown_at = 0.0

        # animación de cambio de fuente
        self._switch_state = "idle"   # idle | out | in
        self._switch_target = None
        self._switch_step = 0

        self.set_title("media-widget")
        self.set_wmclass("media-widget", "media-widget")
        self.set_decorated(False)
        self.set_resizable(False)
        self.set_skip_taskbar_hint(True)
        self.set_keep_above(True)
        self.set_accept_focus(True)
        self.set_default_size(settings["width"], 1)
        self.set_position(Gtk.WindowPosition.NONE)
        self.connect("destroy", self._on_destroy)
        self.connect("focus-out-event", self._on_focus_out)
        self.connect("key-press-event", self._on_key)
        self.connect("show", self._on_show)

        self._setup_visual()
        self._setup_css()
        self._build_ui()

        # posición y estado inicial antes de mostrarlo (sin destellos)
        self._position_window()
        self.move(self._base_x, self._base_y - 44)
        self.set_opacity(0.0)

        # temporizadores
        self._tick_id = GLib.timeout_add(250, self._tick)
        self._vol_id = GLib.timeout_add(50, self._flush_volumes)
        self._pulse_fallback = GLib.timeout_add(2000, self._fallback_pulse)

        # watcher de eventos de audio (pactl subscribe)
        self.watcher = PactlWatcher(self._on_pulse_event)
        self.watcher.start()

        # cerrar con SIGTERM/SIGINT limpio
        for sig in (signal.SIGTERM, signal.SIGINT):
            signal.signal(sig, lambda *a: self._close_now())

    # ==================================================== setup básico
    def _setup_visual(self):
        screen = self.get_screen()
        rgba = screen.get_rgba_visual()
        self._rgba = rgba is not None
        if rgba:
            self.set_visual(rgba)
        self.set_app_paintable(rgba is not None)

    def _setup_css(self):
        css = theme_mod.build_css(self.theme, use_alpha=self._rgba)
        provider = Gtk.CssProvider()
        provider.load_from_data(css.encode("utf-8"))
        Gtk.StyleContext.add_provider_for_screen(
            self.get_screen(), provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)
        self._provider = provider

    # ====================================================== construcción
    def _build_ui(self):
        self.panel = Gtk.EventBox()
        self.panel.get_style_context().add_class("panel")
        self.add(self.panel)

        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        col.set_margin_start(10)
        col.set_margin_end(10)
        col.set_margin_top(10)
        col.set_margin_bottom(10)
        self.panel.add(col)
        self.body = col

        self._build_media_section()
        self._build_output_section()
        self._build_input_section()
        self._build_apps_section()
        self._build_bluetooth_section()
        self._build_devices_section()
        self._build_diagnostics()

        self.show_all()
        # estados iniciales (algunos widgets empiezan ocultos)
        self.media_section.set_visible(False)
        self.apps_box.set_visible(False)
        self.bt_box.set_visible(False)
        self.dev_dropdown.set_visible(False)
        self.out_bar.set_visible(False)
        self.in_bar.set_visible(False)
        self.squares_box.set_visible(False)
        self.switch_btn.set_visible(False)

    # -------------------------------------------------------- helpers
    def _label(self, text="", size="s9", cls="bold", expand=False,
               halign="start", ellipsize=False):
        lbl = Gtk.Label(label=text)
        ctx = lbl.get_style_context()
        ctx.add_class("t-accent")
        for c in cls.split():
            if c:
                ctx.add_class(c)
        if size:
            ctx.add_class(size)
        lbl.set_halign(Gtk.Align.START if halign == "start" else
                       Gtk.Align.END)
        if ellipsize:
            lbl.set_ellipsize(Pango.EllipsizeMode.END)
            lbl.set_max_width_chars(24)
        lbl.set_vexpand(False)
        if expand:
            lbl.set_hexpand(True)
        return lbl

    def _textbtn(self, text="", size="s9", cls="", on_click=None,
                 tooltip=None, halign="start"):
        b = Gtk.Button(label=text)
        ctx = b.get_style_context()
        ctx.add_class("textbtn")
        ctx.add_class(size)
        for c in cls.split():
            if c:
                ctx.add_class(c)
        b.set_can_focus(False)
        b.set_focus_on_click(False)
        b.set_relief(Gtk.ReliefStyle.NONE)
        b.set_valign(Gtk.Align.CENTER)
        b.set_halign(Gtk.Align.START if halign == "start" else Gtk.Align.END)
        if tooltip:
            b.set_tooltip_text(tooltip)
        if on_click:
            b.connect("clicked", on_click)
        return b

    def _sep(self, height=1):
        e = Gtk.EventBox()
        e.set_size_request(-1, height)
        e.get_style_context().add_class("sep")
        return e

    # ------------------------------------------------ sección: media
    def _build_media_section(self):
        sec = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.media_section = sec

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        # portada 48x48
        frame = Gtk.EventBox()
        frame.set_size_request(48, 48)
        frame.get_style_context().add_class("cover-frame")
        stack = Gtk.Stack()
        placeholder = Gtk.Label(label=GLY_ART)
        placeholder.get_style_context().add_class("t-accent")
        placeholder.get_style_context().add_class("s18")
        placeholder.set_halign(Gtk.Align.CENTER)
        placeholder.set_valign(Gtk.Align.CENTER)
        stack.add_named(placeholder, "placeholder")
        img = Gtk.Image()
        stack.add_named(img, "cover")
        stack.set_visible_child_name("placeholder")
        frame.add(stack)
        self.art_stack = stack
        self.art_img = img
        row.pack_start(frame, False, False, 0)

        # columna derecha
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        info.set_vexpand(True)

        title_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL,
                            spacing=6)
        self.title_l = self._label("", size="s9", expand=True,
                                   ellipsize=True)
        title_row.pack_start(self.title_l, True, True, 0)

        # cubos de fuentes (1 por reproductor; se muestran si hay >1)
        squares = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=3)
        squares.set_valign(Gtk.Align.CENTER)
        self.squares_box = squares
        title_row.pack_start(squares, False, False, 0)
        info.pack_start(title_row, False, False, 0)

        self.artist_l = self._label("", size="s8", cls="fg60", expand=True,
                                    ellipsize=True)
        info.pack_start(self.artist_l, False, False, 0)

        # controles: prev / play-pause / next / cambiar fuente
        ctr = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self.prev_btn = self._textbtn("prev", size="s9", tooltip="Anterior",
                                      on_click=self._on_media_prev)
        self.play_btn = self._textbtn("play", size="s9", tooltip="Reproducir",
                                      on_click=self._on_media_play)
        self.next_btn = self._textbtn("next", size="s9", tooltip="Siguiente",
                                      on_click=self._on_media_next)
        self.switch_btn = self._textbtn(GLY_SWITCH, size="s11",
                                        tooltip="Cambiar fuente",
                                        on_click=self._on_media_switch)
        ctr.pack_start(self.prev_btn, False, False, 0)
        ctr.pack_start(self.play_btn, False, False, 0)
        ctr.pack_start(self.next_btn, False, False, 0)
        ctr.pack_start(self.switch_btn, False, False, 0)
        info.pack_start(ctr, False, False, 0)

        # duración: pos + barra + total (solo si hay duración)
        prog = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.pos_l = self._label("0:00", size="s8", cls="")
        self.len_l = self._label("0:00", size="s8", cls="", halign="end")
        self.seek_bar = SegBar(self.colors, height=4, blocks=None,
                               on_set=self._on_seek, drag_emit=False)
        self.seek_bar.set_hexpand(True)
        prog.pack_start(self.pos_l, False, False, 0)
        prog.pack_start(self.seek_bar, True, True, 0)
        prog.pack_start(self.len_l, False, False, 0)
        self.progress_row = prog
        info.pack_start(prog, False, False, 0)

        row.pack_start(info, True, True, 0)
        sec.pack_start(row, False, False, 0)
        sec.pack_start(self._sep(1), False, False, 0)

        self.body.pack_start(sec, False, False, 0)

    def _clear_squares(self):
        for ch in self.squares_box.get_children():
            self.squares_box.remove(ch)
            ch.destroy()

    def _rebuild_squares(self):
        self._clear_squares()
        current = self._current_player_id()
        for pid in self._players:
            b = self._textbtn("", size="s8", cls="src-sq", halign="center",
                              tooltip=pid,
                              on_click=lambda w, p=pid: self._switch_to(p))
            b.set_size_request(6, 6)
            if pid == current:
                b.get_style_context().add_class("on")
            self.squares_box.pack_start(b, False, False, 0)
        self.squares_box.show_all()
        self.squares_box.set_visible(len(self._players) > 1)

    # --------------------------------------------- sección: output
    def _build_output_section(self):
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.out_title_l = self._label("", size="s9", expand=True)
        self.out_mute_btn = self._textbtn("Mute", size="s9", halign="end",
                                          tooltip="Silenciar salida",
                                          on_click=self._on_toggle_out_mute)
        header.pack_start(self.out_title_l, True, True, 0)
        header.pack_start(self.out_mute_btn, False, False, 0)
        self.out_bar = SegBar(self.colors, height=5, blocks=15,
                              on_set=self._on_out_vol)
        self.out_bar.set_hexpand(True)
        self.body.pack_start(header, False, False, 0)
        self.body.pack_start(self.out_bar, False, False, 0)

    # ---------------------------------------------- sección: input
    def _build_input_section(self):
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.in_title_l = self._label("", size="s9", expand=True)
        self.in_mute_btn = self._textbtn("Mute", size="s9", halign="end",
                                         tooltip="Silenciar micrófono",
                                         on_click=self._on_toggle_in_mute)
        header.pack_start(self.in_title_l, True, True, 0)
        header.pack_start(self.in_mute_btn, False, False, 0)
        self.in_bar = SegBar(self.colors, height=5, blocks=15,
                             on_set=self._on_in_vol)
        self.in_bar.set_hexpand(True)
        self.body.pack_start(header, False, False, 0)
        self.body.pack_start(self.in_bar, False, False, 0)

    # ------------------------------------------- sección: app volumes
    def _build_apps_section(self):
        title = self._label("App Volumes", size="s9")
        self.apps_title = title
        self.apps_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                spacing=4)
        self.body.pack_start(title, False, False, 0)
        self.body.pack_start(self.apps_box, False, False, 0)
        self._app_rows = {}   # index (sink-input) -> {row, label, bar}

    def _rebuild_app_rows(self):
        seen = set()
        for a in self.pulse.apps:
            idx = a["index"]
            row = self._app_rows.get(idx)
            if row is None:
                row = self._make_app_row(a)
                self._app_rows[idx] = row
                self.apps_box.pack_start(row["box"], False, False, 0)
            seen.add(idx)
            # eliminar el row si el nombre cambió
            if row["name"] != a["name"]:
                old = self._app_rows.pop(idx)
                old["box"].destroy()
                row = self._make_app_row(a)
                self._app_rows[idx] = row
                self.apps_box.pack_start(row["box"], False, False, 0)
                seen.discard(idx)
        for idx in [i for i in self._app_rows if i not in seen]:
            self._app_rows[idx]["box"].destroy()
            del self._app_rows[idx]
        self.apps_box.show_all()

    def _make_app_row(self, app):
        row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        name = self._label("", size="s8", cls="", ellipsize=True)
        bar = SegBar(self.colors, height=5, blocks=15,
                     on_set=lambda pct, i=app["index"]: self._on_app_vol(i,
                                                                         pct))
        bar.set_hexpand(True)
        row.pack_start(name, False, False, 0)
        row.pack_start(bar, False, False, 0)
        return {"box": row, "label": name, "bar": bar, "name": app["name"]}

    # ----------------------------------------- sección: bluetooth
    def _build_bluetooth_section(self):
        self.bt_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.bt_box.pack_start(self._sep(1), False, False, 0)
        bt_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        bt_row.set_margin_top(2)
        bprev = self._textbtn(GLY_BT_PREV, size="s11",
                              on_click=self._on_bt_prev)
        bplay = self._textbtn(GLY_BT_PLAY, size="s11",
                              on_click=self._on_bt_play)
        bnext = self._textbtn(GLY_BT_NEXT, size="s11",
                              on_click=self._on_bt_next)
        bt_row.pack_start(bprev, False, False, 0)
        bt_row.pack_start(bplay, False, False, 0)
        bt_row.pack_start(bnext, False, False, 0)
        self.bt_box.pack_start(bt_row, False, False, 0)
        self.body.pack_start(self.bt_box, False, False, 0)

    # ------------------------------------------- sección: devices
    def _build_devices_section(self):
        self.dev_header_btn = self._textbtn(
            "Devices " + GLY_CHEV_RIGHT, size="s9", halign="start",
            tooltip="Dispositivos", on_click=self._on_toggle_devices)
        self.dev_dropdown = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                    spacing=3)
        self.body.pack_start(self.dev_header_btn, False, False, 0)
        self.body.pack_start(self.dev_dropdown, False, False, 0)
        self._dev_rows = []

    def _rebuild_dev_rows(self):
        for ch in self.dev_dropdown.get_children():
            self.dev_dropdown.remove(ch)
            ch.destroy()
        self._dev_rows = []

        lbl = self._label("  Outputs", size="s8", cls="fg60")
        self.dev_dropdown.pack_start(lbl, False, False, 0)
        for s in self.pulse.sinks:
            mark = "*" if s["is_default"] else " "
            text = ("  %s %s" % (mark, s["description"][:30])).rstrip()
            btn = self._textbtn(text, size="s9",
                                cls="fg100" if s["is_default"] else "fg70",
                                tooltip=s["name"],
                                on_click=lambda w, d=s: self._on_pick_sink(d))
            btn.set_size_request(-1, 16)
            btn.set_halign(Gtk.Align.START)
            btn.get_style_context().add_class("dev-row")
            self.dev_dropdown.pack_start(btn, False, False, 0)
            self._dev_rows.append(btn)

        lbl = self._label("  Inputs", size="s8", cls="fg60")
        self.dev_dropdown.pack_start(lbl, False, False, 0)
        for s in self.pulse.sources:
            mark = "*" if s["is_default"] else " "
            text = ("  %s %s" % (mark, s["description"][:30])).rstrip()
            btn = self._textbtn(text, size="s9",
                                cls="fg100" if s["is_default"] else "fg70",
                                tooltip=s["name"],
                                on_click=lambda w, d=s: self._on_pick_source(d))
            btn.set_size_request(-1, 16)
            btn.set_halign(Gtk.Align.START)
            btn.get_style_context().add_class("dev-row")
            self.dev_dropdown.pack_start(btn, False, False, 0)
            self._dev_rows.append(btn)
        self.dev_dropdown.show_all()

    # --------------------------------------------- sección: diag
    def _build_diagnostics(self):
        self.diag_l = self._label("", size="s7", cls="fg50", expand=True)
        self.body.pack_start(self.diag_l, False, False, 0)

    # ====================================================== servicios
    def _on_players_changed(self):
        self._media_refresh()

    def _on_pulse_event(self):
        # PipeWire emite eventos casi continuos → refresco con intervalo mínimo
        if self._has_pending():
            # mientras hay volúmenes pendientes, verificar pronto la
            # confirmación del servidor (y nunca dejar que un refresco
            # sobrescriba el valor manual).
            if not self._verify_due:
                self._verify_due = True
                GLib.timeout_add(250, self._verify_pending)
            return
        if self._pulse_event_due:
            return
        self._pulse_event_due = True
        GLib.timeout_add(1500, self._pulse_event_flush)

    def _verify_pending(self):
        self._verify_due = False
        self._refresh_pulse_now()
        return False

    def _pulse_event_flush(self):
        self._pulse_event_due = False
        self._pulse_force = True
        self._refresh_pulse_now()
        return False

    def _on_show(self, _w):
        if self._intro_started:
            return
        self._intro_started = True
        self._shown_at = time.time()
        self._run_intro()
        GLib.timeout_add(120, self._refresh_pulse_now)
        # de-mapa: un solo re-present a los 80ms asegura el foco de i3 sin
        # pelearse con un clic del usuario
        GLib.timeout_add(80, self._re_present)

    def _re_present(self):
        self.present()
        return False

    def _position_window(self):
        screen = self.get_screen()
        geo = screen.get_monitor_geometry(0) \
            if screen.get_n_monitors() else screen.get_geometry()
        w = self.settings["width"]
        m = self.settings
        pos = m.get("position", "top-right")
        if pos == "top-left":
            x = geo.x + m["margin_x"]
        elif pos == "top-center":
            x = geo.x + (geo.width - w) // 2
        else:
            x = geo.x + geo.width - w - m["margin_x"]
        y = geo.y + m["margin_y"]
        self._base_x = x
        self._base_y = y
        self.move(x, y)

    # ------------------------------------------------------ animación
    def _run_intro(self):
        steps = int(SHORT_DURATION / 16)
        start_t = time.time()

        def step():
            t = time.time() - start_t
            p = min(1.0, t / (SHORT_DURATION / 1000.0))
            ease = p
            y = self._base_y - int(44 * (1.0 - ease))
            self.move(self._base_x, y)
            self.set_opacity(ease)
            return p < 1.0

        GLib.timeout_add(16, step)
        self.present()

    def _close_animated(self):
        if self._closing:
            return
        self._closing = True
        dlog("close animado")
        start_t = time.time()

        def step():
            t = time.time() - start_t
            p = min(1.0, t / (EXIT_DURATION / 1000.0))
            ease = p
            self.set_opacity(1.0 - ease)
            y = self._base_y - int(44 * ease)
            self.move(self._base_x, y)
            if p < 1.0:
                return True
            self.destroy()
            return False

        GLib.timeout_add(16, step)

    def _close_now(self):
        """Cierre inmediato (señales SIGTERM/SIGINT). toggle.sh y los tests
        dependen de que el proceso muera de verdad; el cierre animado
        puede tragarse la señal si el loop está ocupado."""
        if self._closing:
            return
        self._closing = True
        dlog("close inmediato (señal)")
        try:
            self.watcher.stop()
        except Exception:
            pass
        try:
            self.hide()
        except Exception:
            pass
        self.destroy()

    def _on_destroy(self, *_a):
        dlog("destroy -> main_quit")
        try:
            self.watcher.stop()
        except Exception:
            pass
        Gtk.main_quit()

    def _on_focus_out(self, _w, _ev):
        if self._closing:
            return True
        # gracia de mapeo: en i3 el foco puede perderse en el instante de
        # abrir (compitiendo con la ventana activa del usuario); no cerrar
        # durante los primeros 600ms para que el de-mapa/retry-present
        # pueda entregar el foco sin matar el widget.
        if self._shown_at and time.time() - self._shown_at < 0.6:
            dlog("focus-out ignorado (gracia de apertura)")
            return True
        dlog("focus-out -> cierre animado")
        self._close_animated()
        return True

    # ====================================================== timers
    def _tick(self):
        self._position_updates += 1
        self._update_media_position()
        if self._position_updates % 6 == 0:
            self._media_refresh()
        # volumen pendiente sin confirmar demasiado tiempo → descartar
        if self._pending_last and self._has_pending() and \
                time.time() - self._pending_last > 3.0:
            self.pending = {"sink": None, "source": None, "apps": {}}
            self._sent = {"sink": None, "source": None, "apps": {}}
            self._pending_last = 0.0
        if self._pulse_force or (time.time() - self._pulse_last >= 2.0):
            if not self._has_pending():
                self._refresh_pulse_now()
        return True

    def _fallback_pulse(self):
        if not self._has_pending() and time.time() - self._pulse_last >= 2.0:
            self._refresh_pulse_now()
        return True

    def _has_pending(self):
        return (self.pending["sink"] is not None or
                self.pending["source"] is not None or
                bool(self.pending["apps"]))

    def _flush_volumes(self):
        # Envía los valores pendientes (sin repetir si no cambiaron) pero NO
        # los limpia: se confirman cuando el snapshot del servidor coincide
        # (ver _update_pulse_ui). Así las flechas siguientes avanzan desde el
        # valor manual, no desde un snapshot obsoleto.
        pul = self.pulse
        if self.pending["sink"] is not None and pul.default_sink:
            if self._sent["sink"] != self.pending["sink"]:
                pul.set_sink_volume(pul.default_sink["index"],
                                    self.pending["sink"])
                self._sent["sink"] = self.pending["sink"]
        if self.pending["source"] is not None and pul.default_source:
            if self._sent["source"] != self.pending["source"]:
                pul.set_source_volume(pul.default_source["index"],
                                      self.pending["source"])
                self._sent["source"] = self.pending["source"]
        if self.pending["apps"]:
            for idx, pct in list(self.pending["apps"].items()):
                if self._sent["apps"].get(idx) != pct:
                    pul.set_input_volume(idx, pct)
                    self._sent["apps"][idx] = pct
        return True

    # ===================================================== media
    def _current_player_id(self):
        cur = self.mpris.current_source()
        if not cur and self._players:
            cur = self._players[0]
        return cur

    def _media_refresh(self):
        players = self.mpris.players()
        changed = players != self._players
        self._players = players

        if not players:
            if self._media is not None:
                self._media = None
            self.media_section.set_visible(False)
            self._save_focus(self.active_section, self.active_sub)
            return

        if changed:
            self._rebuild_squares()
            self.switch_btn.set_visible(len(players) > 1)
            cur = self._current_player_id()
            if cur not in players:
                cur = players[0]
                self.mpris.persist(cur)

        cur = self._current_player_id()
        if cur is None:
            cur = players[0]
            self.mpris.persist(cur)

        snap = self.mpris.read(cur)
        if snap is None:
            return
        old = self._media
        self._media = snap
        self._media_t0 = time.time()
        self.media_section.set_visible(True)
        self.media_section.show_all()
        self._apply_media(snap, changed=changed)

    def _apply_media(self, snap, changed=False):
        fresh = (self._media_prev_fields if hasattr(self, "_media_prev_fields")
                 else None)
        fields = (snap["title"], snap["artist"], snap.get("player"),
                  snap["status"], snap["length"])
        dlog("media: player=%s title=%r status=%s len=%.1f pos=%.1f art=%s"
             % (snap.get("player"), snap["title"], snap["status"],
                snap.get("length") or 0, snap.get("position") or 0,
                bool(snap.get("art_url"))))
        if fresh != fields or changed:
            self.title_l.set_text(snap["title"] or snap.get("player") or "")
            artist = snap.get("artist") or ""
            if artist:
                artist = artist + " • " + snap.get("player", "")
            self.artist_l.set_text(artist)
            self.play_btn.set_label(
                "pause" if snap["status"] == "Playing" else "play")
            self._media_prev_fields = fields
        # visibilidades (show_all() las re-muestra; se re-aplican aquí)
        self.switch_btn.set_visible(len(self._players) > 1)
        self.squares_box.set_visible(len(self._players) > 1)
        self.progress_row.set_visible(bool(snap.get("length")))
        if snap.get("art_url") != self._cover_shown:
            self._cover_shown = snap.get("art_url")
            self._load_cover(snap.get("art_url"))
        self._update_media_position(force=True)

    def _update_media_position(self, force=False):
        snap = self._media
        if not snap:
            return
        status = snap.get("status")
        pos = snap.get("position") or 0.0
        if status == "Playing":
            pos += time.time() - self._media_t0
        length = snap.get("length") or 0.0
        if length and pos > length:
            pos = length
        self.pos_l.set_text(fmt_time(pos))
        self.len_l.set_text(fmt_time(length))
        if self.seek_bar._dragging:
            return
        if length:
            self.seek_bar.set_value(pos / length * 100.0)

    def _on_media_prev(self, _w=None):
        dlog("media action: previous")
        cur = self._current_player_id()
        self.mpris.action(cur, "previous")
        self._media_refresh_after_action()

    def _on_media_play(self, _w=None):
        cur = self._current_player_id()
        dlog("media action: play-pause (cur=%s)" % cur)
        if self._media:
            self._media["status"] = (
                "Paused" if self._media["status"] == "Playing" else "Playing")
            self._media_t0 = time.time()
            self.play_btn.set_label("pause"
                                    if self._media["status"] == "Playing"
                                    else "play")
            self.mpris.action(cur, "play-pause")
        else:
            self.mpris.action(cur, "play")
        self._media_refresh_after_action()

    def _on_media_next(self, _w=None):
        dlog("media action: next")
        cur = self._current_player_id()
        self.mpris.action(cur, "next")
        self._media_refresh_after_action()

    def _media_refresh_after_action(self):
        GLib.timeout_add(250, self._media_refresh)

    def _on_media_switch(self, _w=None):
        dlog("media action: switch")
        if len(self._players) < 2:
            return
        cur = self._current_player_id()
        try:
            i = self._players.index(cur)
        except ValueError:
            i = -1
        nxt = self._players[(i + 1) % len(self._players)]
        self._switch_to(nxt)

    def _switch_to(self, player_id):
        if self._switch_state != "idle":
            return
        self._switch_target = player_id
        self._switch_state = "out"
        self._switch_step = 0
        GLib.timeout_add(MEDIA_ANIM_STEP, self._switch_anim)

    def _switch_anim(self):
        if self._switch_state == "out":
            self._switch_step += 1
            p = min(1.0, self._switch_step * MEDIA_ANIM_STEP / 140.0)
            self.media_section.set_opacity(1.0 - p)
            if p < 1.0:
                return True
            # aplicar cambio
            self.mpris.persist(self._switch_target)
            self._media = None
            self._media_refresh()
            self._rebuild_squares()
            self._switch_state = "in"
            self._switch_step = 0
            return True
        if self._switch_state == "in":
            self._switch_step += 1
            p = min(1.0, self._switch_step * MEDIA_ANIM_STEP / 240.0)
            self.media_section.set_opacity(p)
            if p < 1.0:
                return True
            self.media_section.set_opacity(1.0)
            self._switch_state = "idle"
        return False

    def _on_seek(self, pct):
        snap = self._media
        if not snap or not snap.get("length"):
            return
        target = snap["length"] * (pct / 100.0)
        snap["position"] = target
        snap["status"] = snap.get("status", "Paused")
        self._media_t0 = time.time()
        self._update_media_position(force=True)
        cur = self._current_player_id()
        if cur:
            self.mpris.action(cur, "position", target)
            self._media_refresh_after_action()

    # portada ----------------------------------------------------
    def _load_cover(self, url):
        if not url:
            self.art_stack.set_visible_child_name("placeholder")
            return

        def _download():
            try:
                os.makedirs(COVERS, exist_ok=True)
                digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]
                path = os.path.join(COVERS, digest + ".png")
                data = None
                if os.path.exists(path):
                    with open(path, "rb") as f:
                        data = f.read()
                else:
                    req = urllib.request.Request(
                        url, headers={"User-Agent": "media-widget/1.0"})
                    with urllib.request.urlopen(req, timeout=8) as r:
                        data = r.read()
                    with open(path, "wb") as f:
                        f.write(data)
                if data is None:
                    return
                loader = GdkPixbuf.PixbufLoader.new()
                try:
                    loader.write(data)
                    loader.close()
                    pix = loader.get_pixbuf()
                except Exception:
                    pix = None
                if pix is None:
                    return
                pix = pix.scale_simple(48, 48, GdkPixbuf.InterpType.BILINEAR)
                GLib.idle_add(self._set_cover, pix)
            except Exception:
                pass

        t = threading.Thread(target=_download, daemon=True)
        t.start()

    def _set_cover(self, pix):
        self.art_img.set_from_pixbuf(pix)
        self.art_stack.set_visible_child_name("cover")
        return False

    # ===================================================== volumen
    def _refresh_pulse_now(self):
        try:
            self.pulse.refresh()
        except Exception:
            return
        self._pulse_last = time.time()
        self._pulse_force = False
        self._update_pulse_ui()
        if not self._focus_applied:
            self._focus_applied = True
            GLib.timeout_add(50, self._apply_focus)

    def _update_pulse_ui(self):
        color = self.colors
        sink = self.pulse.default_sink
        src = self.pulse.default_source

        # output
        if sink:
            disp = (self.pending["sink"] if self.pending["sink"] is not None
                    else sink["volume"])
            if self.pending["sink"] is not None and \
                    abs(sink["volume"] - self.pending["sink"]) <= 2:
                self.pending["sink"] = None
                self._sent["sink"] = None
                self._pending_last = 0.0 if not self._has_pending() \
                    else self._pending_last
                disp = sink["volume"]
            if sink["muted"]:
                title = GLY_MUTED + " Output: Muted"
            else:
                glyph = GLY_BT if sink["is_bluetooth"] else GLY_VOL
                title = "%s Output: %d%%" % (glyph, disp)
            self.out_title_l.set_text(title)
            self.out_mute_btn.set_label("Unmute" if sink["muted"] else "Mute")
            if not sink["muted"]:
                self.out_bar.set_visible(True)
                self.out_bar.set_value(disp)
            else:
                self.out_bar.set_visible(False)
        else:
            self.out_title_l.set_text(GLY_VOL + " Output: 0%")

        # input
        if src:
            disp = (self.pending["source"] if self.pending["source"]
                    is not None else src["volume"])
            if self.pending["source"] is not None and \
                    abs(src["volume"] - self.pending["source"]) <= 2:
                self.pending["source"] = None
                self._sent["source"] = None
                self._pending_last = 0.0 if not self._has_pending() \
                    else self._pending_last
                disp = src["volume"]
            if src["muted"]:
                title = GLY_MIC_MUTED + " Input: Muted"
            else:
                title = "%s Input: %d%%" % (GLY_MIC, disp)
            self.in_title_l.set_text(title)
            self.in_mute_btn.set_label("Unmute" if src["muted"] else "Mute")
            if not src["muted"]:
                self.in_bar.set_visible(True)
                self.in_bar.set_value(disp)
            else:
                self.in_bar.set_visible(False)
        else:
            self.in_title_l.set_text(GLY_MIC + " Input: 0%")

        # app volumes
        self._rebuild_app_rows()
        for a in self.pulse.apps:
            row = self._app_rows.get(a["index"])
            if row is None:
                continue
            pend = self.pending["apps"].get(a["index"])
            if pend is not None and abs(a["volume"] - pend) <= 2:
                del self.pending["apps"][a["index"]]
                self._sent["apps"].pop(a["index"], None)
                self._pending_last = 0.0 if not self._has_pending() \
                    else self._pending_last
                pend = None
            disp = pend if pend is not None else a["volume"]
            name = a["name"][:20]
            row["label"].set_text("%s (%d%%)" % (name, disp))
            if not a["muted"]:
                row["bar"].set_value(disp)
        self.apps_title.set_visible(bool(self.pulse.apps))
        self.apps_box.set_visible(bool(self.pulse.apps))

        # bluetooth
        bt = bool(sink and sink["is_bluetooth"])
        self.bt_box.set_visible(bt)

        # devices
        if self.devices_open:
            self._rebuild_dev_rows()

        # diagnóstico
        d = self.pulse.diagnostics
        self.diag_l.set_text("%s: Running | Rate: %s | Output: %s"
                             % (d["server"], d["rate"], d["output"]))
        dlog("pulse: sink=%s vol=%s muted=%s | src=%s vol=%s muted=%s | "
             "apps=%d sinks=%d sources=%d bt=%s"
             % (sink and sink["name"], sink and sink["volume"],
                sink and sink["muted"], src and src["name"],
                src and src["volume"], src and src["muted"],
                len(self.pulse.apps), len(self.pulse.sinks),
                len(self.pulse.sources),
                bool(sink and sink["is_bluetooth"])))

    def _on_out_vol(self, pct):
        dlog("volume: sink -> %d%%" % pct)
        self.out_bar.set_value(pct)
        self.pending["sink"] = pct
        self._pending_last = time.time()
        if self.pulse.default_sink:
            self.out_title_l.set_text("%s Output: %d%%"
                                      % (GLY_VOL, pct))

    def _on_in_vol(self, pct):
        dlog("volume: source -> %d%%" % pct)
        self.in_bar.set_value(pct)
        self.pending["source"] = pct
        self._pending_last = time.time()
        if self.pulse.default_source:
            self.in_title_l.set_text("%s Input: %d%%" % (GLY_MIC, pct))

    def _on_app_vol(self, idx, pct):
        row = self._app_rows.get(idx)
        if row:
            row["bar"].set_value(pct)
        self.pending["apps"][idx] = pct
        self._pending_last = time.time()

    def _on_toggle_out_mute(self, _w=None):
        if self.pulse.default_sink:
            self.pulse.toggle_sink_mute(self.pulse.default_sink["index"])
            self._pulse_force = True
            GLib.timeout_add(200, self._refresh_pulse_now)

    def _on_toggle_in_mute(self, _w=None):
        if self.pulse.default_source:
            self.pulse.toggle_source_mute(self.pulse.default_source["index"])
            self._pulse_force = True
            GLib.timeout_add(200, self._refresh_pulse_now)

    def _on_pick_sink(self, dev):
        dlog("devices: pick sink %r" % dev["name"])
        self.pulse.set_default_sink(dev["name"])
        self._pulse_force = True
        GLib.timeout_add(150, self._refresh_pulse_now)

    def _on_pick_source(self, dev):
        dlog("devices: pick source %r" % dev["name"])
        self.pulse.set_default_source(dev["name"])
        self._pulse_force = True
        GLib.timeout_add(150, self._refresh_pulse_now)

    def _on_toggle_devices(self, _w=None):
        self.devices_open = not self.devices_open
        dlog("devices dropdown -> %s" % ("open" if self.devices_open else "closed"))
        self.dev_header_btn.set_label(
            "Devices " +
            (GLY_CHEV_DOWN if self.devices_open else GLY_CHEV_RIGHT))
        if self.devices_open:
            self._rebuild_dev_rows()
        self.dev_dropdown.set_visible(self.devices_open)
        mx = self._max_items(3)
        if self.active_sub >= mx:
            self.active_sub = max(0, mx - 1)
        self._apply_focus()

    # bluetooth media ---------------------------------------------
    def _bt_cmd(self, cmd):
        try:
            subprocess.run(["playerctl", cmd], capture_output=True,
                           timeout=5)
        except Exception:
            pass

    def _on_bt_prev(self, _w=None):
        cur = self._current_player_id()
        if cur:
            self.mpris.action(cur, "previous")
        self._bt_cmd("previous")

    def _on_bt_play(self, _w=None):
        cur = self._current_player_id()
        if cur:
            self.mpris.action(cur, "play-pause")
        self._bt_cmd("play-pause")

    def _on_bt_next(self, _w=None):
        cur = self._current_player_id()
        if cur:
            self.mpris.action(cur, "next")
        self._bt_cmd("next")

    # ===================================================== teclado
    def _max_items(self, sec):
        if sec == 0:
            if not self._media:
                return 0
            n = 3
            if len(self._players) > 1:
                n += 1
            if self._media.get("length"):
                n += 1
            return n
        if sec == 1:
            sink = self.pulse.default_sink
            return 2 if (sink and not sink["muted"]) else 1
        if sec == 2:
            src = self.pulse.default_source
            return 2 if (src and not src["muted"]) else 1
        if sec == 3:
            n = 1
            if self.devices_open:
                n += len(self.pulse.sinks) + len(self.pulse.sources)
            return n
        if sec == 4:
            return len(self.pulse.apps)
        return 0

    def _media_items(self):
        items = ["prev", "play", "next"]
        if len(self._players) > 1:
            items.append("switch")
        if self._media and self._media.get("length"):
            items.append("slider")
        return items

    def _device_item(self, sub):
        if sub == 0:
            return {"type": "header"}
        current = 1
        for i in range(len(self.pulse.sinks)):
            if current == sub:
                return {"type": "sink", "index": i,
                        "data": self.pulse.sinks[i]}
            current += 1
        for j in range(len(self.pulse.sources)):
            if current == sub:
                return {"type": "source", "index": j,
                        "data": self.pulse.sources[j]}
            current += 1
        return None

    def _on_key(self, _w, ev):
        key = ev.keyval
        state = ev.state & Gdk.ModifierType.SHIFT_MASK
        ctrl = ev.state & Gdk.ModifierType.CONTROL_MASK
        dlog("key: %s (send=%s)" % (Gdk.keyval_name(key) or "?",
                                    getattr(ev, "send_event", False)))
        if key == Gdk.KEY_Escape:
            self._close_animated()
            return True
        if key == Gdk.KEY_Tab:
            self._cycle_section(1 if not state else -1)
            return True
        if key in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right,
                   Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._handle_nav(key, ctrl=ctrl)
            return True
        return False

    def _cycle_section(self, direction):
        start = self.active_section
        sec = (self.active_section + direction) % 5
        tries = 0
        while self._max_items(sec) == 0 and tries < 5:
            sec = (sec + direction) % 5
            tries += 1
        if self._max_items(sec) > 0:
            self.active_section = sec
            self.active_sub = 0
            self._apply_focus(cycle=True)

    def _handle_nav(self, key, ctrl=False):
        if key in (Gdk.KEY_Down, Gdk.KEY_Up):
            direction = 1 if key == Gdk.KEY_Down else -1
            self._navigate_sub(direction)
        elif key == Gdk.KEY_Right:
            if not self._adjust_slider(1):
                self._navigate_sub(1)
        elif key == Gdk.KEY_Left:
            if not self._adjust_slider(-1):
                self._navigate_sub(-1)
        else:  # Enter / space
            self._trigger_active()

    def _navigate_sub(self, direction):
        mx = self._max_items(self.active_section)
        if mx > 0:
            self.active_sub = (self.active_sub + direction + mx) % mx
        else:
            self.active_sub = 0
        self._apply_focus()

    def _adjust_slider(self, direction):
        sec = self.active_section
        sub = self.active_sub
        if sec == 0:
            items = self._media_items()
            if sub < len(items) and items[sub] == "slider":
                if self._media and self._media.get("length"):
                    pos = self._media.get("position") or 0.0
                    length = self._media["length"]
                    target = max(0.0, min(length, pos + direction * 5))
                    self._media["position"] = target
                    self._media_t0 = time.time()
                    self._update_media_position(force=True)
                    self.mpris.action(self._current_player_id(),
                                      "position", target)
                    self._media_refresh_after_action()
                return True
            return False
        if sec == 1 and sub == 1:
            sink = self.pulse.default_sink
            if sink and not sink["muted"]:
                base = (self.pending["sink"]
                        if self.pending["sink"] is not None
                        else sink["volume"])
                new = max(0, min(100, base + direction * 5))
                self.pending["sink"] = new
                self._pending_last = time.time()
                self.out_bar.set_value(new)
                self.out_title_l.set_text("%s Output: %d%%"
                                          % (GLY_VOL, new))
                return True
        elif sec == 2 and sub == 1:
            src = self.pulse.default_source
            if src and not src["muted"]:
                base = (self.pending["source"]
                        if self.pending["source"] is not None
                        else src["volume"])
                new = max(0, min(100, base + direction * 5))
                self.pending["source"] = new
                self._pending_last = time.time()
                self.in_bar.set_value(new)
                self.in_title_l.set_text("%s Input: %d%%"
                                         % (GLY_MIC, new))
                return True
        elif sec == 4:
            if sub < len(self.pulse.apps):
                app = self.pulse.apps[sub]
                base = (self.pending["apps"].get(app["index"])
                        if self.pending["apps"].get(app["index"]) is not None
                        else app["volume"])
                new = max(0, min(100, base + direction * 5))
                self.pending["apps"][app["index"]] = new
                self._pending_last = time.time()
                row = self._app_rows.get(app["index"])
                if row:
                    row["bar"].set_value(new)
                return True
        return False

    def _trigger_active(self):
        sec = self.active_section
        sub = self.active_sub
        dlog("trigger: sec=%d sub=%d" % (sec, sub))
        if sec == 0:
            items = self._media_items()
            if sub >= len(items):
                return
            item = items[sub]
            if item == "prev":
                self._on_media_prev()
            elif item == "play":
                self._on_media_play()
            elif item == "next":
                self._on_media_next()
            elif item == "switch":
                self._on_media_switch()
        elif sec == 1 and sub == 0:
            self._on_toggle_out_mute()
        elif sec == 2 and sub == 0:
            self._on_toggle_in_mute()
        elif sec == 3:
            dev = self._device_item(sub)
            if dev is None:
                return
            if dev["type"] == "header":
                self._on_toggle_devices()
            elif dev["type"] == "sink":
                self._on_pick_sink(dev["data"])
            elif dev["type"] == "source":
                self._on_pick_source(dev["data"])
        # sec 4 (apps): sin acción al pulsar, solo barras

    # foco ---------------------------------------------------------
    def _focus_widget_for(self, sec, sub):
        if sec == 0:
            items = self._media_items()
            if sub >= len(items):
                return None
            name = items[sub]
            return {"prev": self.prev_btn, "play": self.play_btn,
                    "next": self.next_btn, "switch": self.switch_btn,
                    "slider": self.seek_bar}.get(name)
        if sec == 1:
            return [self.out_mute_btn, self.out_bar][sub] \
                if sub < 2 else None
        if sec == 2:
            return [self.in_mute_btn, self.in_bar][sub] if sub < 2 else None
        if sec == 3:
            if sub == 0:
                return self.dev_header_btn
            i = sub - 1
            return self._dev_rows[i] if i < len(self._dev_rows) else None
        if sec == 4:
            if sub < len(self.pulse.apps):
                row = self._app_rows.get(self.pulse.apps[sub]["index"])
                return row["bar"] if row else None
        return None

    def _apply_focus(self, cycle=False):
        if self._focus_widget is not None:
            try:
                self._focus_widget.get_style_context().remove_class(
                    "focused")
            except Exception:
                pass
        if not cycle and self._max_items(self.active_section) == 0:
            return
        w = self._focus_widget_for(self.active_section, self.active_sub)
        self._focus_widget = w
        if w is not None:
            w.get_style_context().add_class("focused")
        dlog("nav: sec=%d sub=%d widget=%s"
             % (self.active_section, self.active_sub,
                w and w.__class__.__name__ or "None"))
        self._save_focus(self.active_section, self.active_sub)

    # persistencia de foco ----------------------------------------
    def _save_focus(self, sec, sub):
        try:
            os.makedirs(CACHE, exist_ok=True)
            with open(FOCUS_FILE, "w") as f:
                json.dump([sec, sub], f)
        except OSError:
            pass

    def _load_focus(self):
        try:
            with open(FOCUS_FILE) as f:
                sec, sub = json.load(f)
            self.active_section = max(0, min(4, int(sec)))
            self.active_sub = max(0, int(sub))
        except (OSError, ValueError, TypeError):
            pass


def main():
    settings = load_settings()
    theme = theme_mod.load_theme()
    win = MediaWidget(settings, theme)
    win._load_focus()
    win.show_all()
    Gtk.main()


if __name__ == "__main__":
    main()