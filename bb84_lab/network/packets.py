"""Serialize AEAD packets; cryptographic operations stay in core.secure_channel."""

import base64

from bb84_lab.core.secure_channel import AuthenticationError, Packet
from bb84_lab.network.config import CHUNK_BYTES
from bb84_lab.network.transport import receive_frame, send_frame


def send_encrypted(peer, channel, plaintext):
    packet = channel.encrypt(plaintext)
    send_frame(peer.connection, {"kind": "data", "version": packet.version,
               "session_id": packet.session_id, "sender": packet.sender,
               "sequence": packet.sequence,
               "ciphertext": base64.b64encode(packet.ciphertext).decode("ascii")})


def receive_encrypted(peer, channel):
    frame = receive_frame(peer.connection)
    try:
        if frame.get("kind") != "data":
            raise ValueError("Sai loại gói mã hóa")
        ciphertext = base64.b64decode(frame["ciphertext"], validate=True)
        if len(ciphertext) > CHUNK_BYTES + 16:
            raise ValueError("Gói mã hóa vượt giới hạn")
        packet = Packet(frame["version"], frame["session_id"], frame["sender"],
                        frame["sequence"], ciphertext)
        return channel.decrypt(packet)
    except (KeyError, TypeError, ValueError) as error:
        raise AuthenticationError("Gói bị sửa, phát lại hoặc không hợp lệ") from error
