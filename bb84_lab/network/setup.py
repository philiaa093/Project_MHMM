"""Local browser setup for a network demo role and its optional Eve relay."""

from ipaddress import IPv4Address
import os
from pathlib import Path
import secrets
import threading

from bb84_lab.network.service import NetworkNode, make_transport_server
from bb84_lab.shared.paths import OUTPUT_ROOT


DEFAULT_PSK_PATH = OUTPUT_ROOT / "network" / "auth.key"
DEFAULT_PORT = 9100
PSK_BYTES = 32


class SetupConflict(ValueError):
    """A setup action conflicts with the current launcher or PSK state."""


def create_psk_file(path, value=None):
    if value is None:
        value = secrets.token_bytes(PSK_BYTES)
    if len(value) != PSK_BYTES:
        raise ValueError("Tệp PSK phải có đúng 32 byte")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(value)
    except OSError:
        path.unlink(missing_ok=True)
        raise


def read_psk_file(path):
    if not path.is_file():
        raise OSError("Không đọc được tệp PSK")
    with path.open("rb") as handle:
        value = handle.read(PSK_BYTES + 1)
    if len(value) != PSK_BYTES:
        raise ValueError("Tệp PSK phải có đúng 32 byte")
    return value


class NetworkSetup:
    def __init__(self, psk_path=DEFAULT_PSK_PATH, inbox=OUTPUT_ROOT / "received"):
        self._psk_path = Path(psk_path).absolute()
        self._inbox = Path(inbox)
        self._lock = threading.Lock()
        self._node = None
        self._eve = None
        self._transport = None
        self._closed = False

    @property
    def node(self):
        with self._lock:
            return self._node

    @property
    def eve(self):
        with self._lock:
            return self._eve

    def snapshot(self):
        with self._lock:
            path = self._psk_path
            try:
                read_psk_file(path)
                ready = True
            except (OSError, ValueError):
                ready = False
            return {"psk_ready": ready, "psk_exists": path.exists() or path.is_symlink(),
                    "psk_path": str(path), "role": self._node.role if self._node else None,
                    "eve_enabled": self._eve is not None, "port": DEFAULT_PORT}

    def _check_available(self):
        if self._closed or self._node is not None:
            raise SetupConflict("Hãy khởi động lại giao diện cấu hình để đổi vai trò hoặc khóa")

    def write_psk(self, value=None):
        with self._lock:
            self._check_available()
            try:
                create_psk_file(self._psk_path, value)
            except FileExistsError:
                raise SetupConflict("Đã có tệp PSK tại vị trí này. Tệp đang dùng được giữ nguyên.") from None

    def start(self, role, host, port, *, eve=False):
        if role not in ("alice", "bob") or type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Chọn vai trò Alice hoặc Bob và cổng TCP từ 1 đến 65535")
        if type(eve) is not bool or (eve and role != "alice"):
            raise ValueError("Chỉ máy Alice có thể chọn chạy kèm Eve")
        if type(host) is not str:
            raise ValueError("Nhập địa chỉ IPv4, ví dụ 192.168.1.20")
        try:
            ip = IPv4Address(host.strip())
        except ValueError:
            raise ValueError("Nhập địa chỉ IPv4, ví dụ 192.168.1.20") from None
        if ip.is_unspecified or ip.is_multicast or ip.is_reserved:
            raise ValueError("Nhập địa chỉ IPv4 cụ thể của thiết bị trong mạng LAN hoặc VPN")
        with self._lock:
            self._check_available()
            try:
                psk = read_psk_file(self._psk_path)
            except (OSError, ValueError):
                raise SetupConflict("Hãy tạo hoặc nhập tệp PSK hợp lệ trước khi bắt đầu") from None

            address = str(ip), port
            target = address if role == "alice" else None
            node = NetworkNode(role, psk, target=target, inbox=self._inbox)
            relay = NetworkNode("eve", target=address) if eve else None
            if eve or role == "bob":
                listener = relay if eve else node
                bind_address = ("127.0.0.1", 0) if eve else address
                try:
                    transport = make_transport_server(listener, *bind_address)
                except OSError:
                    message = ("Eve chưa mở được cổng cục bộ. Hãy thử khởi động lại."
                               if eve else "Bob chưa mở được cổng. Kiểm tra IPv4 thuộc máy này và cổng còn trống.")
                    raise ValueError(message) from None
                try:
                    if eve:
                        node.target = transport.server_address
                    threading.Thread(target=transport.serve_forever, daemon=True).start()
                except RuntimeError:
                    transport.server_close()
                    raise
                self._transport = transport
            self._node = node
            self._eve = relay

    def close(self):
        with self._lock:
            self._closed = True
            self._eve = None
            transport, self._transport = self._transport, None
        if transport is not None:
            try:
                transport.shutdown()
            finally:
                transport.server_close()
