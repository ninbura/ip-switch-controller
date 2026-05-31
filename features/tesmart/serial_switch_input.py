import os
import sys
import traceback
from typing import Optional

_plugin_root = os.path.realpath(os.path.join(os.path.dirname(__file__ or ""), "..", ".."))
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)

from ...shared.logger import log as _log

from src.backend.PluginManager.ActionBase import ActionBase

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

try:
    import serial.tools.list_ports as _list_ports
    def _get_available_ports() -> list[tuple[str, str]]:
        return [(p.device, p.description or p.device) for p in _list_ports.comports()]
except ImportError:
    def _get_available_ports() -> list[tuple[str, str]]:
        return []

DEFAULT_SERIAL_PORT = ""
DEFAULT_INPUT = 1
MAX_INPUTS = 16
DEFAULT_LABEL_SIZE = 20
DEFAULT_INACTIVE_COLOR = "#000000"
DEFAULT_ACTIVE_COLOR = "#006666"
SETTINGS_KEY_SERIAL_PORT = "serial_port"
SETTINGS_KEY_INPUT = "input_number"
SETTINGS_KEY_INACTIVE_COLOR = "inactive_color"
SETTINGS_KEY_ACTIVE_COLOR = "active_color"


def _input_label(number: int) -> str:
    return f"Input {number}"


def _parse_color(hex_str: str) -> list[int]:
    try:
        h = hex_str.lstrip("#")
        return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255]
    except Exception:
        return [0, 0, 0, 255]


class TESmartSerialSwitchInput(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = True
        self._last_active_input: Optional[int] = None

    def on_ready(self) -> None:
        settings = self.get_settings()
        number = settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT)
        self.set_center_label(_input_label(number), font_size=DEFAULT_LABEL_SIZE)
        self.plugin_base.tesmart_serial.register_action(self)

    def on_removed_from_cache(self) -> None:
        self.plugin_base.tesmart_serial.unregister_action(self)

    def get_serial_port(self) -> str:
        return self.get_settings().get(SETTINGS_KEY_SERIAL_PORT, DEFAULT_SERIAL_PORT)

    def update_active_state(self, active_input: int) -> None:
        self._last_active_input = active_input
        settings = self.get_settings()
        number = settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT)
        if number == active_input:
            color = _parse_color(settings.get(SETTINGS_KEY_ACTIVE_COLOR, DEFAULT_ACTIVE_COLOR))
        else:
            color = _parse_color(settings.get(SETTINGS_KEY_INACTIVE_COLOR, DEFAULT_INACTIVE_COLOR))
        self.set_background_color(color)

    def on_key_down(self) -> None:
        settings = self.get_settings()
        port = settings.get(SETTINGS_KEY_SERIAL_PORT, DEFAULT_SERIAL_PORT)
        number = settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT)
        if not port:
            _log("tesmart serial: no port configured, cannot switch input")
            self.show_error(duration=2)
            return
        try:
            self.plugin_base.tesmart_serial.get_client(port).switch_to(number)
            self.plugin_base.tesmart_serial.notify_input(port, number)
        except Exception:
            _log(f"tesmart serial switch to input {number} on {port} failed:\n{traceback.format_exc()}")
            self.show_error(duration=2)

    def get_config_rows(self) -> list:
        settings = self.get_settings()
        saved_port = settings.get(SETTINGS_KEY_SERIAL_PORT, DEFAULT_SERIAL_PORT)

        available = _get_available_ports()
        port_paths = [p for p, _ in available]
        port_labels = [f"{p} — {d}" if d != p else p for p, d in available]

        if saved_port and saved_port not in port_paths:
            port_paths.insert(0, saved_port)
            port_labels.insert(0, f"{saved_port} (not connected)")

        self._port_paths = port_paths

        port_model = Gtk.StringList()
        for label in port_labels:
            port_model.append(label)
        if not port_labels:
            port_model.append("(no serial ports found)")

        self.port_selector = Adw.ComboRow(title="Serial Port", model=port_model)
        if saved_port in port_paths:
            self.port_selector.set_selected(port_paths.index(saved_port))
        self.port_selector.connect("notify::selected", self.on_port_changed)

        input_model = Gtk.StringList()
        for i in range(1, MAX_INPUTS + 1):
            input_model.append(_input_label(i))
        self.input_selector = Adw.ComboRow(title="Switch to", model=input_model)
        self.input_selector.set_selected(settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT) - 1)
        self.input_selector.connect("notify::selected", self.on_input_changed)

        self.inactive_color_entry = Adw.EntryRow(title="Inactive Color (hex)")
        self.inactive_color_entry.set_text(settings.get(SETTINGS_KEY_INACTIVE_COLOR, DEFAULT_INACTIVE_COLOR))
        self.inactive_color_entry.connect("changed", self.on_inactive_color_changed)

        self.active_color_entry = Adw.EntryRow(title="Active Color (hex)")
        self.active_color_entry.set_text(settings.get(SETTINGS_KEY_ACTIVE_COLOR, DEFAULT_ACTIVE_COLOR))
        self.active_color_entry.connect("changed", self.on_active_color_changed)

        return [self.port_selector, self.input_selector,
                self.inactive_color_entry, self.active_color_entry]

    def on_port_changed(self, combo, _param) -> None:
        idx = combo.get_selected()
        if not self._port_paths or idx >= len(self._port_paths):
            return
        new_port = self._port_paths[idx]
        settings = self.get_settings()
        old_port = settings.get(SETTINGS_KEY_SERIAL_PORT, DEFAULT_SERIAL_PORT)
        settings[SETTINGS_KEY_SERIAL_PORT] = new_port
        self.set_settings(settings)
        if old_port != new_port:
            self.plugin_base.tesmart_serial.handle_port_change(self, old_port, new_port)

    def on_input_changed(self, combo, _param) -> None:
        settings = self.get_settings()
        number = combo.get_selected() + 1
        settings[SETTINGS_KEY_INPUT] = number
        self.set_settings(settings)
        self.set_center_label(_input_label(number), font_size=DEFAULT_LABEL_SIZE)
        if self._last_active_input is not None:
            self.update_active_state(self._last_active_input)

    def on_inactive_color_changed(self, entry) -> None:
        settings = self.get_settings()
        settings[SETTINGS_KEY_INACTIVE_COLOR] = entry.get_text()
        self.set_settings(settings)
        if self._last_active_input is not None:
            self.update_active_state(self._last_active_input)

    def on_active_color_changed(self, entry) -> None:
        settings = self.get_settings()
        settings[SETTINGS_KEY_ACTIVE_COLOR] = entry.get_text()
        self.set_settings(settings)
        if self._last_active_input is not None:
            self.update_active_state(self._last_active_input)
