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

DEFAULT_IP = "192.168.1.10"
DEFAULT_INPUT = 1
MAX_INPUTS = 16
DEFAULT_INACTIVE_COLOR = "#000000"
DEFAULT_ACTIVE_COLOR = "#006666"
SETTINGS_KEY_IP = "ip"
SETTINGS_KEY_INPUT = "input_number"
SETTINGS_KEY_INACTIVE_COLOR = "inactive_color"
SETTINGS_KEY_ACTIVE_COLOR = "active_color"


def _input_label(number: int) -> str:
    return f"Input {number}"


def _parse_color(hex_str: str) -> list[int]:
    """Convert '#RRGGBB' or 'RRGGBB' to [R, G, B, 255]. Returns black on invalid input."""
    try:
        h = hex_str.lstrip("#")
        return [int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255]
    except Exception:
        return [0, 0, 0, 255]


class SwitchInputAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = True
        self._last_active_input: Optional[int] = None

    def on_ready(self) -> None:
        settings = self.get_settings()
        number = settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT)
        self.set_center_label(_input_label(number))
        self.plugin_base.register_action(self)

    def on_removed_from_cache(self) -> None:
        self.plugin_base.unregister_action(self)

    def get_ip(self) -> str:
        return self.get_settings().get(SETTINGS_KEY_IP, DEFAULT_IP)

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
        number = settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT)
        ip = self.get_ip()
        try:
            self.plugin_base.get_client(ip).switch_to(number)
            self.plugin_base.notify_active_input(ip, number)
        except Exception:
            self.show_error(duration=2)

    def get_config_rows(self) -> list:
        settings = self.get_settings()

        self.ip_entry = Adw.EntryRow(title="IP Address")
        self.ip_entry.set_text(settings.get(SETTINGS_KEY_IP, DEFAULT_IP))
        self.ip_entry.connect("changed", self.on_ip_changed)

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

        return [self.ip_entry, self.input_selector, self.inactive_color_entry, self.active_color_entry]

    def on_ip_changed(self, entry) -> None:
        settings = self.get_settings()
        settings[SETTINGS_KEY_IP] = entry.get_text()
        self.set_settings(settings)

    def on_input_changed(self, combo, _param) -> None:
        settings = self.get_settings()
        number = combo.get_selected() + 1
        settings[SETTINGS_KEY_INPUT] = number
        self.set_settings(settings)
        self.set_center_label(_input_label(number))

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
