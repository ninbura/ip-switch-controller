import ipaddress
import threading
from typing import TYPE_CHECKING

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib

from ..backend.tesmart_client import TESmartClient

if TYPE_CHECKING:
    from ..actions.tesmart.SwitchInput import TESmartSwitchInput


def _is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


class TESmartManager:
    def __init__(self):
        self._actions: list["TESmartSwitchInput"] = []
        self._actions_lock = threading.Lock()
        self._clients: dict[tuple, TESmartClient] = {}
        self._clients_lock = threading.Lock()
        self._last_active: dict[tuple, int] = {}  # keyed by (ip, port)

    def get_client(self, ip: str, port: int) -> TESmartClient:
        key = (ip, port)
        with self._clients_lock:
            if key not in self._clients:
                self._clients[key] = TESmartClient(
                    ip, port,
                    on_input_change=lambda active: self._on_input_change(ip, port, active),
                )
            return self._clients[key]

    def register_action(self, action: "TESmartSwitchInput") -> None:
        ip, port = action.get_ip(), action.get_port()
        with self._actions_lock:
            if action not in self._actions:
                self._actions.append(action)
        if _is_valid_ip(ip):
            self.get_client(ip, port)
        cache_key = (ip, port)
        if cache_key in self._last_active:
            GLib.idle_add(action.update_active_state, self._last_active[cache_key])

    def unregister_action(self, action: "TESmartSwitchInput") -> None:
        ip, port = action.get_ip(), action.get_port()
        with self._actions_lock:
            if action in self._actions:
                self._actions.remove(action)
            still_used = any(a.get_ip() == ip and a.get_port() == port for a in self._actions)
        if not still_used:
            with self._clients_lock:
                client = self._clients.pop((ip, port), None)
            if client:
                client.stop()

    def notify_input(self, ip: str, port: int, active_input: int) -> None:
        self._on_input_change(ip, port, active_input)

    def handle_connection_change(
        self,
        action: "TESmartSwitchInput",
        old_ip: str,
        old_port: int,
        new_ip: str,
        new_port: int,
    ) -> None:
        with self._actions_lock:
            still_used = any(
                a is not action and a.get_ip() == old_ip and a.get_port() == old_port
                for a in self._actions
            )
        if not still_used:
            with self._clients_lock:
                client = self._clients.pop((old_ip, old_port), None)
            if client:
                client.stop()
        if _is_valid_ip(new_ip):
            self.get_client(new_ip, new_port)
        cache_key = (new_ip, new_port)
        if cache_key in self._last_active:
            GLib.idle_add(action.update_active_state, self._last_active[cache_key])

    def _on_input_change(self, ip: str, port: int, active_input: int) -> None:
        cache_key = (ip, port)
        self._last_active[cache_key] = active_input
        with self._actions_lock:
            snapshot = [a for a in self._actions if a.get_ip() == ip and a.get_port() == port]
        for action in snapshot:
            GLib.idle_add(action.update_active_state, active_input)
