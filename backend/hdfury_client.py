import socket
import threading
import time
from typing import Callable, Optional

from backend.logger import log as _log

RECONNECT_DELAY = 2
SWITCH_TIMEOUT = 3
POLL_INTERVAL = 2
MAX_INPUTS = 4
QUERY_COMMANDS = b"get inseltx0\nget inseltx1\n"


class HDFuryClient:
    def __init__(
        self,
        ip: str,
        port: int = 2222,
        on_tx0_change: Optional[Callable[[int], None]] = None,
        on_tx1_change: Optional[Callable[[int], None]] = None,
    ):
        self.ip = ip
        self.port = port
        self._on_tx0_change = on_tx0_change
        self._on_tx1_change = on_tx1_change
        self._sock: Optional[socket.socket] = None
        self._sock_lock = threading.Lock()
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def switch_to(self, output: str, input_number: int) -> None:
        if not 0 <= input_number < MAX_INPUTS:
            raise ValueError(f"input_number must be 0–{MAX_INPUTS - 1}, got {input_number}")
        deadline = time.time() + SWITCH_TIMEOUT
        while True:
            with self._sock_lock:
                sock = self._sock
            if sock is not None:
                break
            if time.time() >= deadline:
                raise ConnectionError(f"Not connected to {self.ip}:{self.port}")
            time.sleep(0.05)
        cmd = f"set insel{output} {input_number}\n"
        sock.sendall(cmd.encode())

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
                sock.settimeout(POLL_INTERVAL)
            except Exception as e:
                _log(f"hdfury connection to {self.ip}:{self.port} failed: {e}")
                time.sleep(RECONNECT_DELAY)
                continue

            _log(f"hdfury connected to {self.ip}:{self.port}")
            with self._sock_lock:
                self._sock = sock

            self._listen(sock)

            with self._sock_lock:
                self._sock = None
            try:
                sock.close()
            except Exception:
                pass

            _log(f"hdfury disconnected from {self.ip}:{self.port}, reconnecting in {RECONNECT_DELAY}s")
            if self._running:
                time.sleep(RECONNECT_DELAY)

    def _listen(self, sock: socket.socket) -> None:
        try:
            sock.sendall(QUERY_COMMANDS)
        except Exception as e:
            _log(f"hdfury initial query to {self.ip} failed: {e}")
            return

        buffer = ""
        while self._running:
            try:
                data = sock.recv(256)
                if not data:
                    _log(f"hdfury connection to {self.ip} closed by server")
                    break
                text = data.decode("ascii", errors="ignore")
                buffer += text
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    self._handle_line(line.strip())
            except socket.timeout:
                try:
                    sock.sendall(QUERY_COMMANDS)
                except Exception:
                    break
            except Exception as e:
                _log(f"hdfury recv error on {self.ip}: {e}")
                break

    def _handle_line(self, line: str) -> None:
        parts = line.split()
        if len(parts) != 2:
            return
        output, raw = parts[0], parts[1]
        try:
            active_input = int(raw)
        except ValueError:
            return
        if output == "inseltx0" and self._on_tx0_change:
            self._on_tx0_change(active_input)
        elif output == "inseltx1" and self._on_tx1_change:
            self._on_tx1_change(active_input)
