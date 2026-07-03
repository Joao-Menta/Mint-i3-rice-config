#!/usr/bin/env sh

if ! command -v playerctl >/dev/null 2>&1; then
    echo "󰎆 no playerctl"
    exit 0
fi

STATUS=$(playerctl status 2>/dev/null)
if [ -z "$STATUS" ] || [ "$STATUS" = "Stopped" ]; then
    echo ""
    exit 0
fi

ARTIST=$(playerctl metadata artist 2>/dev/null)
TITLE=$(playerctl metadata title 2>/dev/null)

if [ -z "$ARTIST" ]; then
    INFO="$TITLE"
else
    INFO="$ARTIST - $TITLE"
fi

if [ ${#INFO} -gt 40 ]; then
    INFO="${INFO:0:38}…"
fi

case "$STATUS" in
    Playing)  echo "󰎆 $INFO" ;;
    Paused)   echo "󰏤 $INFO" ;;
esac
