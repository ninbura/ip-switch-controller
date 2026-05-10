import logging
import socket
import threading
import time
from typing import Callable, Optional

log = logging.getLogger(__name__)

RECONNECT_DELAY = 0
POLL_INTERVAL = 2
SWITCH_TIMEOUT = 3  # seconds to wait for a connection before giving up
FEEDBACK_OPCODE = 0x10
PACKET_LENGTH = 6
QUERY_COMMAND = bytes([0xAA, 0xBB, 0x03, 0x10, 0x00, 0xEE])


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
                sock.settimeout(POLL_INTERVAL)
            except Exception as e:
                log.warning("Connection to %s:%d failed: %s", self.ip, self.port, e)
                time.sleep(RECONNECT_DELAY)
                continue

            with self._sock_lock:
                self._sock = sock

            log.debug("Connected to %s:%d", self.ip, self.port)
            self._listen(sock)

            with self._sock_lock:
                self._sock = None
            try:
                sock.close()
            except Exception:
                pass

            if self._running and RECONNECT_DELAY > 0:
                time.sleep(RECONNECT_DELAY)

    def _listen(self, sock: socket.socket) -> None:
        buffer = b""

        # Query immediately on connect to get the current active input
        try:
            sock.sendall(QUERY_COMMAND)
        except Exception as e:
            log.warning("Initial query to %s failed: %s", self.ip, e)
            return

        while self._running:
            try:
                data = sock.recv(256)
                if not data:
                    log.warning("Connection to %s closed by server", self.ip)
                    break
                buffer += data
                while len(buffer) >= PACKET_LENGTH:
                    self._handle_packet(buffer[:PACKET_LENGTH])
                    buffer = buffer[PACKET_LENGTH:]
            except socket.timeout:
                # No data received — poll for current state
                try:
                    sock.sendall(QUERY_COMMAND)
                except Exception:
                    break
            except Exception:
                break

    def _handle_packet(self, packet: bytes) -> None:
        if packet[0] != 0xAA or packet[1] != 0xBB or packet[5] != 0xEE:
            return
        if packet[3] == FEEDBACK_OPCODE and self._on_input_change:
            self._on_input_change(packet[4] + 1)  # convert 0-indexed to 1-indexed
