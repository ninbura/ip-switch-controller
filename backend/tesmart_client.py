import socket

class TesmartClient:
    def __init__(self, ip: str, port: int = 5000):
        self.ip = ip
        self.port = port

    def _send(self, command: bytes) -> bytes:
        with socket.create_connection((self.ip, self.port), timeout=3) as sock:
            sock.sendall(command)
            return sock.recv(256)

    def switch_to(self, pc_number: int) -> None:
        """Switch the active input to the given PC number (1–16)."""
        if not 1 <= pc_number <= 16:
            raise ValueError(f"pc_number must be 1–16, got {pc_number}")
        command = bytes([0xAA, 0xBB, 0x03, 0x01, pc_number, 0xEE])
        self._send(command)

    def get_active_input(self) -> int:
        """Return the currently active input port number (1–16)."""
        command = bytes([0xAA, 0xBB, 0x03, 0x10, 0x00, 0xEE])
        response = self._send(command)
        # Response mirrors the command structure; active port is at byte index 4
        return response[4]