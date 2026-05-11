import ipaddress
import threading

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib

from src.backend.PluginManager.PluginBase import PluginBase
from src.backend.PluginManager.ActionHolder import ActionHolder
from src.backend.PluginManager.ActionInputSupport import ActionInputSupport
from src.backend.DeckManagement.InputIdentifier import Input

from .actions.tesmart.SwitchInput import TESmartSwitchInput
from .actions.hdfury.SwitchInput import HDFurySwitchInput
from .backend.tesmart_client import TESmartClient
from .backend.hdfury_client import HDFuryClient


def _is_valid_ip(ip: str) -> bool:
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


class IpSwitchController(PluginBase):
    def __init__(self):
        super().__init__()

        # TESmart state
        self._tesmart_actions: list[TESmartSwitchInput] = []
        self._tesmart_actions_lock = threading.Lock()
        self._tesmart_clients: dict[tuple, TESmartClient] = {}
        self._tesmart_clients_lock = threading.Lock()
        self._tesmart_last_active: dict[tuple, int] = {}  # keyed by (ip, port)

        # HDFury state
        self._hdfury_actions: list[HDFurySwitchInput] = []
        self._hdfury_actions_lock = threading.Lock()
        self._hdfury_clients: dict[tuple, HDFuryClient] = {}
        self._hdfury_clients_lock = threading.Lock()
        self._hdfury_last_active: dict[tuple, int] = {}  # keyed by (ip, port, output)

        self._register_action_holders()

        self.register(
            plugin_name="IP Switch Controller",
            github_repo="https://github.com/ninbura/tesmart-controller",
            plugin_version="1.0.0",
            app_version="1.1.1-alpha"
        )

    def _register_action_holders(self) -> None:
        action_support = {
            Input.Key: ActionInputSupport.SUPPORTED,
            Input.Dial: ActionInputSupport.UNSUPPORTED,
            Input.Touchscreen: ActionInputSupport.UNSUPPORTED,
        }
        self.add_action_holder(ActionHolder(
            plugin_base=self,
            action_base=TESmartSwitchInput,
            action_id="dev_ninbura_IpSwitchController::TESmartSwitchInput",
            action_name="TESmart: Switch Input",
            action_support=action_support,
        ))
        self.add_action_holder(ActionHolder(
            plugin_base=self,
            action_base=HDFurySwitchInput,
            action_id="dev_ninbura_IpSwitchController::HDFurySwitchInput",
            action_name="HDFury: Switch Input",
            action_support=action_support,
        ))

    # ── TESmart ──────────────────────────────────────────────────────────────

    def get_tesmart_client(self, ip: str, port: int) -> TESmartClient:
        key = (ip, port)
        with self._tesmart_clients_lock:
            if key not in self._tesmart_clients:
                self._tesmart_clients[key] = TESmartClient(
                    ip, port,
                    on_input_change=lambda active: self._on_tesmart_input_change(ip, port, active),
                )
            return self._tesmart_clients[key]

    def register_tesmart_action(self, action: TESmartSwitchInput) -> None:
        ip, port = action.get_ip(), action.get_port()
        with self._tesmart_actions_lock:
            if action not in self._tesmart_actions:
                self._tesmart_actions.append(action)
        if _is_valid_ip(ip):
            self.get_tesmart_client(ip, port)
        cache_key = (ip, port)
        if cache_key in self._tesmart_last_active:
            GLib.idle_add(action.update_active_state, self._tesmart_last_active[cache_key])

    def unregister_tesmart_action(self, action: TESmartSwitchInput) -> None:
        ip, port = action.get_ip(), action.get_port()
        with self._tesmart_actions_lock:
            if action in self._tesmart_actions:
                self._tesmart_actions.remove(action)
            still_used = any(a.get_ip() == ip and a.get_port() == port for a in self._tesmart_actions)
        if not still_used:
            with self._tesmart_clients_lock:
                client = self._tesmart_clients.pop((ip, port), None)
            if client:
                client.stop()

    def notify_tesmart_input(self, ip: str, port: int, active_input: int) -> None:
        self._on_tesmart_input_change(ip, port, active_input)

    def handle_tesmart_connection_change(
        self,
        action: TESmartSwitchInput,
        old_ip: str,
        old_port: int,
        new_ip: str,
        new_port: int,
    ) -> None:
        old_key = (old_ip, old_port)
        with self._tesmart_actions_lock:
            still_used = any(
                a is not action and a.get_ip() == old_ip and a.get_port() == old_port
                for a in self._tesmart_actions
            )
        if not still_used:
            with self._tesmart_clients_lock:
                client = self._tesmart_clients.pop(old_key, None)
            if client:
                client.stop()
        if _is_valid_ip(new_ip):
            self.get_tesmart_client(new_ip, new_port)
        cache_key = (new_ip, new_port)
        if cache_key in self._tesmart_last_active:
            GLib.idle_add(action.update_active_state, self._tesmart_last_active[cache_key])

    def _on_tesmart_input_change(self, ip: str, port: int, active_input: int) -> None:
        cache_key = (ip, port)
        self._tesmart_last_active[cache_key] = active_input
        with self._tesmart_actions_lock:
            snapshot = [a for a in self._tesmart_actions if a.get_ip() == ip and a.get_port() == port]
        for action in snapshot:
            GLib.idle_add(action.update_active_state, active_input)

    # ── HDFury ───────────────────────────────────────────────────────────────

    def get_hdfury_client(self, ip: str, port: int) -> HDFuryClient:
        key = (ip, port)
        with self._hdfury_clients_lock:
            if key not in self._hdfury_clients:
                self._hdfury_clients[key] = HDFuryClient(
                    ip, port,
                    on_tx0_change=lambda n: self._on_hdfury_output_change(ip, port, "tx0", n),
                    on_tx1_change=lambda n: self._on_hdfury_output_change(ip, port, "tx1", n),
                )
            return self._hdfury_clients[key]

    def register_hdfury_action(self, action: HDFurySwitchInput) -> None:
        ip, port, output = action.get_ip(), action.get_port(), action.get_output()
        with self._hdfury_actions_lock:
            if action not in self._hdfury_actions:
                self._hdfury_actions.append(action)
        if _is_valid_ip(ip):
            self.get_hdfury_client(ip, port)
        cache_key = (ip, port, output)
        if cache_key in self._hdfury_last_active:
            GLib.idle_add(action.update_active_state, self._hdfury_last_active[cache_key])

    def unregister_hdfury_action(self, action: HDFurySwitchInput) -> None:
        ip, port = action.get_ip(), action.get_port()
        with self._hdfury_actions_lock:
            if action in self._hdfury_actions:
                self._hdfury_actions.remove(action)
            still_used = any(a.get_ip() == ip and a.get_port() == port for a in self._hdfury_actions)
        if not still_used:
            with self._hdfury_clients_lock:
                client = self._hdfury_clients.pop((ip, port), None)
            if client:
                client.stop()

    def notify_hdfury_output(self, ip: str, port: int, output: str, active_input: int) -> None:
        self._on_hdfury_output_change(ip, port, output, active_input)

    def handle_hdfury_connection_change(
        self,
        action: HDFurySwitchInput,
        old_ip: str,
        old_port: int,
        new_ip: str,
        new_port: int,
    ) -> None:
        old_key = (old_ip, old_port)
        with self._hdfury_actions_lock:
            still_used = any(
                a is not action and a.get_ip() == old_ip and a.get_port() == old_port
                for a in self._hdfury_actions
            )
        if not still_used:
            with self._hdfury_clients_lock:
                client = self._hdfury_clients.pop(old_key, None)
            if client:
                client.stop()
        if _is_valid_ip(new_ip):
            self.get_hdfury_client(new_ip, new_port)
        cache_key = (new_ip, new_port, action.get_output())
        if cache_key in self._hdfury_last_active:
            GLib.idle_add(action.update_active_state, self._hdfury_last_active[cache_key])

    def _on_hdfury_output_change(self, ip: str, port: int, output: str, active_input: int) -> None:
        cache_key = (ip, port, output)
        self._hdfury_last_active[cache_key] = active_input
        with self._hdfury_actions_lock:
            snapshot = [
                a for a in self._hdfury_actions
                if a.get_ip() == ip and a.get_port() == port and a.get_output() == output
            ]
        for action in snapshot:
            GLib.idle_add(action.update_active_state, active_input)
