#!/usr/bin/env bash
DIR="${HOME}/media/pictures/wallpapers/nord"

if [[ ! -d "$DIR" ]]; then
    exit 1
fi
CACHE="${HOME}/.cache/wallpaper-index"

mapfile -t files < <(find "$DIR" -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' \) | sort)
total=${#files[@]}

if [[ $total -eq 0 ]]; then
    exit 1
fi

if [[ ! -f $CACHE ]]; then
    idx=0
else
    idx=$(cat "$CACHE")
    idx=$(( (idx + 1) % total ))
fi

feh --bg-fill "${files[$idx]}"
echo "$idx" > "$CACHE"

BASENAME=$(basename "${files[$idx]}")
"${HOME}/.config/i3/apply-theme.sh" "$BASENAME"
