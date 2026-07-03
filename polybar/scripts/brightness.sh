#!/usr/bin/env sh

BACKLIGHT="/sys/class/backlight/intel_backlight"
MAX=$(cat "$BACKLIGHT/max_brightness" 2>/dev/null || echo 0)
CUR=$(cat "$BACKLIGHT/brightness" 2>/dev/null || echo 0)

if [ "$MAX" = 0 ]; then
    echo "N/A"
    exit 0
fi

PCT=$(( CUR * 100 / MAX ))

case "$1" in
    status)
        if [ "$PCT" -gt 80 ]; then
            echo "󰃠 $PCT%"
        elif [ "$PCT" -gt 50 ]; then
            echo "󰃟 $PCT%"
        elif [ "$PCT" -gt 20 ]; then
            echo "󰃝 $PCT%"
        else
            echo "󰃜 $PCT%"
        fi
        ;;
    up)
        VAL=$(( CUR + MAX / 20 ))
        [ "$VAL" -gt "$MAX" ] && VAL=$MAX
        echo "$VAL" | sudo tee "$BACKLIGHT/brightness" >/dev/null 2>&1
        ;;
    down)
        VAL=$(( CUR - MAX / 20 ))
        [ "$VAL" -lt 1 ] && VAL=1
        echo "$VAL" | sudo tee "$BACKLIGHT/brightness" >/dev/null 2>&1
        ;;
esac
