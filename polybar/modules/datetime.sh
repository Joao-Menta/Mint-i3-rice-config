#!/bin/bash
# Reloj local sincronizado por NTP (systemd-timesyncd).
# El sistema ya esta sincronizado (offset ~35ms), asi que `date` es la hora oficial
# sin el desfase que metia el scraping HTTP + interval 30s + wttr.in bloqueante.
DATE=$(date '+%A, %d %B %Y  %H:%M:%S')

# Clima cacheado 10 min para no bloquear el tick de 1s
CACHE="/tmp/polybar-weather-cache"
TTL=600
WEATHER=""
if [ -f "$CACHE" ]; then
    AGE=$(( $(date +%s) - $(stat -c %Y "$CACHE" 2>/dev/null || echo 0) ))
    if [ "$AGE" -lt "$TTL" ]; then
        WEATHER=$(cat "$CACHE" 2>/dev/null)
    fi
fi
if [ -z "$WEATHER" ]; then
    JSON=$(curl -s --max-time 5 "wttr.in/Rancagua?format=j1" 2>/dev/null)
    if [ -n "$JSON" ]; then
        WEATHER=$(echo "$JSON" | python3 -c "import sys,json; w=json.load(sys.stdin); print(w['current_condition'][0]['temp_C']+'°C')" 2>/dev/null)
    fi
    if [ -n "$WEATHER" ]; then
        echo -n "$WEATHER" > "$CACHE" 2>/dev/null
    else
        WEATHER=$(cat "$CACHE" 2>/dev/null)
        [ -z "$WEATHER" ] && WEATHER="4°C"
    fi
fi
echo "$DATE  $WEATHER"
