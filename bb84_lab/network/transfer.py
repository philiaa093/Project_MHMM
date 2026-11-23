"""Chunked text/file transfer, integrity checks and atomic receiver publication."""

import hashlib
import json
from pathlib import Path
import re
import secrets
import socket

from bb84_lab.core.secure_channel import AuthenticationError, _json_bytes
from bb84_lab.network.config import CHUNK_BYTES, DEFAULT_MAX_FILE_BYTES, network_config, public_config
from bb84_lab.network.packets import receive_encrypted, send_encrypted
from bb84_lab.network.session import hello_alice, hello_bob, prepare_alice_channel, prepare_bob_channel
from bb84_lab.network.transport import configure_socket


def safe_filename(value):
    if type(value) is not str:
        raise ValueError("Tên tệp không hợp lệ")
    value = value.replace("\\", "/").rsplit("/", 1)[-1]
    value = re.sub(r'[\x00-\x1f\x7f<>:"/\\|?*]', "_", value).strip(" .")
    # Bound the UTF-8 byte length as well as characters for Linux VMs.
    value = value.encode("utf-8")[:140].decode("utf-8", errors="ignore")
    return value or "message.bin"


def _hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
            digest.update(chunk)
    return digest.hexdigest()


def send_transfer(target, psk, path, name=None, kind="file", config=None, event=lambda *a, **k: None,
                  max_bytes=DEFAULT_MAX_FILE_BYTES):
    path = Path(path)
    size = path.stat().st_size
    if size > max_bytes or kind not in ("file", "text") or (kind == "text" and size > 16384):
        raise ValueError("Tệp vượt giới hạn hoặc loại không hợp lệ")
    config = network_config() if config is None else network_config(public_config(config))
    digest = _hash_file(path)
    event("connecting", "Đang kết nối tới đầu nhận/proxy")
    with socket.create_connection(target, timeout=15) as connection:
        configure_socket(connection)
        peer = hello_alice(connection, psk)
        try:
            channel, stats = prepare_alice_channel(peer, config, event)
            if channel is None:
                event("aborted", "Phiên dừng trước mã hóa", **stats)
                return {"state": "aborted", "statistics": stats}
            metadata = {"name": safe_filename(path.name if name is None else name),
                        "size": size, "sha256": digest, "kind": kind}
            send_encrypted(peer, channel, _json_bytes(metadata))
            sent = 0
            with path.open("rb") as handle:
                for chunk in iter(lambda: handle.read(CHUNK_BYTES), b""):
                    send_encrypted(peer, channel, chunk)
                    sent += len(chunk)
                    event("progress", "Đang gửi dữ liệu mã hóa", bytes=sent, total=size)
            send_encrypted(peer, channel, _json_bytes({"kind": "end", "size": sent, "sha256": digest}))
            receipt = peer.receive("receipt")
            if receipt.get("size") != size or receipt.get("sha256") != digest or receipt.get("accepted") is not True:
                raise AuthenticationError("Biên nhận của Bob không khớp")
            event("complete", "Bob đã xác thực và lưu đủ dữ liệu", bytes=size, sha256=digest)
            return {"state": "complete", "size": size, "sha256": digest, "statistics": stats}
        except Exception:
            try:
                peer.send({"kind": "abort"})
            except (OSError, ValueError):
                pass
            raise


def receive_transfer(connection, psk, inbox, event=lambda *a, **k: None,
                     max_bytes=DEFAULT_MAX_FILE_BYTES, noise=0, completed=lambda item: None):
    if type(noise) not in (int, float) or not 0 <= noise <= 1:
        raise ValueError("Nhiễu phải nằm trong [0,1]")
    configure_socket(connection)
    peer = hello_bob(connection, psk)
    temporary = None
    try:
        channel, stats = prepare_bob_channel(peer, event, noise)
        if channel is None:
            event("aborted", "Phiên dừng trước mã hóa", **stats)
            return None
        metadata = json.loads(receive_encrypted(peer, channel))
        size = metadata.get("size")
        digest = metadata.get("sha256")
        if (type(size) is not int or not 0 <= size <= max_bytes or type(digest) is not str
                or not re.fullmatch(r"[0-9a-f]{64}", digest) or metadata.get("kind") not in ("text", "file")
                or (metadata["kind"] == "text" and size > 16384)):
            raise ValueError("Thông tin tệp không hợp lệ hoặc vượt giới hạn")
        name = safe_filename(metadata.get("name"))
        inbox = Path(inbox).resolve()
        inbox.mkdir(parents=True, exist_ok=True)
        transfer_id = secrets.token_hex(16)
        temporary = inbox / f".{transfer_id}.part"
        final = inbox / f"{transfer_id}_{name}"
        measured = hashlib.sha256()
        received = 0
        with temporary.open("xb") as handle:
            while received < size:
                chunk = receive_encrypted(peer, channel)
                if len(chunk) != min(CHUNK_BYTES, size - received):
                    raise AuthenticationError("Sai kích thước hoặc thứ tự khối")
                handle.write(chunk)
                measured.update(chunk)
                received += len(chunk)
                event("progress", "Đang nhận và xác thực từng khối", bytes=received, total=size)
        ending = json.loads(receive_encrypted(peer, channel))
        if ending != {"kind": "end", "size": size, "sha256": digest} or measured.hexdigest() != digest:
            raise AuthenticationError("Tệp thiếu hoặc SHA-256 không khớp")
        text = temporary.read_text(encoding="utf-8") if metadata["kind"] == "text" else None
        temporary.replace(final)
        temporary = None
        item = {"id": transfer_id, "name": name, "size": size, "sha256": digest,
                "kind": metadata["kind"], "path": str(final), "text": text}
        completed(item)
        event("complete", "Đã nhận đủ, xác thực và lưu tệp", bytes=size, sha256=digest)
        peer.send({"kind": "receipt", "accepted": True, "size": size, "sha256": digest})
        return item
    except Exception:
        try:
            peer.send({"kind": "abort"})
        except (OSError, ValueError):
            pass
        raise
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
