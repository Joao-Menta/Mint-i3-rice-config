#!/usr/bin/env sh

case "$1" in
    menu)
        exec ~/.config/rofi/scripts/powermenu_t1
        ;;
    lock)
        dm-tool lock
        ;;
    suspend)
        systemctl suspend
        ;;
    reboot)
        systemctl reboot
        ;;
    poweroff)
        systemctl poweroff
        ;;
    logout)
        i3-msg exit
        ;;
esac
