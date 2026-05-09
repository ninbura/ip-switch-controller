import os
import sys

# Add the plugin root to sys.path so backend/ is importable
_plugin_root = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _plugin_root not in sys.path:
    sys.path.insert(0, _plugin_root)

from src.backend.PluginManager.ActionBase import ActionBase  # provided by StreamController at runtime
from backend.tesmart_client import TesmartClient

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

DEFAULT_IP = "192.168.1.10"


class SwitchInputAction(ActionBase):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.has_configuration = True

    def on_ready(self) -> None:
        icon_path = os.path.join(self.plugin_base.PATH, "assets", "info.png")
        self.set_media(media_path=icon_path, size=0.75)
        settings = self.get_settings()
        pc = settings.get("pc_number", 1)
        self.set_bottom_label(f"PC {pc}")

    def on_key_down(self) -> None:
        settings = self.get_settings()
        ip = settings.get("ip", DEFAULT_IP)
        pc = settings.get("pc_number", 1)
        try:
            client = TesmartClient(ip)
            client.switch_to(pc)
        except Exception:
            self.show_error(duration=2)

    def get_config_rows(self) -> list:
        settings = self.get_settings()

        self.ip_entry = Adw.EntryRow(title="IP Address")
        self.ip_entry.set_text(settings.get("ip", DEFAULT_IP))
        self.ip_entry.connect("changed", self.on_ip_changed)

        pc_model = Gtk.StringList()
        for i in range(1, 17):
            pc_model.append(f"PC {i}")
        self.pc_selector = Adw.ComboRow(title="Switch to", model=pc_model)
        self.pc_selector.set_selected(settings.get("pc_number", 1) - 1)
        self.pc_selector.connect("notify::selected", self.on_pc_changed)

        return [self.ip_entry, self.pc_selector]

    def on_ip_changed(self, entry) -> None:
        settings = self.get_settings()
        settings["ip"] = entry.get_text()
        self.set_settings(settings)

    def on_pc_changed(self, combo, _param) -> None:
        settings = self.get_settings()
        pc_number = combo.get_selected() + 1
        settings["pc_number"] = pc_number
        self.set_settings(settings)
        self.set_bottom_label(f"PC {pc_number}")
