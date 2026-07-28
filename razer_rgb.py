import json
import math
import sys
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QColor, QIcon, QPalette
from PyQt6.QtWidgets import (
    QApplication, QColorDialog, QComboBox, QGroupBox,
    QHBoxLayout, QLabel, QMainWindow, QPushButton,
    QSlider, QTabWidget, QVBoxLayout, QWidget,
)
from openrazer.client import DeviceManager

STATE_FILE = Path.home() / ".config" / "razer-rgb-state.json"
ICON_PATH  = Path(__file__).resolve().parent / "icon.png"

# Effects handled by the matrix animation service (no service conflict)
MATRIX_EFFECTS = {"spectrum", "static", "breath_single"}

EFFECTS_KEYBOARD = [
    ("Spectrum",          "spectrum"),
    ("Static",            "static"),
    ("Breathing — uno",   "breath_single"),
    ("Breathing — dos",   "breath_dual"),
    ("Breathing random",  "breath_random"),
    ("Wave",              "wave"),
    ("Reactive",          "reactive"),
    ("Ripple",            "ripple"),
    ("Ripple random",     "ripple_random"),
    ("Starlight — uno",   "starlight_single"),
    ("Starlight — dos",   "starlight_dual"),
    ("Starlight random",  "starlight_random"),
    ("Sin luz",           "none"),
]

EFFECTS_MOUSE = [
    ("Spectrum",          "logo_spectrum"),
    ("Static",            "logo_static"),
    ("Breathing — uno",   "logo_breath_single"),
    ("Breathing — dos",   "logo_breath_dual"),
    ("Breathing random",  "logo_breath_random"),
    ("Reactive",          "logo_reactive"),
    ("Sin luz",           "logo_none"),
]

WAVE_DIRS  = [("Derecha →", 1), ("Izquierda ←", 2)]
SPEED_OPTS = [("Lento", 1), ("Normal", 2), ("Rápido", 3)]


def _device_key(device) -> str:
    return device.name.replace("Razer ", "")


def read_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return {}


def write_device_state(device, state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    full = read_state()
    full[_device_key(device)] = state
    STATE_FILE.write_text(json.dumps(full))


def color_button(initial: QColor) -> QPushButton:
    btn = QPushButton()
    btn.setFixedSize(40, 28)
    btn._color = initial
    _repaint_btn(btn)
    return btn


def _repaint_btn(btn: QPushButton):
    btn.setStyleSheet(f"background-color: {btn._color.name()}; border: 1px solid #666;")


def pick_color(btn: QPushButton):
    c = QColorDialog.getColor(btn._color)
    if c.isValid():
        btn._color = c
        _repaint_btn(btn)


class DeviceTab(QWidget):
    def __init__(self, device, effects: list, is_keyboard: bool):
        super().__init__()
        self.device      = device
        self.effects     = effects
        self.is_keyboard = is_keyboard

        root = QVBoxLayout(self)
        root.setSpacing(12)

        # Brightness
        br_box = QGroupBox("Brillo")
        br_lay = QHBoxLayout(br_box)
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(0, 100)
        try:
            self.brightness_slider.setValue(int(device.brightness))
        except Exception:
            self.brightness_slider.setValue(100)
        self.brightness_slider.setTickInterval(10)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.bri_label = QLabel(f"{self.brightness_slider.value()}%")
        self.brightness_slider.valueChanged.connect(
            lambda v: self.bri_label.setText(f"{v}%")
        )
        br_lay.addWidget(self.brightness_slider)
        br_lay.addWidget(self.bri_label)
        root.addWidget(br_box)

        # Effect selector
        fx_box = QGroupBox("Efecto")
        fx_lay = QVBoxLayout(fx_box)
        self.effect_combo = QComboBox()
        for label, _ in effects:
            self.effect_combo.addItem(label)
        self.effect_combo.currentIndexChanged.connect(self._on_effect_changed)
        fx_lay.addWidget(self.effect_combo)
        root.addWidget(fx_box)

        # Options
        self.opts_box = QGroupBox("Opciones")
        self.opts_lay = QVBoxLayout(self.opts_box)
        root.addWidget(self.opts_box)

        self._c1 = QColor(255, 0, 0)
        self._c2 = QColor(0, 0, 255)
        self._build_color_row()
        self._build_wave_row()
        self._build_speed_row()

        # Apply
        self.apply_btn = QPushButton("Aplicar")
        self.apply_btn.setFixedHeight(36)
        self.apply_btn.clicked.connect(self._apply)
        root.addWidget(self.apply_btn)

        root.addStretch()
        self._on_effect_changed(0)

    def _build_color_row(self):
        self.color_row = QWidget()
        lay = QHBoxLayout(self.color_row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("Color 1:"))
        self.btn_c1 = color_button(self._c1)
        self.btn_c1.clicked.connect(lambda: pick_color(self.btn_c1))
        lay.addWidget(self.btn_c1)
        lay.addSpacing(16)
        self.lbl_c2 = QLabel("Color 2:")
        self.btn_c2 = color_button(self._c2)
        self.btn_c2.clicked.connect(lambda: pick_color(self.btn_c2))
        lay.addWidget(self.lbl_c2)
        lay.addWidget(self.btn_c2)
        lay.addStretch()
        self.opts_lay.addWidget(self.color_row)

    def _build_wave_row(self):
        self.wave_row = QWidget()
        lay = QHBoxLayout(self.wave_row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("Dirección:"))
        self.wave_combo = QComboBox()
        for label, _ in WAVE_DIRS:
            self.wave_combo.addItem(label)
        lay.addWidget(self.wave_combo)
        lay.addStretch()
        self.opts_lay.addWidget(self.wave_row)

    def _build_speed_row(self):
        self.speed_row = QWidget()
        lay = QHBoxLayout(self.speed_row)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(QLabel("Velocidad:"))
        self.speed_combo = QComboBox()
        for label, _ in SPEED_OPTS:
            self.speed_combo.addItem(label)
        self.speed_combo.setCurrentIndex(1)
        lay.addWidget(self.speed_combo)
        lay.addStretch()
        self.opts_lay.addWidget(self.speed_row)

    def _on_effect_changed(self, _=None):
        key = self._current_key()
        needs_c1   = key in ("static", "breath_single", "breath_dual", "reactive",
                             "ripple", "starlight_single", "starlight_dual",
                             "logo_static", "logo_breath_single", "logo_breath_dual",
                             "logo_reactive")
        needs_c2   = key in ("breath_dual", "starlight_dual", "logo_breath_dual")
        needs_wave = key == "wave"
        needs_spd  = key in ("reactive", "starlight_single", "starlight_dual",
                             "starlight_random", "logo_reactive")

        self.color_row.setVisible(needs_c1)
        self.lbl_c2.setVisible(needs_c2)
        self.btn_c2.setVisible(needs_c2)
        self.wave_row.setVisible(needs_wave)
        self.speed_row.setVisible(needs_spd)
        self.opts_box.setVisible(needs_c1 or needs_wave or needs_spd)

    def _current_key(self):
        return self.effects[self.effect_combo.currentIndex()][1]

    def _rgb(self, btn):
        c = btn._color
        return c.red(), c.green(), c.blue()

    def _speed(self):
        return SPEED_OPTS[self.speed_combo.currentIndex()][1]

    def _wave_dir(self):
        return WAVE_DIRS[self.wave_combo.currentIndex()][1]

    def _apply(self):
        # Brightness (works for all modes)
        try:
            self.device.brightness = self.brightness_slider.value()
        except Exception:
            pass

        key        = self._current_key()
        r1, g1, b1 = self._rgb(self.btn_c1)
        r2, g2, b2 = self._rgb(self.btn_c2)
        sp         = self._speed()
        fx         = self.device.fx

        if self.is_keyboard:
            if key == "spectrum":
                write_device_state(self.device, {"mode": "spectrum"})
            elif key == "static":
                write_device_state(self.device, {"mode": "static", "color": [r1, g1, b1]})
            elif key == "breath_single":
                write_device_state(self.device, {"mode": "breath", "color": [r1, g1, b1]})
            else:
                # Hardware effect: pause the matrix service so it doesn't override
                write_device_state(self.device, {"mode": "hardware"})
                hardware = {
                    "breath_dual":      lambda: fx.breath_dual(r1, g1, b1, r2, g2, b2),
                    "breath_random":    lambda: fx.breath_random(),
                    "wave":             lambda: fx.wave(self._wave_dir()),
                    "reactive":         lambda: fx.reactive(r1, g1, b1, sp),
                    "ripple":           lambda: fx.ripple(r1, g1, b1),
                    "ripple_random":    lambda: fx.ripple_random(),
                    "starlight_single": lambda: fx.starlight_single(sp, r1, g1, b1),
                    "starlight_dual":   lambda: fx.starlight_dual(sp, r1, g1, b1, r2, g2, b2),
                    "starlight_random": lambda: fx.starlight_random(sp),
                    "none":             lambda: fx.none(),
                }
                if key in hardware:
                    hardware[key]()
        else:
            # Mouse logo — always hardware (no matrix service for mouse)
            mouse_fx = {
                "logo_spectrum":      lambda: fx.misc.logo.spectrum(),
                "logo_static":        lambda: fx.misc.logo.static(r1, g1, b1),
                "logo_breath_single": lambda: fx.misc.logo.breath_single(r1, g1, b1),
                "logo_breath_dual":   lambda: fx.misc.logo.breath_dual(r1, g1, b1, r2, g2, b2),
                "logo_breath_random": lambda: fx.misc.logo.breath_random(),
                "logo_reactive":      lambda: fx.misc.logo.reactive(r1, g1, b1, sp),
                "logo_none":          lambda: fx.misc.logo.none(),
            }
            if key in mouse_fx:
                mouse_fx[key]()

        self.apply_btn.setText("Aplicado ✓")
        self.apply_btn.setStyleSheet("color: #4caf50;")
        QTimer.singleShot(1500, self._reset_btn)

    def _reset_btn(self):
        self.apply_btn.setText("Aplicar")
        self.apply_btn.setStyleSheet("")


class MainWindow(QMainWindow):
    def __init__(self, devices):
        super().__init__()
        self.setWindowTitle("Razer RGB Control")
        self.setWindowIcon(QIcon(str(ICON_PATH)))
        self.setMinimumWidth(440)

        tabs = QTabWidget()
        self.setCentralWidget(tabs)

        for dev in devices:
            is_kb = "keyboard" in dev.type.lower() if hasattr(dev, "type") else True
            effects = EFFECTS_KEYBOARD if is_kb else EFFECTS_MOUSE
            tab = DeviceTab(dev, effects, is_keyboard=is_kb)
            tabs.addTab(tab, dev.name.replace("Razer ", ""))



def main():
    dm = DeviceManager()
    dm.sync_effects = False
    if not dm.devices:
        print("No se encontraron dispositivos Razer. ¿Está corriendo openrazer-daemon?")
        sys.exit(1)

    app = QApplication(sys.argv)
    app.setDesktopFileName("razer-rgb")
    app.setWindowIcon(QIcon(str(ICON_PATH)))
    app.setStyle("Fusion")

    pal = QPalette()
    pal.setColor(QPalette.ColorRole.Window,          QColor(30,  30,  30))
    pal.setColor(QPalette.ColorRole.WindowText,      QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Base,            QColor(22,  22,  22))
    pal.setColor(QPalette.ColorRole.AlternateBase,   QColor(40,  40,  40))
    pal.setColor(QPalette.ColorRole.Text,            QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Button,          QColor(45,  45,  45))
    pal.setColor(QPalette.ColorRole.ButtonText,      QColor(220, 220, 220))
    pal.setColor(QPalette.ColorRole.Highlight,       QColor(0,   120, 215))
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor(255, 255, 255))
    app.setPalette(pal)

    win = MainWindow(dm.devices)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
