#!/usr/bin/env sh

while true; do
    current=$(xclip -o -selection clipboard 2>/dev/null)
    saved=$(tail -1 "${XDG_CACHE_HOME:-$HOME/.cache}/rofi-clipboard" 2>/dev/null)
    [ -n "$current" ] && [ "$current" != "$saved" ] && \
        ~/.config/rofi/scripts/rofi-clipboard save
    sleep 1
done
