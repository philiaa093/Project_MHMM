"""Bounded TCP frames and authenticated public discussion for the network demo."""

import json
import socket
import struct

from bb84_lab.core.secure_channel import AuthenticatedTranscript, AuthenticationError, Envelope, _json_bytes


MAX_FRAME_BYTES = 2 * 1024 * 1024
SOCKET_TIMEOUT = 90


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError("Nonfinite JSON number")


def receive_exact(connection, length):
    chunks = bytearray()
    while len(chunks) < length:
        chunk = connection.recv(length - len(chunks))
        if not chunk:
            raise ConnectionError("Kết nối đã đóng trước khi hoàn tất")
        chunks.extend(chunk)
    return bytes(chunks)


def receive_frame(connection):
    length = struct.unpack("!I", receive_exact(connection, 4))[0]
    if not 1 <= length <= MAX_FRAME_BYTES:
        raise ValueError("Frame vượt giới hạn")
    value = json.loads(receive_exact(connection, length).decode("utf-8"),
                       object_pairs_hook=_unique, parse_constant=_invalid_constant)
    if type(value) is not dict:
        raise ValueError("Frame phải là đối tượng JSON")
    return value


def send_frame(connection, value):
    data = _json_bytes(value)
    if not 1 <= len(data) <= MAX_FRAME_BYTES:
        raise ValueError("Frame vượt giới hạn")
    connection.sendall(struct.pack("!I", len(data)) + data)


def configure_socket(connection):
    connection.settimeout(SOCKET_TIMEOUT)
    connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)


class ProtocolMismatch(AuthenticationError):
    """Authenticated peers selected different educational protocols."""


class PublicPeer:
    def __init__(self, connection, psk, session_id, role):
        self.connection = connection
        self.auth = AuthenticatedTranscript(psk, session_id)
        self.role = role
        self.remote = "bob" if role == "alice" else "alice"

    @property
    def session_id(self):
        return self.auth.session_id

    def send(self, payload):
        envelope = self.auth.seal(self.role, payload)
        send_frame(self.connection, {
            "kind": "public", "version": envelope.version,
            "session_id": envelope.session_id, "sender": envelope.sender,
            "sequence": envelope.sequence, "payload": envelope.payload,
            "tag": envelope.tag.hex(),
        })

    def receive(self, kind=None):
        frame = receive_frame(self.connection)
        try:
            if frame.get("kind") != "public" or frame["sender"] != self.remote:
                raise AuthenticationError("Sai vai trò hoặc loại thông điệp")
            envelope = Envelope(frame["version"], frame["session_id"], frame["sender"],
                                frame["sequence"], frame["payload"], bytes.fromhex(frame["tag"]))
            payload = self.auth.receive(envelope)
        except (KeyError, TypeError, ValueError) as error:
            raise AuthenticationError("Xác thực thảo luận công khai thất bại") from error
        if payload.get("kind") == "abort":
            raise AuthenticationError("Đầu bên kia đã hủy phiên")
        if payload.get("kind") == "protocol-mismatch":
            raise ProtocolMismatch("Alice và Bob phải chọn cùng giao thức")
        if kind is not None and payload.get("kind") != kind:
            raise AuthenticationError("Sai bước giao thức")
        return payload
