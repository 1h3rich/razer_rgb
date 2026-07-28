#!/usr/bin/env python3
"""
Continuous spectrum animation on Razer keyboards.
Caps Lock key turns white when the keyd capslock_layer is active.
Reads ~/.config/razer-rgb-state.json to allow external color control.

State file modes:
  {"mode": "spectrum"}               — default rainbow animation
  {"mode": "static",  "color": [r,g,b]}  — solid color
  {"mode": "breath",  "color": [r,g,b]}  — breathing animation
  {"mode": "hardware"}               — pause matrix so hardware effects show
"""

import colorsys
import json
import math
import os
import pty
import subprocess
import threading
import time
from pathlib import Path

import openrazer.client

STATE_FILE = Path.home() / ".config" / "razer-rgb-state.json"

CAPSLOCK_POS = {
    'Ornata V2':     (3, 1),
    'Huntsman Mini': (2, 1),
}

WHITE = (255, 255, 255)
FPS   = 20
SPEED = 0.003


def read_state(device_key: str) -> dict:
    try:
        full = json.loads(STATE_FILE.read_text())
        return full.get(device_key, {"mode": "spectrum"})
    except Exception:
        return {"mode": "spectrum"}


def get_keyboards(dm):
    result = []
    for device in dm.devices:
        if device.type != 'keyboard':
            continue
        if not device.capabilities.get('lighting_led_matrix'):
            continue
        pos = next((v for k, v in CAPSLOCK_POS.items() if k in device.name), None)
        if pos is not None:
            result.append((device, pos))
    return result


def hue_to_rgb(h):
    r, g, b = colorsys.hsv_to_rgb(h % 1.0, 1.0, 1.0)
    return int(r * 255), int(g * 255), int(b * 255)


class SpectrumAnimation:
    def __init__(self, keyboards):
        self.keyboards       = keyboards
        self.capslock_active = False
        self._hue            = 0.0
        self._phase          = 0.0
        self._thread         = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def set_capslock(self, active):
        self.capslock_active = active

    def _run(self):
        interval  = 1.0 / FPS
        hues      = {}   # per-device hue for spectrum
        phases    = {}   # per-device phase for breath
        while True:
            for kb, (cap_row, cap_col) in self.keyboards:
                device_key = kb.name.replace("Razer ", "")
                state = read_state(device_key)
                mode  = state.get("mode", "spectrum")

                if mode == "hardware":
                    continue  # don't touch this keyboard's matrix

                if mode == "static":
                    c     = state.get("color", [255, 255, 255])
                    color = (int(c[0]), int(c[1]), int(c[2]))

                elif mode == "breath":
                    phases[device_key] = (phases.get(device_key, 0.0) + 0.05) % (2 * math.pi)
                    amp   = (math.sin(phases[device_key]) + 1) / 2
                    c     = state.get("color", [255, 0, 0])
                    color = (int(c[0] * amp), int(c[1] * amp), int(c[2] * amp))

                else:  # spectrum
                    hues[device_key] = (hues.get(device_key, 0.0) + SPEED) % 1.0
                    color = hue_to_rgb(hues[device_key])

                fx = kb.fx.advanced
                for row in range(fx.rows):
                    for col in range(fx.cols):
                        if self.capslock_active and row == cap_row and col == cap_col:
                            fx.matrix.set(row, col, WHITE)
                        else:
                            fx.matrix.set(row, col, color)
                fx.draw()

            time.sleep(interval)


def main():
    dm = openrazer.client.DeviceManager()
    dm.sync_effects = False

    keyboards = get_keyboards(dm)
    if not keyboards:
        print('No Razer keyboards found with LED matrix.', flush=True)
        return

    print(f'Tracking: {[kb.name for kb, _ in keyboards]}', flush=True)

    anim = SpectrumAnimation(keyboards)
    anim.start()

    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        ['keyd', 'listen'],
        stdout=slave_fd,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    os.close(slave_fd)

    buf = b''
    with os.fdopen(master_fd, 'rb', buffering=0) as tty:
        while True:
            try:
                chunk = tty.read(64)
            except OSError:
                break
            if not chunk:
                break
            buf += chunk
            while b'\n' in buf or b'\r' in buf:
                for sep in (b'\r\n', b'\n', b'\r'):
                    if sep in buf:
                        line, buf = buf.split(sep, 1)
                        break
                line = line.decode(errors='replace').strip()
                if not line:
                    continue
                if line == '+capslock_layer':
                    anim.set_capslock(True)
                elif line == '-capslock_layer':
                    anim.set_capslock(False)

    proc.wait()


if __name__ == '__main__':
    main()
