import os
import sys
from typing import Optional

_plugin_root = os.path.realpath(os.path.join(os.path.dirname(__file__ or ""), "..", ".."))
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)

from src.backend.PluginManager.ActionBase import ActionBase

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

DEFAULT_IP = ""
DEFAULT_PORT = 2222
DEFAULT_OUTPUT = "tx0"
DEFAULT_INPUT = 1
MAX_INPUTS = 4
DEFAULT_LABEL_SIZE = 20
DEFAULT_INACTIVE_COLOR = "#000000"
DEFAULT_ACTIVE_COLOR = "#006666"
SETTINGS_KEY_IP = "ip"
SETTINGS_KEY_PORT = "port"
SETTINGS_KEY_OUTPUT = "output"
SETTINGS_KEY_INPUT = "input_number"
SETTINGS_KEY_INACTIVE_COLOR = "inactive_color"
SETTINGS_KEY_ACTIVE_COLOR = "active_color"

OUTPUTS = ["tx0", "tx1"]
OUTPUT_LABELS = ["Output 1 (TX0)", "Output 2 (TX1)"]


def _input_label(number: int) -> str:
    return f"Input {number}"


def _parse_color(hex_str: str) -> list[int]:
    try:
        h = hex_str.lstrip("#")
        return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255]
    except Exception:
        return [0, 0, 0, 255]


class HDFurySwitchInput(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = True
        self._last_active_input: Optional[int] = None

    def on_ready(self) -> None:
        settings = self.get_settings()
        number = settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT)
        self.set_center_label(_input_label(number), font_size=DEFAULT_LABEL_SIZE)
        self.plugin_base.register_hdfury_action(self)

    def on_removed_from_cache(self) -> None:
        self.plugin_base.unregister_hdfury_action(self)

    def get_ip(self) -> str:
        return self.get_settings().get(SETTINGS_KEY_IP, DEFAULT_IP)

    def get_port(self) -> int:
        return self.get_settings().get(SETTINGS_KEY_PORT, DEFAULT_PORT)

    def get_output(self) -> str:
        return self.get_settings().get(SETTINGS_KEY_OUTPUT, DEFAULT_OUTPUT)

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
        ip = settings.get(SETTINGS_KEY_IP, DEFAULT_IP)
        port = settings.get(SETTINGS_KEY_PORT, DEFAULT_PORT)
        output = settings.get(SETTINGS_KEY_OUTPUT, DEFAULT_OUTPUT)
        number = settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT)
        if not ip:
            self.show_error(duration=2)
            return
        try:
            self.plugin_base.get_hdfury_client(ip, port).switch_to(output, number)
            self.plugin_base.notify_hdfury_output(ip, port, output, number)
        except Exception:
            self.show_error(duration=2)

    def get_config_rows(self) -> list:
        settings = self.get_settings()

        self.ip_entry = Adw.EntryRow(title="IP Address")
        self.ip_entry.set_text(settings.get(SETTINGS_KEY_IP, DEFAULT_IP))
        self.ip_entry.connect("changed", self.on_ip_changed)

        self.port_entry = Adw.EntryRow(title="Port")
        self.port_entry.set_text(str(settings.get(SETTINGS_KEY_PORT, DEFAULT_PORT)))
        self.port_entry.connect("changed", self.on_port_changed)

        output_model = Gtk.StringList()
        for label in OUTPUT_LABELS:
            output_model.append(label)
        self.output_selector = Adw.ComboRow(title="Output", model=output_model)
        current_output = settings.get(SETTINGS_KEY_OUTPUT, DEFAULT_OUTPUT)
        self.output_selector.set_selected(OUTPUTS.index(current_output) if current_output in OUTPUTS else 0)
        self.output_selector.connect("notify::selected", self.on_output_changed)

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

        return [self.ip_entry, self.port_entry, self.output_selector, self.input_selector,
                self.inactive_color_entry, self.active_color_entry]

    def on_ip_changed(self, entry) -> None:
        settings = self.get_settings()
        old_ip = settings.get(SETTINGS_KEY_IP, DEFAULT_IP)
        old_port = settings.get(SETTINGS_KEY_PORT, DEFAULT_PORT)
        new_ip = entry.get_text()
        settings[SETTINGS_KEY_IP] = new_ip
        self.set_settings(settings)
        if old_ip != new_ip:
            self.plugin_base.handle_hdfury_connection_change(self, old_ip, old_port, new_ip, old_port)

    def on_port_changed(self, entry) -> None:
        settings = self.get_settings()
        old_ip = settings.get(SETTINGS_KEY_IP, DEFAULT_IP)
        old_port = settings.get(SETTINGS_KEY_PORT, DEFAULT_PORT)
        try:
            new_port = int(entry.get_text())
        except ValueError:
            return
        settings[SETTINGS_KEY_PORT] = new_port
        self.set_settings(settings)
        if old_port != new_port:
            self.plugin_base.handle_hdfury_connection_change(self, old_ip, old_port, old_ip, new_port)

    def on_output_changed(self, combo, _param) -> None:
        settings = self.get_settings()
        settings[SETTINGS_KEY_OUTPUT] = OUTPUTS[combo.get_selected()]
        self.set_settings(settings)
        if self._last_active_input is not None:
            self.update_active_state(self._last_active_input)

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
