#!/usr/bin/env bash

WALLPAPER_NAME="$1"
THEME_DIR="${HOME}/.config/wallpaper-themes"

BASE="${WALLPAPER_NAME%.*}"

case "$BASE" in
    40|50|60|70)
        source "$THEME_DIR/colors-$BASE.sh"
        ;;
    *)
        source "$THEME_DIR/colors-nord.sh"
        ;;
esac

# ---- POLYBAR ----
POLYBAR_CFG="${HOME}/.config/polybar/config.ini"
BAR_BG="#99${background#\#}"
sed -i \
    -e "s|^background = #[0-9a-fA-F]*|background = $background|" \
    -e "s|^background-alt = .*|background-alt = $color6|" \
    -e "s|^foreground = #[0-9a-fA-F]*|foreground = $foreground|" \
    -e "s|^primary = .*|primary = $color6|" \
    -e "s|^bar-bg = .*|bar-bg = $BAR_BG|" \
    -e "s|^alert = .*|alert = $color1|" \
    -e "s|^disabled = .*|disabled = $color8|" \
    -e "s|label-warn-foreground = .*|label-warn-foreground = $color1|" \
    -e "s|label = %{F#[0-9a-fA-F]*}|label = %{F${color6}}|" \
    "$POLYBAR_CFG"

# ---- GHOSTTY ----
GHOSTTY_CFG="${HOME}/.config/ghostty/config"
GHOSTTY_BASE=$(grep -v "^# pywal" "$GHOSTTY_CFG" | \
               grep -v "^palette = " | \
               grep -v "^background = " | \
               grep -v "^foreground = " | \
               grep -v "^cursor-color = ")

echo "$GHOSTTY_BASE" > "$GHOSTTY_CFG"
cat >> "$GHOSTTY_CFG" << EOF

# pywal
background = ${background#\#}
foreground = ${foreground#\#}
cursor-color = ${cursor#\#}
palette = 0=$background
palette = 1=$color1
palette = 2=$color2
palette = 3=$color3
palette = 4=$color4
palette = 5=$color5
palette = 6=$color6
palette = 7=$color7
palette = 8=$color8
palette = 9=$color9
palette = 10=$color10
palette = 11=$color11
palette = 12=$color12
palette = 13=$color13
palette = 14=$color14
palette = 15=$color15
EOF

# ---- DUNST ----
DUNST_CFG="${HOME}/.config/dunst/dunstrc"
sed -i \
    -e "/^\[global\]/,/^\[/ s|frame_color = \".*\"|frame_color = \"$color6\"|" \
    -e "/^\[global\]/,/^\[/ s|background = \".*\"|background = \"$color0\"|" \
    -e "/^\[global\]/,/^\[/ s|foreground = \".*\"|foreground = \"$foreground\"|" \
    -e "/^\[urgency_low\]/,/^\[/ s|background = \".*\"|background = \"$color8\"|" \
    -e "/^\[urgency_low\]/,/^\[/ s|foreground = \".*\"|foreground = \"$foreground\"|" \
    -e "/^\[urgency_low\]/,/^\[/ s|frame_color = \".*\"|frame_color = \"$color6\"|" \
    -e "/^\[urgency_normal\]/,/^\[/ s|background = \".*\"|background = \"$color8\"|" \
    -e "/^\[urgency_normal\]/,/^\[/ s|foreground = \".*\"|foreground = \"$foreground\"|" \
    -e "/^\[urgency_normal\]/,/^\[/ s|frame_color = \".*\"|frame_color = \"$color6\"|" \
    -e "/^\[urgency_critical\]/,/^\[/ s|background = \".*\"|background = \"$color0\"|" \
    -e "/^\[urgency_critical\]/,/^\[/ s|foreground = \".*\"|foreground = \"$foreground\"|" \
    -e "/^\[urgency_critical\]/,/^\[/ s|frame_color = \".*\"|frame_color = \"$color1\"|" \
    "$DUNST_CFG"

# ---- BTOP ----
BTOP_DIR="${HOME}/.config/btop"
BTOP_THEMES="${BTOP_DIR}/themes"
mkdir -p "$BTOP_THEMES"
BTOP_THEME="${BTOP_THEMES}/pywal.theme"
cat > "$BTOP_THEME" << EOF
theme[main_bg] = $background
theme[main_fg] = $foreground
theme[title] = $color6
theme[hi_fg] = $color4
theme[selected_bg] = $color8
theme[selected_fg] = $foreground
theme[inactive_fg] = $color8
theme[proc_misc] = $color4
theme[cpu_box] = $color8
theme[mem_box] = $color8
theme[net_box] = $color8
theme[proc_box] = $color8
theme[div_line] = $color8
theme[temp_start] = $color4
theme[temp_mid] = $color6
theme[temp_end] = $foreground
theme[cpu_start] = $color4
theme[cpu_mid] = $color6
theme[cpu_end] = $foreground
theme[free_start] = $color4
theme[free_mid] = $color6
theme[free_end] = $foreground
theme[cached_start] = $color4
theme[cached_mid] = $color6
theme[cached_end] = $foreground
theme[available_start] = $color4
theme[available_mid] = $color6
theme[available_end] = $foreground
theme[used_start] = $color4
theme[used_mid] = $color6
theme[used_end] = $foreground
theme[download_start] = $color4
theme[download_mid] = $color6
theme[download_end] = $foreground
theme[upload_start] = $color4
theme[upload_mid] = $color6
theme[upload_end] = $foreground
EOF
sed -i "s|^color_theme = .*|color_theme = \"$BTOP_THEME\"|" "${BTOP_DIR}/btop.conf"

# ---- ROFI ----
ROFI_COLORS="${HOME}/.config/rofi/shared/colors.rasi"
sed -i \
    -e "s|background:[[:space:]]*#[0-9a-fA-F]*;|background:     $background;|" \
    -e "s|background-alt:[[:space:]]*#[0-9a-fA-F]*;|background-alt: $color8;|" \
    -e "s|foreground:[[:space:]]*#[0-9a-fA-F]*;|foreground:     $foreground;|" \
    -e "s|selected:[[:space:]]*#[0-9a-fA-F]*;|selected:       $color6;|" \
    -e "s|active:[[:space:]]*#[0-9a-fA-F]*;|active:         $color2;|" \
    -e "s|urgent:[[:space:]]*#[0-9a-fA-F]*;|urgent:         $color1;|" \
    "$ROFI_COLORS"

# ---- I3 ----
I3_CFG="${HOME}/.config/i3/config"
sed -i \
    -e "s|^client.focused[[:space:]]*#.*|client.focused          $color6 $color6 $background $color6 $color6|" \
    -e "s|^client.focused_inactive[[:space:]]*#.*|client.focused_inactive $color8 $color0 $foreground $color0 $color0|" \
    -e "s|^client.unfocused[[:space:]]*#.*|client.unfocused        $color8 $color0 $foreground $color0 $color0|" \
    -e "s|^client.urgent[[:space:]]*#.*|client.urgent           $color1 $color1 $background $color1 $color1|" \
    -e "s|^client.background[[:space:]]*#.*|client.background       $background|" \
    "$I3_CFG"

# ---- I3 colors en runtime (cambio instantáneo) ----
i3-msg "client.focused $color6 $color6 $background $color6 $color6" >/dev/null 2>&1 || true
i3-msg "client.focused_inactive $color8 $color0 $foreground $color0 $color0" >/dev/null 2>&1 || true
i3-msg "client.unfocused $color8 $color0 $foreground $color0 $color0" >/dev/null 2>&1 || true
i3-msg "client.urgent $color1 $color1 $background $color1 $color1" >/dev/null 2>&1 || true
i3-msg "client.background $background" >/dev/null 2>&1 || true

# ---- SHELL PALETTE ----
mkdir -p "${HOME}/.config/shell"
cat > "${HOME}/.config/shell/palette.sh" << EOF
printf '\033]10;%s\033\\\\' "$foreground"
printf '\033]11;%s\033\\\\' "$background"
printf '\033]12;%s\033\\\\' "$cursor"
printf '\033]4;0;%s\033\\\\' "$color0"
printf '\033]4;1;%s\033\\\\' "$color1"
printf '\033]4;2;%s\033\\\\' "$color2"
printf '\033]4;3;%s\033\\\\' "$color3"
printf '\033]4;4;%s\033\\\\' "$color4"
printf '\033]4;5;%s\033\\\\' "$color5"
printf '\033]4;6;%s\033\\\\' "$color6"
printf '\033]4;7;%s\033\\\\' "$color7"
printf '\033]4;8;%s\033\\\\' "$color8"
printf '\033]4;9;%s\033\\\\' "$color9"
printf '\033]4;10;%s\033\\\\' "$color10"
printf '\033]4;11;%s\033\\\\' "$color11"
printf '\033]4;12;%s\033\\\\' "$color12"
printf '\033]4;13;%s\033\\\\' "$color13"
printf '\033]4;14;%s\033\\\\' "$color14"
printf '\033]4;15;%s\033\\\\' "$color15"
EOF

# ---- RELOAD ----
dunstctl reload 2>/dev/null || killall -SIGUSR1 dunst 2>/dev/null || { killall dunst 2>/dev/null; dunst & }

timeout 2 polybar-msg cmd restart 2>/dev/null || { killall -q polybar; while pgrep -x polybar >/dev/null; do sleep 0.2; done; polybar -c "$POLYBAR_CFG" >/dev/null 2>&1 & }

i3-msg reload
