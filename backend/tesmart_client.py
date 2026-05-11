import socket
import threading
import time
from typing import Callable, Optional

from backend.logger import log as _log

RECONNECT_DELAY = 2
SWITCH_TIMEOUT = 3
FEEDBACK_OPCODE = 0x11
PACKET_HEADER = (0xAA, 0xBB)
PACKET_LENGTH = 6
QUERY_COMMAND = bytes([0xAA, 0xBB, 0x03, 0x10, 0x00, 0xEE])


class TesmartClient:
    def __init__(self, ip: str, port: int = 5000, on_input_change: Optional[Callable[[int], None]] = None):
        self.ip = ip
        self.port = port
        self._on_input_change = on_input_change
        self._sock: Optional[socket.socket] = None
        self._sock_lock = threading.Lock()
        self._pending_switch: Optional[int] = None
        self._pending_lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def switch_to(self, input_number: int) -> None:
        if not 1 <= input_number <= 16:
            raise ValueError(f"input_number must be 1–16, got {input_number}")
        deadline = time.time() + SWITCH_TIMEOUT
        while True:
            with self._sock_lock:
                sock = self._sock
            if sock is not None:
                break
            if time.time() >= deadline:
                raise ConnectionError(f"Not connected to {self.ip}")
            time.sleep(0.05)
        with self._pending_lock:
            self._pending_switch = input_number
        sock.sendall(bytes([0xAA, 0xBB, 0x03, 0x01, input_number, 0xEE]))

    def stop(self) -> None:
        self._running = False
        with self._sock_lock:
            if self._sock:
                self._sock.close()
                self._sock = None

    def _run(self) -> None:
        while self._running:
            try:
                sock = socket.create_connection((self.ip, self.port), timeout=5)
                sock.settimeout(None)
            except Exception as e:
                _log(f"tesmart connection to {self.ip}:{self.port} failed: {e}")
                time.sleep(RECONNECT_DELAY)
                continue

            _log(f"tesmart connected to {self.ip}:{self.port}")
            with self._sock_lock:
                self._sock = sock

            self._listen(sock)

            with self._sock_lock:
                self._sock = None
            try:
                sock.close()
            except Exception:
                pass

            _log(f"tesmart disconnected from {self.ip}, reconnecting in {RECONNECT_DELAY}s")
            if self._running:
                time.sleep(RECONNECT_DELAY)

    def _listen(self, sock: socket.socket) -> None:
        buffer = b""

        try:
            sock.sendall(QUERY_COMMAND)
        except Exception as e:
            _log(f"tesmart initial query to {self.ip} failed: {e}")
            return

        while self._running:
            try:
                data = sock.recv(256)
                if not data:
                    _log(f"tesmart connection to {self.ip} closed by server")
                    break
                buffer += data
                while len(buffer) >= PACKET_LENGTH:
                    self._handle_packet(buffer[:PACKET_LENGTH])
                    buffer = buffer[PACKET_LENGTH:]
            except Exception as e:
                _log(f"tesmart recv error on {self.ip}: {e}")
                break

    def _handle_packet(self, packet: bytes) -> None:
        if packet[0] != PACKET_HEADER[0] or packet[1] != PACKET_HEADER[1]:
            return
        if packet[3] != FEEDBACK_OPCODE:
            return

        raw_input = packet[4] + 1  # 0-indexed in protocol, 1-indexed everywhere else

        with self._pending_lock:
            pending = self._pending_switch
            self._pending_switch = None

        active_input = pending if pending is not None else raw_input

        if self._on_input_change:
            self._on_input_change(active_input)
