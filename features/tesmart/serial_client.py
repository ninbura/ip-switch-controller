import threading
import time
from typing import Callable, Optional

try:
    import serial
except ImportError:
    serial = None  # type: ignore

from ...shared.logger import log as _log

RECONNECT_DELAY = 2
SWITCH_TIMEOUT = 3
READ_TIMEOUT = 1
FEEDBACK_OPCODE = 0x11
PACKET_HEADER = (0xAA, 0xBB)
PACKET_LENGTH = 6

def _build_switch_packet(input_number: int) -> bytes:
    n = input_number - 1  # 0-indexed on wire per UART docs
    checksum = (0xAA + 0xBB + 0x03 + 0x00 + n) & 0xFF
    return bytes([0xAA, 0xBB, 0x03, 0x00, n, checksum])


class TESmartSerialClient:
    def __init__(self, port: str, on_input_change: Optional[Callable[[int], None]] = None):
        self.port = port
        self._on_input_change = on_input_change
        self._serial: Optional["serial.Serial"] = None
        self._serial_lock = threading.Lock()
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
            with self._serial_lock:
                ser = self._serial
            if ser is not None:
                break
            if time.time() >= deadline:
                raise ConnectionError(f"Not connected to {self.port}")
            time.sleep(0.05)
        with self._pending_lock:
            self._pending_switch = input_number
        with self._serial_lock:
            if self._serial:
                self._serial.write(_build_switch_packet(input_number))
                self._serial.flush()

    def stop(self) -> None:
        self._running = False
        with self._serial_lock:
            if self._serial:
                self._serial.close()
                self._serial = None

    def _run(self) -> None:
        while self._running:
            if serial is None:
                _log("pyserial not installed; cannot open serial port")
                time.sleep(RECONNECT_DELAY)
                continue
            try:
                ser = serial.Serial(
                    self.port,
                    baudrate=9600,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=READ_TIMEOUT,
                )
            except Exception as e:
                _log(f"tesmart serial open {self.port} failed: {e}")
                time.sleep(RECONNECT_DELAY)
                continue

            _log(f"tesmart serial opened {self.port}")
            with self._serial_lock:
                self._serial = ser

            self._listen(ser)

            with self._serial_lock:
                self._serial = None
            try:
                ser.close()
            except Exception:
                pass

            _log(f"tesmart serial closed {self.port}, reconnecting in {RECONNECT_DELAY}s")
            if self._running:
                time.sleep(RECONNECT_DELAY)

    def _listen(self, ser: "serial.Serial") -> None:
        buffer = b""
        while self._running:
            try:
                data = ser.read(1)
            except Exception as e:
                _log(f"tesmart serial read error on {self.port}: {e}")
                break
            if not data:
                continue  # read timeout, loop and re-check _running
            buffer += data
            try:
                waiting = ser.in_waiting
                if waiting:
                    buffer += ser.read(waiting)
            except Exception:
                pass
            while len(buffer) >= PACKET_LENGTH:
                self._handle_packet(buffer[:PACKET_LENGTH])
                buffer = buffer[PACKET_LENGTH:]

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
