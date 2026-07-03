#!/bin/bash
DATE=$(date '+%A, %d %B %Y  %H:%M')
WEATHER=$({ echo "4°C"; } 2>/dev/null)
JSON=$(curl -s "wttr.in/Rancagua?format=j1" 2>/dev/null)
if [ -n "$JSON" ]; then
    WEATHER=$(echo "$JSON" | python3 -c "import sys,json; w=json.load(sys.stdin); print(w['current_condition'][0]['temp_C']+'°C')" 2>/dev/null)
fi
echo "$DATE  $WEATHER"
