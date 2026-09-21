#!/usr/bin/env bash
# Toggle del Media Widget — abre/cierra el popup.
# Pensado para el click-left del módulo pulseaudio de polybar o un bind de i3.
set -u

MAIN="$HOME/.config/media-widget/main.py"
PIDFILE="$HOME/.config/media-widget/.pid"
LOG="${XDG_RUNTIME_DIR:-/tmp}/media-widget.log"

kill_widget() {
  # 1) pidfile (método rápido y exacto)
  if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE" 2>/dev/null || true)
    if [ -n "$PID" ] && kill -0 "$PID" 2>/dev/null; then
      kill "$PID" 2>/dev/null
      rm -f "$PIDFILE"
      return 0
    fi
    rm -f "$PIDFILE"
  fi

  # 2) por ventana X (xdotool) — encuentra cualquier instancia,
  #    sin importar cómo se haya lanzado
  if command -v xdotool >/dev/null 2>&1; then
    for WIN in $(xdotool search --class media-widget 2>/dev/null); do
      PID=$(xdotool getwindowpid "$WIN" 2>/dev/null || true)
      [ -n "$PID" ] && kill "$PID" 2>/dev/null && return 0
    done
  fi

  # 3) barrido por cmdline (patrón que no coincide con este script)
  for P in $(pgrep -f "media-widget/main[.]py" 2>/dev/null); do
    kill "$P" 2>/dev/null && return 0
  done

  return 1
}

if kill_widget; then
  exit 0
fi

# no estaba abierto → abrir (con ruta absoluta para el pidfile)
nohup python3 "$MAIN" >> "$LOG" 2>&1 &
echo $! > "$PIDFILE"
exit 0