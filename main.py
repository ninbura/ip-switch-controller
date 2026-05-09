import threading
import time

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib

from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder

from .actions.SwitchInputAction.SwitchInputAction import SwitchInputAction
from .backend.tesmart_client import TesmartClient

POLL_INTERVAL = 2


class TesmartController(PluginBase):
    def __init__(self):
        super().__init__()

        self._actions: list[SwitchInputAction] = []
        self._actions_lock = threading.Lock()

        self.switch_input_holder = ActionHolder(
            plugin_base=self,
            action_base=SwitchInputAction,
            action_id="dev_ninbura_TesmartController::SwitchInput",
            action_name="Switch Input",
        )
        self.add_action_holder(self.switch_input_holder)

        self.register(
            plugin_name="TeSmart Controller",
            github_repo="https://github.com/ninbura/tesmart-controller",
            plugin_version="1.0.0",
            app_version="1.1.1-alpha"
        )

        self._poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._poll_thread.start()

    def register_action(self, action: "SwitchInputAction") -> None:
        with self._actions_lock:
            if action not in self._actions:
                self._actions.append(action)

    def unregister_action(self, action: "SwitchInputAction") -> None:
        with self._actions_lock:
            if action in self._actions:
                self._actions.remove(action)

    def _poll_loop(self) -> None:
        while True:
            with self._actions_lock:
                actions_snapshot = list(self._actions)

            by_ip: dict[str, list] = {}
            for action in actions_snapshot:
                by_ip.setdefault(action.get_ip(), []).append(action)

            for ip, actions in by_ip.items():
                try:
                    active = TesmartClient(ip).get_active_input()
                    for action in actions:
                        GLib.idle_add(action.update_active_state, active)
                except Exception:
                    pass

            time.sleep(POLL_INTERVAL)
