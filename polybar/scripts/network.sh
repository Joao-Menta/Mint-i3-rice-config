#!/usr/bin/env sh

get_wifi() {
    nmcli -t -f TYPE,DEVICE,STATE device status 2>/dev/null | grep "^wifi:" | cut -d: -f2 | head -1
}

get_eth() {
    nmcli -t -f TYPE,DEVICE,STATE device status 2>/dev/null | grep "^ethernet:" | cut -d: -f2 | head -1
}

WIFI_DEV=$(get_wifi)
ETH_DEV=$(get_eth)

WIFI_UP=false
ETH_UP=false
[ -n "$WIFI_DEV" ] && nmcli -t -f DEVICE,STATE device status 2>/dev/null | grep -q "^${WIFI_DEV}:connected" && WIFI_UP=true
[ -n "$ETH_DEV" ] && nmcli -t -f DEVICE,STATE device status 2>/dev/null | grep -q "^${ETH_DEV}:connected" && ETH_UP=true

case "$1" in
    status)
        OUTPUT=""
        if $ETH_UP; then
            IP=$(nmcli -t -f DEVICE,IP4.ADDRESS device show "$ETH_DEV" 2>/dev/null | grep "IP4.ADDRESS" | head -1 | cut -d: -f2 | cut -d/ -f1)
            OUTPUT="󰈀 $IP"
        fi
        if $WIFI_UP; then
            SIGNAL=$(nmcli -t -f ACTIVE,SIGNAL dev wifi list 2>/dev/null | grep "^yes" | cut -d: -f2)
            [ -z "$SIGNAL" ] && SIGNAL=0
            if [ "$SIGNAL" -ge 75 ]; then
                COLOR="#a3a47e"
            elif [ "$SIGNAL" -ge 50 ]; then
                COLOR="#d8b84c"
            elif [ "$SIGNAL" -ge 25 ]; then
                COLOR="#d87c4c"
            else
                COLOR="#c04c4c"
            fi
            ICON="%{F${COLOR}}%{F-}"
            OUTPUT="$ICON"
        fi
        if [ -z "$OUTPUT" ]; then
            echo "󰈬 disconnected"
        else
            echo "$OUTPUT"
        fi
        ;;
    menu)
        exec ~/.config/rofi/scripts/rofi-wifi
        ;;
esac
