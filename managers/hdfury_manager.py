import ipaddress
import threading
from typing import TYPE_CHECKING

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib

from ..backend.hdfury_client import HDFuryClient

if TYPE_CHECKING:
    from ..actions.hdfury.SwitchInput import HDFurySwitchInput


def _is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


class HDFuryManager:
    def __init__(self):
        self._actions: list["HDFurySwitchInput"] = []
        self._actions_lock = threading.Lock()
        self._clients: dict[tuple, HDFuryClient] = {}
        self._clients_lock = threading.Lock()
        self._last_active: dict[tuple, int] = {}  # keyed by (ip, port, output)

    def get_client(self, ip: str, port: int) -> HDFuryClient:
        key = (ip, port)
        with self._clients_lock:
            if key not in self._clients:
                self._clients[key] = HDFuryClient(
                    ip, port,
                    on_tx0_change=lambda n: self._on_output_change(ip, port, "tx0", n),
                    on_tx1_change=lambda n: self._on_output_change(ip, port, "tx1", n),
                )
            return self._clients[key]

    def register_action(self, action: "HDFurySwitchInput") -> None:
        ip, port, output = action.get_ip(), action.get_port(), action.get_output()
        with self._actions_lock:
            if action not in self._actions:
                self._actions.append(action)
        if _is_valid_ip(ip):
            self.get_client(ip, port)
        cache_key = (ip, port, output)
        if cache_key in self._last_active:
            GLib.idle_add(action.update_active_state, self._last_active[cache_key])

    def unregister_action(self, action: "HDFurySwitchInput") -> None:
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

    def notify_output(self, ip: str, port: int, output: str, active_input: int) -> None:
        self._on_output_change(ip, port, output, active_input)

    def handle_connection_change(
        self,
        action: "HDFurySwitchInput",
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
        cache_key = (new_ip, new_port, action.get_output())
        if cache_key in self._last_active:
            GLib.idle_add(action.update_active_state, self._last_active[cache_key])

    def _on_output_change(self, ip: str, port: int, output: str, active_input: int) -> None:
        cache_key = (ip, port, output)
        self._last_active[cache_key] = active_input
        with self._actions_lock:
            snapshot = [
                a for a in self._actions
                if a.get_ip() == ip and a.get_port() == port and a.get_output() == output
            ]
        for action in snapshot:
            GLib.idle_add(action.update_active_state, active_input)
