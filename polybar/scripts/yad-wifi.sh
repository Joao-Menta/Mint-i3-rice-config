#!/usr/bin/env bash

read -r -d '' CSS << 'EOF'
window {
    background-color: #131008;
    border: 2px solid #a3a47e;
    border-radius: 8px;
}
* {
    font-family: "Inconsolata Nerd Font Mono";
    font-size: 10pt;
    color: #c4c3c1;
}
button {
    background-image: none;
    background-color: #2a2820;
    color: #c4c3c1;
    border: 1px solid #63593a;
    border-radius: 4px;
    padding: 8px 14px;
    font-size: 16pt;
}
button:hover {
    background-color: #a3a47e;
    color: #131008;
    border-color: #a3a47e;
}
button:active {
    background-color: #8c8d6a;
}
list {
    background-color: #1a1810;
    border-radius: 4px;
}
list row {
    padding: 6px 8px;
}
list row:hover {
    background-color: rgba(163, 164, 126, 0.12);
}
list row:selected {
    background-color: #a3a47e;
    color: #131008;
}
EOF

signal_stairs() {
    local s=$1
    if   [ "$s" -ge 80 ]; then echo "▄▅▆▇█"
    elif [ "$s" -ge 60 ]; then echo "▄▅▆▇░"
    elif [ "$s" -ge 40 ]; then echo "▄▅▆░░"
    elif [ "$s" -ge 20 ]; then echo "▄▅░░░"
    else                      echo "▄░░░░"
    fi
}

cleanup() {
    rm -f /tmp/yad-wifi-*
    exit 0
}
trap cleanup EXIT INT TERM

while true; do
    wifi_enabled=$(nmcli radio wifi | grep -qi enabled && echo true || echo false)
    wwan_enabled=$(nmcli radio wwan | grep -qi enabled && echo true || echo false)

    if ! $wifi_enabled && ! $wwan_enabled; then
        airplane_state="ON"
        wifi_display="OFF"
    elif ! $wifi_enabled; then
        airplane_state="OFF"
        wifi_display="OFF"
    else
        airplane_state="OFF"
        wifi_display="ON"
    fi

    wifi_color="#a3a47e"  # accent
    airplane_color="#63593a"  # disabled
    [ "$wifi_display" = "ON" ] && wifi_color="#a3a47e" || wifi_color="#63593a"
    [ "$airplane_state" = "ON" ] && airplane_color="#a3a47e" || airplane_color="#63593a"

    current_ssid=$(nmcli -t -f NAME connection show --active 2>/dev/null | grep -v "^lo:" | head -1)
    current_signal=$(nmcli -t -f ACTIVE,SIGNAL dev wifi list 2>/dev/null | grep "^yes" | cut -d: -f2)
    [ -z "$current_signal" ] && current_signal=0
    current_bars=$(signal_stairs "$current_signal")

    networks=$(nmcli -t -f SSID,SIGNAL,SECURITY dev wifi list 2>/dev/null | \
        awk -F: '{
            ssid=$1; signal=$2; sec=$3
            if (ssid == "" || ssid == "--") next
            if (signal+0 > max[ssid]+0 || max[ssid] == "") {
                max[ssid] = signal
                sec[ssid] = sec
            }
        }
        END {
            for (s in max) printf "%s|%s|%s\n", s, max[s], sec[s] ? sec[s] : "Open"
        }' | sort -t'|' -k2,2rn)

    list_data=()
    current_in_list=""

    if [ -n "$current_ssid" ]; then
        cur_sec=$(nmcli -t -f SSID,SECURITY dev wifi list 2>/dev/null | \
            grep -F "$current_ssid" | head -1 | cut -d: -f2)
        [ -z "$cur_sec" ] && cur_sec="WPA2"
        [ "$cur_sec" = "" ] && cur_sec="Open"

        list_data+=("TRUE" "$current_ssid" "$current_bars  $current_signal%" "$cur_sec")
        current_in_list="$current_ssid"
    fi

    while IFS='|' read -r ssid signal sec; do
        [ "$ssid" = "$current_in_list" ] && continue
        bars=$(signal_stairs "$signal")
        list_data+=("FALSE" "$ssid" "$bars  $signal%" "$sec")
    done <<< "$networks"

    if [ ${#list_data[@]} -eq 0 ]; then
        if ! $wifi_enabled; then
            msg="Wi-Fi is off"
        else
            msg="No networks found"
        fi
        list_data=("FALSE" "$msg" "" "")
    fi

    header_text=$(printf '<span foreground="#c4c3c1">Wi-Fi  <span foreground="%s">%s</span>    Airplane  <span foreground="%s">%s</span></span>\n<span foreground="#63593a">━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</span>' \
        "$wifi_color" "$wifi_display" "$airplane_color" "$airplane_state")

    result=$(yad --list \
        --radiolist \
        --undecorated \
        --fixed \
        --on-top \
        --mouse \
        --title="" \
        --text="$header_text" \
        --justify=center \
        --column=" " \
        --column="Network:C" \
        --column="Signal:C" \
        --column="Security:C" \
        --button=":30" \
        --button="✈:31" \
        --button=":32" \
        --button=":33" \
        --button=":34" \
        --button=":35" \
        --css="$CSS" \
        --width=460 \
        --height=400 \
        "${list_data[@]}" \
        2>/dev/null)

    exit_code=$?
    [ $exit_code -eq 252 ] && exit 0

    IFS='|' read -r _ selected_ssid _ _ <<< "$result"

    case $exit_code in
        30) # Toggle Wi-Fi
            $wifi_enabled && nmcli radio wifi off || nmcli radio wifi on
            sleep 0.5
            ;;
        31) # Toggle Airplane
            if [ "$airplane_state" = "ON" ]; then
                nmcli radio wifi on
            else
                nmcli radio wifi off 2>/dev/null
                nmcli radio wwan off 2>/dev/null
            fi
            sleep 0.5
            ;;
        32) # Connect
            if [ -n "$selected_ssid" ] && ! echo "$selected_ssid" | grep -qE "^(Wi-Fi is off|No networks found)$"; then
                sec=$(nmcli -t -f SSID,SECURITY dev wifi list 2>/dev/null | \
                    grep -F "$selected_ssid" | head -1 | cut -d: -f2)
                if [ -n "$sec" ] && [ "$sec" != "" ] && [ "$sec" != "Open" ]; then
                    pw=$(yad --entry \
                        --title="Password Required" \
                        --text="Enter password for <b>$selected_ssid</b>:" \
                        --hide-text \
                        --button="Connect:0" \
                        --button="Cancel:1" \
                        --css="$CSS" \
                        --mouse \
                        --undecorated \
                        --on-top \
                        2>/dev/null)
                    [ $? -eq 0 ] && [ -n "$pw" ] && \
                        nmcli dev wifi connect "$selected_ssid" password "$pw" 2>/dev/null
                else
                    nmcli dev wifi connect "$selected_ssid" 2>/dev/null
                fi
            fi
            ;;
        33) # Disconnect
            if [ -n "$current_ssid" ]; then
                nmcli connection down "$current_ssid" 2>/dev/null
            fi
            ;;
        34) # Restart
            nmcli radio wifi off 2>/dev/null
            sleep 2
            nmcli radio wifi on 2>/dev/null
            sleep 2
            ;;
        35) # Refresh
            ;;
    esac

    sleep 0.3
done
