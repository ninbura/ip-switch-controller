import threading
from typing import TYPE_CHECKING

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib

from .serial_client import TESmartSerialClient

if TYPE_CHECKING:
    from .serial_switch_input import TESmartSerialSwitchInput


class TESmartSerialManager:
    def __init__(self):
        self._actions: list["TESmartSerialSwitchInput"] = []
        self._actions_lock = threading.Lock()
        self._clients: dict[str, TESmartSerialClient] = {}
        self._clients_lock = threading.Lock()
        self._last_active: dict[str, int] = {}  # keyed by serial port path

    def get_client(self, port: str) -> TESmartSerialClient:
        with self._clients_lock:
            if port not in self._clients:
                self._clients[port] = TESmartSerialClient(
                    port,
                    on_input_change=lambda active: self._on_input_change(port, active),
                )
            return self._clients[port]

    def register_action(self, action: "TESmartSerialSwitchInput") -> None:
        port = action.get_serial_port()
        with self._actions_lock:
            if action not in self._actions:
                self._actions.append(action)
        if port:
            self.get_client(port)
        if port in self._last_active:
            GLib.idle_add(action.update_active_state, self._last_active[port])

    def unregister_action(self, action: "TESmartSerialSwitchInput") -> None:
        port = action.get_serial_port()
        with self._actions_lock:
            if action in self._actions:
                self._actions.remove(action)
            still_used = any(a.get_serial_port() == port for a in self._actions)
        if not still_used:
            with self._clients_lock:
                client = self._clients.pop(port, None)
            if client:
                client.stop()

    def notify_input(self, port: str, active_input: int) -> None:
        self._on_input_change(port, active_input)

    def handle_port_change(
        self,
        action: "TESmartSerialSwitchInput",
        old_port: str,
        new_port: str,
    ) -> None:
        with self._actions_lock:
            still_used = any(
                a is not action and a.get_serial_port() == old_port
                for a in self._actions
            )
        if not still_used and old_port:
            with self._clients_lock:
                client = self._clients.pop(old_port, None)
            if client:
                client.stop()
        if new_port:
            self.get_client(new_port)
        if new_port in self._last_active:
            GLib.idle_add(action.update_active_state, self._last_active[new_port])

    def _on_input_change(self, port: str, active_input: int) -> None:
        self._last_active[port] = active_input
        with self._actions_lock:
            snapshot = [a for a in self._actions if a.get_serial_port() == port]
        for action in snapshot:
            GLib.idle_add(action.update_active_state, active_input)
