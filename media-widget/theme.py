"""Theme loader: lee theme.json y genera el CSS de GTK3 (estilo volume_popup
de doty: panel glass, borde 1px acento, texto en acento, esquinas rectas)."""

import json
import os

DIR = os.path.dirname(os.path.abspath(__file__))

DEFAULT_COLORS = {
    "bg": "#2e3440",
    "bg_dark": "#1d2330",
    "bg_light": "#4c566a",
    "fg": "#eceff4",
    "fg_light": "#aeb7c6",
    "accent": "#88c0d0",
    "secondary": "#81a1c1",
    "tertiary": "#81a1c1",
    "error": "#bf616a",
}


def hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def rgba(hex_color, alpha):
    r, g, b = hex_to_rgb(hex_color)
    return "rgba(%d, %d, %d, %.2f)" % (r, g, b, alpha)


def load_theme(path=None):
    path = path or os.path.join(DIR, "theme.json")
    with open(path) as f:
        data = json.load(f)
    colors = dict(DEFAULT_COLORS)
    palette = data.get("colors", {})
    for k, v in palette.items():
        if k in DEFAULT_COLORS and isinstance(v, str):
            colors[k] = v
    glass = bool(palette.get("glass", True))
    alpha = float(palette.get("glass_alpha", 0.5))
    font = data.get("font", "FiraCode Nerd Font")
    return {"colors": colors, "font": font, "glass": glass,
            "glass_alpha": alpha}


def build_css(theme, use_alpha=True):
    c = theme["colors"]
    font = theme["font"]
    glass = theme.get("glass", True) and use_alpha
    alpha = theme.get("glass_alpha", 0.5) if glass else 1.0

    acc = c["accent"]
    a60 = rgba(acc, 0.6)
    a50 = rgba(acc, 0.5)
    a70 = rgba(acc, 0.7)
    a35 = rgba(acc, 0.35)
    focus = rgba(acc, 0.19)      # mismo color que el highlight de doty (#30d5c4a1)

    return f"""@define-color bg {c['bg']};
@define-color bg_dark {c['bg_dark']};
@define-color bg_light {c['bg_light']};
@define-color fg {c['fg']};
@define-color fg_light {c['fg_light']};
@define-color accent {acc};
@define-color secondary {c['secondary']};
@define-color tertiary {c['tertiary']};
@define-color error {c['error']};

* {{
  font-family: "{font}", "FiraCode Nerd Font Mono", monospace;
  outline: none;
  border-radius: 0px;
}}

.panel {{
  background-color: {rgba(c['bg'], alpha)};
  border: 1px solid {acc};
}}

/* texto: todo en acento, con opacidades */
.t-accent {{ color: {acc}; }}
.fg100 {{ color: {acc}; }}
.fg70  {{ color: {a70}; }}
.fg60  {{ color: {a60}; }}
.fg50  {{ color: {a50}; }}
.fg35  {{ color: {a35}; }}

.s7  {{ font-size: 7px; }}
.s8  {{ font-size: 8px; }}
.s9  {{ font-size: 9px; }}
.s10 {{ font-size: 10px; }}
.s11 {{ font-size: 11px; }}
.s18 {{ font-size: 18px; }}
.bold {{ font-weight: bold; }}

/* portada */
.cover-frame {{
  background-color: @bg_light;
  border: 1px solid {acc};
}}

/* botones de texto (transparentes, acento) */
button.textbtn {{
  background-image: none;
  background-color: transparent;
  color: {acc};
  border: none;
  box-shadow: none;
  text-shadow: none;
  padding: 0;
  min-width: 0;
  min-height: 0;
}}
button.textbtn:hover {{ background-color: {focus}; }}
button.textbtn:hover:disabled {{ background-color: transparent; }}
button.textbtn:disabled {{ color: {a35}; }}

/* elemento enfocado por teclado (highlight estilo doty) */
.focused {{ background-color: {focus}; }}

/* cuadritos indicadores de fuente (pestañas) */
button.src-sq {{
  background-color: @bg_light;
  border: 1px solid {acc};
}}
button.src-sq.on {{ background-color: {acc}; }}
button.src-sq:hover {{ background-color: {a60}; }}

/* filas de dispositivos */
.dev-row {{ background-color: transparent; }}
.dev-row:hover {{ background-color: {focus}; }}

/* separadores */
.sep {{
  background-color: {rgba(acc, 0.25)};
}}
"""