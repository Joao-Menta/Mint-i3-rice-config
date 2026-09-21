# Media Widget — panel de audio estilo doty (volume_popup)

Widget GTK3 que se abre desde el icono de volumen de polybar (`click-left =
~/.config/media-widget/toggle.sh`) en i3. Es una réplica del *volume_popup*
de doty (parazeeknova/doty) en Python:

- **Media**: lo que suena ahora mismo (Spotify, Brave/YouTube, cualquier
  reproductor MPRIS) — portada, título, artista • reproductor, cubos-ficha
  por fuente, prev / play-pause / next / cambiar fuente (󰑖), y la duración
  con barra clicable.
- **Output** / **Input**: barras de **bloques** (15 rectángulos que se
  llenan según el volumen; clic, arrastre y rueda) + Mute/Unmute.
- **App Volumes**: una barra igual por cada aplicación con audio
  (sink-inputs de PulseAudio/PipeWire).
- **Devices**: lista de sinks y sources desplegable/plegable (flecha ▾/▸);
  clic cambia el dispositivo por defecto.
- **Bluetooth**: controles prev/play/next del reproductor cuando el sink
  predeterminado es bluetooth.
- Navegación por teclado como en doty: `Tab` cambia de sección, `↑/↓`
  elige elemento, `←/→` ajusta barras (±5), `Enter/Esc` activa/cierra.
  Clic fuera de la ventana la cierra (comportamiento Hyprland de doty).

Colores (paleta wabi de doty) y opciones en `theme.json` y `settings.json`
(ancho, posición top-right/top-left/top-center, márgenes).

## Requisitos
- `python3` + `python3-gi` (Gtk3)
- `pactl` (PulseAudio o PipeWire con compatibilidad `pulse`)
- Fuente `FiraCode Nerd Font`
- (`playerctl` opcional para los controles BT)

## Archivos
- `main.py` — ventana, secciones, temporizadores, teclado, animaciones.
- `pulse.py` — estado y acciones de audio vía `pactl` (JSON).
- `mpris.py` — reproductores MPRIS vía GDBus + persistencia de fuente.
- `segbar.py` — slider de bloques (y barra continua para la duración).
- `theme.py` / `theme.json` — paleta wabi + CSS de GTK3.
- `settings.json` — dimensiones y posición del panel.
- `toggle.sh` — abre/cierra (polybar `click-left`).

La fuente de reproductor seleccionada se guarda en
`~/.cache/media-widget/current_media_player` y las portadas se cachean en
`~/.cache/media-widget/covers/`.

## Notas de implementación

- **Tema**: paleta Nord del sistema (polybar/i3) en `theme.json`; fallback en
  `theme.py`. Fondo translúcido `rgba(bg, 0.5)` (`glass=true` +
  `glass_alpha=0.5`, mismo valor que el `volume_popup` original de doty);
  requiere compositor (picom). Borde, textos y barrita de bloques en acento
  `#88c0d0`; se cambia sin tocar código, solo `theme.json`.
- **Cambio de dispositivo por defecto (Devices)**: se intenta primero
  `pactl set-default-sink/source` y se verifica el resultado. En sistemas
  PipeWire/WirePlumber (p. ej. tarjetas *mono* tipo `sof-essx8336` con nodos
  alternativos `_5__sink`/`_6__sink`/`_7__sink` suspendidos), pactl lo aplica
  pero no lo refleja `get-default-sink`; en ese caso se cae a
  `pw-metadata -n default 0 default.audio.sink '{"name": ...}'`, que sí
  actualiza la metadata que los clientes leen.
- **Volumen con teclado/rueda**: los cambios se acumulan en `pending` y se
  envían a `pactl` solo cuando cambian (sin repetirse); el valor pendiente
  se muestra en la barra/título hasta que un refresco confirma que el
  servidor lo aplicó (tolerancia ±2 %), y se descarta tras ~3 s si nunca se
  confirma. Así, `←/→` seguidos avanzan de +5 en +5 sin perder pasos contra
  un snapshot obsoleto.
- **Robustez**: los eventos de PipeWire (~146/s) se refrescan como mucho
  1 vez/1.5 s; el foco se reclama al abrir (`present()` + reintento a 80 ms);
  `focus-out` los primeros 600 ms tras abrir se ignora (gracia de apertura
  para que i3 entregue el foco); `SIGTERM/SIGINT` cierran de inmediato para
  que `toggle.sh` (que mata con `kill`) sea fiable.
- **Depuración**: `MEDIA_WIDGET_DEBUG=1` vuelca `dlog()` a stderr
  (`/tmp/media-widget.log` con `toggle.sh`).