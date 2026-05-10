import glob
import os
import socket
import threading
import time
from datetime import datetime
from typing import Callable, Optional

RECONNECT_DELAY = 2
SWITCH_TIMEOUT = 3
FEEDBACK_OPCODE = 0x11
PACKET_HEADER = (0xAA, 0xBB)
PACKET_LENGTH = 6
QUERY_COMMAND = bytes([0xAA, 0xBB, 0x03, 0x10, 0x00, 0xEE])

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__ or ""))), "log")
_LOG_PATH = os.path.join(_LOG_DIR, f"debug_{datetime.now().strftime('%Y-%m-%dT%H-%M-%S')}.log")
_MAX_LOGS = 10


def _setup_log() -> None:
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        logs = sorted(glob.glob(os.path.join(_LOG_DIR, "debug_*.log")))
        for old in logs[:-(_MAX_LOGS - 1)]:
            os.remove(old)
    except Exception:
        pass


_setup_log()


def _log(msg: str) -> None:
    try:
        with open(_LOG_PATH, "a") as f:
            f.write(f"[tesmart] {msg}\n")
    except Exception:
        pass


class TesmartClient:
    def __init__(self, ip: str, port: int = 5000, on_input_change: Optional[Callable[[int], None]] = None):
        self.ip = ip
        self.port = port
        self._on_input_change = on_input_change
        self._sock: Optional[socket.socket] = None
        self._sock_lock = threading.Lock()
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
            except Exception as e:
                _log(f"connection to {self.ip}:{self.port} failed: {e}")
                time.sleep(RECONNECT_DELAY)
                continue

            _log(f"connected to {self.ip}:{self.port}")
            with self._sock_lock:
                self._sock = sock

            self._listen(sock)

            with self._sock_lock:
                self._sock = None
            try:
                sock.close()
            except Exception:
                pass

            _log(f"disconnected from {self.ip}, reconnecting in {RECONNECT_DELAY}s")
            if self._running:
                time.sleep(RECONNECT_DELAY)

    def _listen(self, sock: socket.socket) -> None:
        buffer = b""

        # One initial query to get the current active input on connect
        try:
            sock.sendall(QUERY_COMMAND)
            _log(f"sent initial query to {self.ip}")
        except Exception as e:
            _log(f"initial query to {self.ip} failed: {e}")
            return

        # Passive listener — the switch broadcasts 0x11 on every input change
        while self._running:
            try:
                data = sock.recv(256)
                if not data:
                    _log(f"connection to {self.ip} closed by server")
                    break
                _log(f"recv {self.ip}: {data.hex()}")
                buffer += data
                while len(buffer) >= PACKET_LENGTH:
                    self._handle_packet(buffer[:PACKET_LENGTH])
                    buffer = buffer[PACKET_LENGTH:]
            except Exception as e:
                _log(f"recv error on {self.ip}: {e}")
                break

    def _handle_packet(self, packet: bytes) -> None:
        _log(f"packet {self.ip}: {packet.hex()}")
        if packet[0] != PACKET_HEADER[0] or packet[1] != PACKET_HEADER[1]:
            _log(f"invalid packet header, skipping")
            return
        if packet[3] == FEEDBACK_OPCODE:
            active_input = packet[4]  # already 1-indexed
            _log(f"active input on {self.ip}: {active_input}")
            if self._on_input_change:
                self._on_input_change(active_input)
