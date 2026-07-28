# razer_rgb

App PyQt6 para controlar el RGB de dispositivos Razer en Linux vía [OpenRazer](https://openrazer.github.io/),
con indicador de Caps Lock integrado en la propia animación del teclado.

## Hecho para hardware concreto — ¿funciona con otros dispositivos Razer?

Este proyecto se desarrolló y se probó **solo** con:

- Teclado Razer Ornata V2
- Teclado Razer Huntsman Mini
- Ratón Razer Viper Mini

**No se sabe con certeza si funciona igual en otro hardware Razer**, pero por cómo está
construido, la respuesta previsible es "a medias":

- **Detección de dispositivos, brillo, y los efectos que van directos al firmware**
  (`wave`, `reactive`, `ripple`, `ripple_random`, `starlight_*`, `breath_dual`,
  `breath_random`, `none`, y los efectos de logo del ratón) usan la API genérica de
  OpenRazer (`fx.*` / `fx.misc.logo.*`). OpenRazer abstrae el protocolo USB por
  dispositivo internamente, así que estos **deberían funcionar en cualquier teclado o
  ratón Razer soportado por OpenRazer**, no solo en los dos de arriba.
- **`Spectrum`, `Static` y `Breathing — uno`** son distintos: no llaman al hardware
  directamente, escriben su estado en `~/.config/razer-rgb-state.json`, que lee el
  servicio `razer-capslock-led.py` (ver más abajo). Ese servicio tiene hardcodeada
  la posición (fila, columna) de la tecla Caps Lock **solo** para Ornata V2 y
  Huntsman Mini (`CAPSLOCK_POS` en `razer-capslock-led.py`). En un teclado que no
  esté en ese diccionario, el servicio **ignora silenciosamente** ese teclado —
  estos tres efectos no harían nada visible hasta añadir la posición de su Caps
  Lock a `CAPSLOCK_POS`.
- El código que separa teclado de ratón (`"keyboard" in dev.type`) y asume que
  cualquier no-teclado tiene zona de logo (`fx.misc.logo`) es razonablemente
  genérico, pero no está probado con ratones sin esa zona, ni con otros tipos de
  periférico (mousepad, auriculares, etc.).

En resumen: si tienes otro teclado/ratón Razer soportado por OpenRazer, la app lo
detectará y la mayoría de efectos deberían funcionar; lo único garantizado que no
funciona sin tocar código es el indicador de Caps Lock (y por tanto los tres efectos
que dependen del servicio) en un teclado distinto a los dos de arriba.

## Arquitectura

Dos procesos independientes coordinados por un archivo de estado JSON:

```
razer-capslock-led.py  (servicio systemd, siempre activo)
      ↕  lee ~/.config/razer-rgb-state.json cada frame
razer_rgb.py            (app PyQt6, se abre a demanda)
      ↕  escribe ~/.config/razer-rgb-state.json al aplicar
```

El servicio pinta la matriz de LEDs a 20 FPS vía `fx.advanced.draw()` y pone en blanco
la tecla Caps Lock cuando la capa de `keyd` está activa. Sin esta coordinación por
archivo de estado, el servicio sobreescribiría cualquier efecto que la app aplicase.

Modos del archivo de estado:
```
{"mode": "spectrum"}                    — arcoíris animado (por defecto)
{"mode": "static",  "color": [r,g,b]}   — color sólido
{"mode": "breath",  "color": [r,g,b]}   — respiración
{"mode": "hardware"}                    — el servicio pausa esa tecla/teclado
```

Los efectos "hardware" (`wave`, `reactive`, `ripple`...) ponen `{"mode": "hardware"}`
para que el servicio no pinte encima, y llaman directamente a `fx.*` de OpenRazer.
Mientras un efecto hardware está activo, el indicador de Caps Lock no funciona —
para recuperarlo hay que volver a `Spectrum` o `Static`.

## Instalación

1. `openrazer-daemon` corriendo, usuario en el grupo `plugdev`.
2. Instala el servicio de animación:
   ```bash
   sudo cp razer-capslock-led.py /usr/local/lib/razer-capslock-led.py
   sudo cp razer-capslock-led.service /etc/systemd/system/
   sudo systemctl enable --now razer-capslock-led
   ```
3. Lanza la app: `python3 razer_rgb.py`, o instala `razer-rgb.desktop` en
   `~/.local/share/applications/` para tenerla en el lanzador de KDE.

## Uso

Una pestaña por dispositivo detectado. Por pestaña: deslizador de brillo, desplegable
de efecto (las opciones relevantes — colores, dirección, velocidad — aparecen y
desaparecen según el efecto elegido), y botón Aplicar. Al cerrar la app, el servicio
retoma la animación spectrum arcoíris automáticamente.

## Solución de problemas

- **Los colores no cambian al pulsar Aplicar** → el servicio no está actualizado o no
  está corriendo: `systemctl status razer-capslock-led`.
- **"No se encontraron dispositivos Razer"** → `systemctl status openrazer-daemon`,
  y confirma que tu usuario está en el grupo `plugdev` (`sudo gpasswd -a $USER plugdev`,
  luego reinicia sesión).
- **El servicio falla al reiniciar** → `journalctl -u razer-capslock-led -n 30`.

## Requisitos

`python-pyqt6`, `python3-openrazer`, `openrazer-daemon`, usuario en el grupo `plugdev`.

## Actualizaciones

- Icono nuevo (keycap con luz RGB), y la app ahora fija su propio icono de ventana y
  `desktopFileName` — en Wayland, sin esto KDE no asocia la ventana con el icono del
  `.desktop` y cae a uno genérico.
- Documentado explícitamente el alcance real del hardware soportado (ver el apartado
  de arriba) — antes solo estaba implícito en el código (`CAPSLOCK_POS`).

---

Hecho con ayuda de IA (Claude Code). Si lo pruebas en otro teclado/ratón Razer y
`CAPSLOCK_POS` no lo cubre, añadir su posición de Caps Lock en
`razer-capslock-led.py` debería bastar para que el indicador funcione también ahí.
