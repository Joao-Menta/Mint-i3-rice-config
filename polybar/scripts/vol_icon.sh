#!/usr/bin/env sh
# Icono de volumen para polybar (custom/script).
# Imprime el glifo Nerd Font según el nivel del sink por defecto,
# o "muted" (color disabled) cuando está muteado.
set -u

M=$(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null)
case "$M" in
  *yes*|*sí*) printf '%%{F#4c566a}muted%%{F-}\n'; exit 0 ;;
esac

V=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | head -1)
P=$(printf '%s' "$V" | grep -o '[0-9][0-9]*%' | head -1 | tr -d '%')
[ -z "$P" ] && P=0

if   [ "$P" -ge 67 ]; then printf '󰕾\n'
elif [ "$P" -ge 34 ]; then printf '󰖀\n'
else printf '󰕿\n'
fi