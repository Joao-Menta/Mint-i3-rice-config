# Mint i3 Rice Config

Personal dotfiles for **Linux Mint** with **i3** window manager, themed with a custom **Nord** palette that auto-adapts to the wallpaper.

## Features

- **Auto-themed**: Change wallpaper, and everything follows — polybar, dunst, ghostty, btop, rofi, i3 colors, and terminal palette
- **Nord-inspired**: Clean, blue-ish dark theme as the base
- **i3-master-stack**: Master-stack layout for automatic window management
- **Polybar**: Full-featured bar with workspace, audio, network, battery, CPU, memory, temperature, pomodoro, date/weather, and power menu
- **Rofi**: Custom launcher, power menu, clipboard manager, emoji picker, WiFi manager, Bluetooth manager, and more
- **Dunst**: Minimal notification daemon with theme-aware colors
- **Ghostty**: GPU-accelerated terminal with dynamic color palette
- **Fastfetch**: Beautiful system info with custom ASCII logo

## Screenshots

> Add screenshots to the `screenshots/` directory.

## Dependencies

### Required
```bash
# Window manager & compositor
sudo apt install i3 picom

# Bar
sudo apt install polybar

# Launcher & menus
sudo apt install rofi

# Notifications
sudo apt install dunst

# Terminal
# Download from: https://ghostty.org/download

# Wallpaper
sudo apt install feh

# System monitor
sudo apt install btop

# System info
sudo apt install fastfetch

# Network
sudo apt install network-manager nmcli

# Audio
sudo apt install pulseaudio pavucontrol

# Clipboard
sudo apt install xclip

# Bluetooth
sudo apt install bluez bluez-tools

# Fonts
sudo apt install fonts-font-awesome
# Download Inconsolata Nerd Font from: https://www.nerdfonts.com/

# Screenshot
sudo apt install flameshot

# Backlight (if Intel)
sudo apt install xbacklight
```

### Optional
```bash
# Pomodoro timer (polybar module)
sudo apt install python3

# YAD WiFi manager
sudo apt install yad

# Media control
sudo apt install playerctl

# Weather
sudo apt install curl

# Image viewer (for rofi wallpaper picker)
sudo apt install feh
```

### Python packages (for pywal)
```bash
pip install pywal
```

## Installation

```bash
# Clone the repo
git clone git@github.com:Joao-Mint/Mint-i3-rice-config.git ~/dotfiles

# Create symlinks
ln -sf ~/dotfiles/i3/config ~/.config/i3/config
ln -sf ~/dotfiles/i3/wallpaper-cycle.sh ~/.config/i3/wallpaper-cycle.sh
ln -sf ~/dotfiles/i3/apply-theme.sh ~/.config/i3/apply-theme.sh
ln -sf ~/dotfiles/polybar/config.ini ~/.config/polybar/config.ini
ln -sf ~/dotfiles/polybar/launch.sh ~/.config/polybar/launch.sh
# ... (repeat for each config, or use a symlink script)

# Restart i3
i3-msg restart
```

> **Note**: The `i3-master-stack` directory is from [windwp/i3-master-stack](https://github.com/windwp/i3-master-stack).

## Keybindings

| Key | Action |
|-----|--------|
| `$mod+Return` | Open Ghostty |
| `$mod+d` | Rofi app launcher |
| `$mod+Escape` | Rofi power menu |
| `$mod+n` | Cycle wallpaper |
| `$mod+b` / `Ctrl+Shift+Escape` | Open btop |
| `$mod+e` | Open Thunar file manager |
| `$mod+q` | Kill focused window |
| `$mod+h/j/k/l` | Focus left/down/up/right |
| `$mod+Shift+h/j/k/l` | Move window left/down/up/right |
| `$mod+f` | Toggle fullscreen |
| `$mod+r` | Resize mode |
| `$mod+m` | Go to master (i3-master-stack) |
| `$mod+Shift+m` | Swap master (i3-master-stack) |
| `$mod+Alt+m` | Toggle master layout |
| `$mod+1-0` | Switch workspace |
| `$mod+Shift+1-0` | Move window to workspace |
| `Print` | Flameshot screenshot |
| `XF86AudioRaiseVolume` | Volume up |
| `XF86AudioLowerVolume` | Volume down |
| `XF86AudioMute` | Mute |

## Theme System

Wallpapers in `~/media/pictures/wallpapers/nord/` are named with a number prefix (e.g., `40.jpg`, `50.jpg`, `60.png`, `70.png`). When the wallpaper cycles:

1. `wallpaper-cycle.sh` sets the wallpaper via `feh` and calls `apply-theme.sh`
2. `apply-theme.sh` reads the corresponding `<number>` and sources the matching theme file from `wallpaper-themes/`
3. All application configs are updated in-place with the new colors
4. Services are reloaded (dunst, polybar, i3)

Files without a matching theme fall back to the default Nord palette (`wallpaper-themes/colors-nord.sh`).

### Adding a new wallpaper
```bash
# Generate a theme from your new wallpaper
wal -i ~/media/pictures/wallpapers/nord/my-wallpaper.jpg

# Save the colors to a theme file
cat ~/.cache/wal/colors.sh > ~/dotfiles/wallpaper-themes/colors-my-wallpaper.sh

# Add the number/case to apply-theme.sh
```

## Directory Structure

```
dotfiles/
├── README.md
├── i3/
│   ├── config                    # i3 window manager config
│   ├── wallpaper-cycle.sh        # Wallpaper cycling script
│   ├── apply-theme.sh            # Theme application engine
│   ├── i3_master.ini             # i3-master-stack config
│   └── i3-master-stack/          # i3-master-stack layout
├── polybar/
│   ├── config.ini                # Bar config
│   ├── launch.sh                 # Bar launcher
│   ├── modules/                  # Bar modules
│   └── scripts/                  # Helper scripts
├── rofi/
│   ├── config.rasi               # Main rofi config
│   ├── launcher.rasi             # App launcher theme
│   ├── shared/                   # Shared colors, fonts
│   ├── scripts/                  # Rofi scripts
│   └── colors/                   # Color themes
├── dunst/
│   └── dunstrc                   # Notification config
├── ghostty/
│   └── config                    # Terminal config
├── btop/
│   └── btop.conf                 # System monitor config
├── fastfetch/
│   ├── config.jsonc              # System info config
│   └── logos/                    # ASCII logos
├── wallpaper-themes/             # Pywal color schemes
│   ├── colors-40.sh
│   ├── colors-50.sh
│   ├── colors-60.sh
│   ├── colors-70.sh
│   └── colors-nord.sh            # Default fallback
└── shell/
    └── palette.sh                # Terminal color sequences
```

## Credits

- **i3-master-stack**: [windwp/i3-master-stack](https://github.com/windwp/i3-master-stack)
- **Nord theme**: [nordtheme.com](https://www.nordtheme.com/)
- **Pywal**: [dylanaraps/pywal](https://github.com/dylanaraps/pywal)

## License

MIT
