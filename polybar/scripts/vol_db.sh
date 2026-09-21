#!/usr/bin/env sh
# Decibelios del sink por defecto para polybar (custom/script).
# Ej.: "-20,81 dB" (formato según locale). Vacío cuando está muteado
# (el módulo se oculta y el estado mute lo muestra el icono).
set -u

M=$(pactl get-sink-mute @DEFAULT_SINK@ 2>/dev/null)
case "$M" in
  *yes*|*sí*) exit 0 ;;
esac

V=$(pactl get-sink-volume @DEFAULT_SINK@ 2>/dev/null | head -1)
DB=$(printf '%s' "$V" | grep -oE '\-?[0-9]+[,.][0-9]+ ?dB' | head -1)
[ -n "$DB" ] && printf '%s\n' "$DB"