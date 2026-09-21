"""Estado de PulseAudio/PipeWire vía pactl — equivalente al binario
get_audio_status de doty (volumen_popup). Devuelve sinks, sources,
apps (sink-inputs), default sink/source y diagnósticos."""

import json
import subprocess
import threading
import time

from gi.repository import GLib


def _run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              timeout=5).stdout or ""
    except Exception:
        return ""


def _json(args):
    try:
        return json.loads(_run(["pactl", "-f", "json"] + args))
    except (ValueError, json.JSONDecodeError):
        return []


def _first_pct(vol_obj):
    if not isinstance(vol_obj, dict):
        return 0
    vals = []
    for ch in vol_obj.values():
        if not isinstance(ch, dict):
            continue
        p = ch.get("value_percent")
        if isinstance(p, str):
            p = p.rstrip("%")
        try:
            vals.append(int(round(float(p))))
        except (TypeError, ValueError):
            continue
    return int(sum(vals) / len(vals)) if vals else 0


def _device_list(json_items, default_name):
    out = []
    for it in json_items:
        if not isinstance(it, dict):
            continue
        name = it.get("name", "")
        out.append({
            "index": it.get("index"),
            "name": name,
            "description": it.get("description", name),
            "volume": _first_pct(it.get("volume")),
            "muted": bool(it.get("mute")),
            "is_bluetooth": "bluez" in name.lower(),
            "is_default": name == default_name,
        })
    return out


class Pulse(object):
    """Snapshot de estado de audio + acciones pactl."""

    def __init__(self):
        self.default_sink = None
        self.default_source = None
        self.sinks = []
        self.sources = []
        self.apps = []
        self.diagnostics = {"server": "Running", "rate": "48kHz",
                            "output": "Default"}

    # -------------------------------------------------------- estado
    def refresh(self):
        dflt_sink = _run(["pactl", "get-default-sink"]).strip()
        dflt_src = _run(["pactl", "get-default-source"]).strip()
        self.sinks = _device_list(_json(["list", "sinks"]), dflt_sink)
        self.sources = _device_list(_json(["list", "sources"]), dflt_src)
        apps = []
        for it in _json(["list", "sink-inputs"]):
            if not isinstance(it, dict):
                continue
            props = it.get("properties") or {}
            name = (props.get("application.name") or props.get("media.name")
                    or "unknown")
            apps.append({
                "index": it.get("index"),
                "name": str(name),
                "volume": _first_pct(it.get("volume")),
                "muted": bool(it.get("mute")),
            })
        self.apps = apps
        self.default_sink = next((s for s in self.sinks if s["is_default"]),
                                 None)
        self.default_source = next(
            (s for s in self.sources if s["is_default"]), None)
        self._refresh_diagnostics()
        return self

    def _refresh_diagnostics(self):
        txt = _run(["pactl", "info"]).lower()
        rate = ""
        for tok in txt.replace("\n", " ").split():
            if tok.endswith("hz"):
                rate = tok
                break
        server = "PulseAudio" if "pipewire" not in txt else "PipeWire"
        self.diagnostics = {"server": server, "rate": rate or "??",
                            "output": "Default"}

    # ------------------------------------------------------ acciones
    def set_sink_volume(self, index, pct):
        _run(["pactl", "set-sink-volume", str(index), "%d%%" % pct])

    def set_source_volume(self, index, pct):
        _run(["pactl", "set-source-volume", str(index), "%d%%" % pct])

    def set_input_volume(self, index, pct):
        _run(["pactl", "set-sink-input-volume", str(index), "%d%%" % pct])

    def toggle_sink_mute(self, index):
        _run(["pactl", "set-sink-mute", str(index), "toggle"])

    def toggle_source_mute(self, index):
        _run(["pactl", "set-source-mute", str(index), "toggle"])

    def set_default_sink(self, name):
        """Establece default sink. En PulseAudio nativo basta pactl; en
        PipeWire/WirePlumber (p.ej. tarjetas 'mono' con nodos suspendidos)
        pactl no aplica el cambio, así que se verifica y se cae a
        pw-metadata (que escribe la metadata default.audio.sink)."""
        for cmd in (["pactl", "set-default-sink", name],
                    ["pw-metadata", "-n", "default", "0",
                     "default.audio.sink", '{"name":"%s"}' % name]):
            _run(cmd)
            if _run(["pactl", "get-default-sink"]).strip() == name:
                return

    def set_default_source(self, name):
        for cmd in (["pactl", "set-default-source", name],
                    ["pw-metadata", "-n", "default", "0",
                     "default.audio.source", '{"name":"%s"}' % name]):
            _run(cmd)
            if _run(["pactl", "get-default-source"]).strip() == name:
                return


class PactlWatcher(threading.Thread):
    """pactl subscribe → on_event() en el hilo principal de GLib.

    PipeWire traduce eventos de stream casi continuos (pueden llegar ~150
    por segundo), así que aquí se limita a un idle_add como mucho cada
    500ms para no saturar el main loop de GTK (la parte de UI ya coalesce
    además el refresco a un mínimo de 1.5s).
    """

    def __init__(self, on_event):
        super().__init__(daemon=True)
        self.on_event = on_event
        self.proc = None
        self._stop = threading.Event()

    def stop(self):
        """Termina el `pactl subscribe` hijo (idempotente).

        Sin esto, cada cierre del widget dejaba un `pactl subscribe`
        huérfano acumulándose; con suficientes, PipeWire alcanza
        `context.max-clients` (64) y los clientes nuevos (widget,
        polybar-vi) pierden la conexión con PulseAudio.
        """
        self._stop.set()
        if self.proc is not None:
            try:
                self.proc.terminate()
            except Exception:
                pass

    def run(self):
        try:
            self.proc = subprocess.Popen(["pactl", "subscribe"],
                                         stdout=subprocess.PIPE, text=True)
        except OSError:
            return
        last = 0.0
        for _line in self.proc.stdout:
            if self._stop.is_set():
                break
            now = time.time()
            if now - last >= 0.5:
                last = now
                GLib.idle_add(self.on_event)
        try:
            self.proc.wait()
        except Exception:
            pass