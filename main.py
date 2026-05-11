import threading

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib

from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport
from src.backend.DeckManagement.InputIdentifier import Input

from .actions.SwitchInputAction.SwitchInputAction import SwitchInputAction
from .backend.tesmart_client import TesmartClient


class TesmartController(PluginBase):
    def __init__(self):
        super().__init__()

        self._actions: list[SwitchInputAction] = []
        self._actions_lock = threading.Lock()
        self._clients: dict[str, TesmartClient] = {}
        self._clients_lock = threading.Lock()
        self._last_active: dict[str, int] = {}

        self.switch_input_holder = ActionHolder(
            plugin_base=self,
            action_base=SwitchInputAction,
            action_id="dev_ninbura_TesmartController::SwitchInput",
            action_name="Switch Input",
            action_support={
                Input.Key: ActionInputSupport.SUPPORTED,
                Input.Dial: ActionInputSupport.UNSUPPORTED,
                Input.Touchscreen: ActionInputSupport.UNSUPPORTED,
            },
        )
        self.add_action_holder(self.switch_input_holder)

        self.register(
            plugin_name="TeSmart Controller",
            github_repo="https://github.com/ninbura/tesmart-controller",
            plugin_version="1.0.0",
            app_version="1.1.1-alpha"
        )

    def get_client(self, ip: str) -> TesmartClient:
        with self._clients_lock:
            if ip not in self._clients:
                self._clients[ip] = TesmartClient(
                    ip,
                    on_input_change=lambda active: self._on_input_change(ip, active),
                )
            return self._clients[ip]

    def register_action(self, action: "SwitchInputAction") -> None:
        ip = action.get_ip()
        with self._actions_lock:
            if action not in self._actions:
                self._actions.append(action)
        self.get_client(ip)
        if ip in self._last_active:
            GLib.idle_add(action.update_active_state, self._last_active[ip])

    def unregister_action(self, action: "SwitchInputAction") -> None:
        ip = action.get_ip()
        with self._actions_lock:
            if action in self._actions:
                self._actions.remove(action)
            still_used = any(a.get_ip() == ip for a in self._actions)
        if not still_used:
            with self._clients_lock:
                client = self._clients.pop(ip, None)
            if client:
                client.stop()

    def notify_active_input(self, ip: str, active_input: int) -> None:
        with self._actions_lock:
            actions_snapshot = [a for a in self._actions if a.get_ip() == ip]
        for action in actions_snapshot:
            GLib.idle_add(action.update_active_state, active_input)

    def _on_input_change(self, ip: str, active_input: int) -> None:
        self._last_active[ip] = active_input
        self.notify_active_input(ip, active_input)
