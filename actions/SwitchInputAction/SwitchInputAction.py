import os
import sys

_plugin_root = os.path.realpath(os.path.join(os.path.dirname(__file__ or ""), "..", ".."))
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)

from src.backend.PluginManager.ActionBase import ActionBase
from backend.tesmart_client import TesmartClient

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

DEFAULT_IP = "192.168.1.10"
DEFAULT_INPUT = 1
MAX_INPUTS = 16
SETTINGS_KEY_IP = "ip"
SETTINGS_KEY_INPUT = "input_number"
COLOR_ACTIVE = [0, 180, 0, 255]
COLOR_INACTIVE = [0, 0, 0, 0]


def _input_label(number: int) -> str:
    return f"Input {number}"


class SwitchInputAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = True

    def on_ready(self) -> None:
        icon_path = os.path.join(self.plugin_base.PATH, "assets", "info.png")
        self.set_media(media_path=icon_path, size=0.75)
        settings = self.get_settings()
        number = settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT)
        self.set_bottom_label(_input_label(number))
        self.plugin_base.register_action(self)

    def on_removed_from_cache(self) -> None:
        self.plugin_base.unregister_action(self)

    def get_ip(self) -> str:
        return self.get_settings().get(SETTINGS_KEY_IP, DEFAULT_IP)

    def update_active_state(self, active_input: int) -> None:
        settings = self.get_settings()
        number = settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT)
        if number == active_input:
            self.set_background_color(COLOR_ACTIVE)
        else:
            self.set_background_color(COLOR_INACTIVE)

    def on_key_down(self) -> None:
        settings = self.get_settings()
        number = settings.get(SETTINGS_KEY_INPUT, DEFAULT_INPUT)
        try:
            client = TesmartClient(self.get_ip())
            client.switch_to(number)
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

        return [self.ip_entry, self.input_selector]

    def on_ip_changed(self, entry) -> None:
        settings = self.get_settings()
        settings[SETTINGS_KEY_IP] = entry.get_text()
        self.set_settings(settings)

    def on_input_changed(self, combo, _param) -> None:
        settings = self.get_settings()
        number = combo.get_selected() + 1
        settings[SETTINGS_KEY_INPUT] = number
        self.set_settings(settings)
        self.set_bottom_label(_input_label(number))
