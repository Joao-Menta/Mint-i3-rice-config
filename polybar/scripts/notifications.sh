#!/usr/bin/env sh

case "$1" in
    status)
        if command -v dunstctl >/dev/null 2>&1; then
            COUNT=$(dunstctl count waiting 2>/dev/null || echo 0)
            HIST=$(dunstctl count history 2>/dev/null || echo 0)
            if [ "$COUNT" -gt 0 ]; then
                echo "󰂚 $COUNT"
            elif [ "$HIST" -gt 0 ]; then
                echo "󰂛 $HIST"
            else
                echo "󰂜"
            fi
        else
            echo "N/A"
        fi
        ;;
    toggle)
        if command -v dunstctl >/dev/null 2>&1; then
            dunstctl set-paused toggle
        fi
        ;;
    history)
        if command -v dunstctl >/dev/null 2>&1; then
            dunstctl history-pop
        fi
        ;;
esac
