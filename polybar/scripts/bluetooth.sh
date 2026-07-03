#!/usr/bin/env sh

case "$1" in
    status)
        if ! command -v bluetoothctl >/dev/null 2>&1; then
            echo "N/A"
            exit 0
        fi
        state=$(bluetoothctl show | grep "Powered:" | awk '{print $2}')
        if [ "$state" = "yes" ]; then
            device_count=$(bluetoothctl devices Connected | wc -l)
            if [ "$device_count" -gt 0 ]; then
                echo " $device_count"
            else
                echo ""
            fi
        else
            echo ""
        fi
        ;;
    toggle)
        state=$(bluetoothctl show | grep "Powered:" | awk '{print $2}')
        if [ "$state" = "yes" ]; then
            bluetoothctl power off >/dev/null 2>&1
        else
            bluetoothctl power on >/dev/null 2>&1
        fi
        ;;
    menu)
        exec rofi -modi "bluetooth:${0%/*}/rofi-bluetooth" -show bluetooth
        ;;
esac
