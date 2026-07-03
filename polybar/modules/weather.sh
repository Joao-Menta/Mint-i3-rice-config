#!/bin/bash
JSON=$(curl -s "wttr.in/Rancagua?format=j1" 2>/dev/null)
if [ -z "$JSON" ]; then
    echo "?°C"
    exit
fi
TEMP=$(echo "$JSON" | python3 -c "
import sys,json
w=json.load(sys.stdin)
print(w['current_condition'][0]['temp_C'] + '°C')
")
echo "$TEMP"
