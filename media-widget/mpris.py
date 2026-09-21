"""Reproductor MPRIS multi-fuente vía GDBus (Spotify, Brave/YouTube, etc.).

Replica lo que hace el helper de doty + playerctl, pero sin dependencias:
lista los reproductores org.mpris.MediaPlayer2.* del bus de sesión, persiste
la selección actual en ~/.cache/media-widget/current_media_player y controla
el reproductor elegido por D-Bus (PlayPause/Next/Previous/SetPosition).
"""

import os

from gi.repository import Gio, GLib

PREFIX = "org.mpris.MediaPlayer2"
PATH = "/org/mpris/MediaPlayer2"
IFACE_PLAYER = "org.mpris.MediaPlayer2.Player"
IFACE_MEDIA = "org.mpris.MediaPlayer2"

_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "media-widget")
STATE_FILE = os.path.join(_CACHE, "current_media_player")


class Mpris(object):
    def __init__(self, on_change=None):
        self.on_change = on_change or (lambda: None)
        self.bus = None
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error:
            return
        self.bus.signal_subscribe(
            None, "org.freedesktop.DBus", "NameOwnerChanged",
            None, None, Gio.DBusSignalFlags.NONE, self._owner_changed, None)

    def _owner_changed(self, *args):
        self.on_change()

    # -------------------------------------------------------- helpers
    @staticmethod
    def _id(bus_name):
        return bus_name[len(PREFIX) + 1:]

    def players(self):
        if self.bus is None:
            return []
        try:
            res = self.bus.call_sync(
                "org.freedesktop.DBus", "/org/freedesktop/DBus",
                "org.freedesktop.DBus", "ListNames", None, None,
                Gio.DBusCallFlags.NONE, 2000, None)
        except GLib.Error:
            return []
        names = [n for n in (res and res.unpack()[0] or [])
                 if n.startswith(PREFIX + ".")]
        return sorted(self._id(n) for n in names)

    def identity(self, player_id):
        p = self._proxy(player_id, iface=IFACE_MEDIA)
        if p is None:
            return player_id
        try:
            v = p.get_cached_property("Identity")
            if v:
                return v.unpack()
        except GLib.Error:
            pass
        return player_id

    # ------------------------------------------------- selección
    def current_source(self):
        try:
            with open(STATE_FILE) as f:
                name = f.read().strip()
            if name and name in self.players():
                return name
        except OSError:
            pass
        return None

    def persist(self, player_id):
        try:
            os.makedirs(_CACHE, exist_ok=True)
            with open(STATE_FILE, "w") as f:
                f.write(player_id)
        except OSError:
            pass

    # ---------------------------------------------------- lectura
    def _proxy(self, player_id, iface=IFACE_PLAYER):
        try:
            return Gio.DBusProxy.new_sync(
                self.bus, Gio.DBusProxyFlags.NONE, None,
                PREFIX + "." + player_id, PATH, iface, None)
        except GLib.Error:
            return None

    def read(self, player_id):
        if self.bus is None:
            return None
        p = self._proxy(player_id)
        if p is None:
            return None
        m = {}
        mv = p.get_cached_property("Metadata")
        meta = mv.unpack() if mv else {}
        if not isinstance(meta, dict):
            meta = {}
        m["title"] = str(meta.get("xesam:title") or "")
        art = meta.get("xesam:artist") or []
        m["artist"] = (", ".join(str(a) for a in art)
                       if isinstance(art, list) else str(art))
        m["art_url"] = str(meta.get("mpris:artUrl") or "")
        m["track_id"] = str(meta.get("mpris:trackid") or "")
        try:
            m["length"] = int(meta.get("mpris:length") or 0) / 1e6
        except (TypeError, ValueError):
            m["length"] = 0.0
        sv = p.get_cached_property("PlaybackStatus")
        m["status"] = (sv.unpack() if sv else "Stopped") or "Stopped"
        pv = p.get_cached_property("Position")
        try:
            m["position"] = int(pv.unpack() if pv else 0) / 1e6
        except (TypeError, ValueError):
            m["position"] = 0.0
        m["player"] = player_id
        return m

    # ---------------------------------------------------- acciones
    def action(self, player_id, act, value=None):
        p = self._proxy(player_id)
        if p is None:
            return
        try:
            if act == "play-pause":
                p.call_sync("PlayPause", None, Gio.DBusCallFlags.NONE,
                            2000, None)
            elif act == "next":
                p.call_sync("Next", None, Gio.DBusCallFlags.NONE,
                            2000, None)
            elif act == "previous":
                p.call_sync("Previous", None, Gio.DBusCallFlags.NONE,
                            2000, None)
            elif act == "play":
                p.call_sync("Play", None, Gio.DBusCallFlags.NONE,
                            2000, None)
            elif act == "position":
                mv = p.get_cached_property("Metadata")
                meta = mv.unpack() if mv else {}
                if not isinstance(meta, dict):
                    meta = {}
                tid = str(meta.get("mpris:trackid")
                          or "/org/mpris/MediaPlayer2/TrackList/NoTrack")
                p.call_sync(
                    "SetPosition",
                    GLib.Variant("(ox)", (tid, int(float(value) * 1e6))),
                    Gio.DBusCallFlags.NONE, 2000, None)
        except GLib.Error:
            pass