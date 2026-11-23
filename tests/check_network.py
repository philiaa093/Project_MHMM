"""Assert-based network checks, run through tests.self_check."""

import hashlib
from http.client import HTTPConnection
import json
from pathlib import Path
import secrets
import shutil
import threading
from bb84_lab.core.secure_channel import AuthenticationError, DemoChannel
from tests.support import rejected


def check_network():
    """Real loopback sockets, independent endpoints and a PSK-free Eve proxy."""
    import socket
    import struct
    from contextlib import contextmanager
    import time
    from bb84_lab.network.config import CHUNK_BYTES, network_config
    from bb84_lab.network.transfer import safe_filename, send_transfer
    from bb84_lab.network.service import NetworkNode, make_transport_server
    from bb84_lab.network.transport import MAX_FRAME_BYTES, receive_frame
    from bb84_lab.network.ui import make_ui_server

    def idle(node):
        deadline = time.monotonic() + 10
        while node.busy.locked() and time.monotonic() < deadline:
            threading.Event().wait(.01)
        assert not node.busy.locked(), "Phiên TCP không giải phóng trạng thái bận"

    @contextmanager
    def scratch_folder():
        parent = Path(__file__).resolve().parents[1] / "outputs"
        parent.mkdir(exist_ok=True)
        scratch = parent / f"self-check-network-{secrets.token_hex(16)}"
        scratch.mkdir()
        try:
            yield scratch
        finally:
            assert scratch.resolve().is_relative_to(parent.resolve())
            shutil.rmtree(scratch)

    with scratch_folder() as folder:
        root = Path(folder)
        psk = secrets.token_bytes(32)
        bob = NetworkNode("bob", psk, inbox=root / "received", max_bytes=CHUNK_BYTES * 4)
        server = make_transport_server(bob)
        target = server.server_address
        eve = NetworkNode("eve", target=target)
        proxy = make_transport_server(eve)
        bob_ui = make_ui_server(bob, 0)
        alice = NetworkNode("alice", psk, target=proxy.server_address, max_bytes=CHUNK_BYTES * 4)
        alice_ui = make_ui_server(alice, 0)
        servers = (server, proxy, bob_ui, alice_ui)
        threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
        for thread in threads:
            thread.start()

        def http(ui, path, body=None, headers=None):
            connection = HTTPConnection("127.0.0.1", ui.server_address[1], timeout=20)
            try:
                connection.request("GET" if body is None else "POST", path, body, headers or {})
                response = connection.getresponse()
                return response.status, dict(response.getheaders()), response.read()
            finally:
                connection.close()

        source = root / "source.bin"
        binary = secrets.token_bytes(CHUNK_BYTES * 2 + 17)
        source.write_bytes(binary)
        try:
            result = send_transfer(target, psk, source, "ảnh thử nghiệm.png")
            idle(bob)
            assert result["state"] == "complete"
            assert result["statistics"]["sample_errors"] == 0
            assert result["statistics"]["output_bits"] >= 256
            assert (bob.snapshot()["statistics"]["sifted_bits"]
                    == result["statistics"]["sample_count"] + result["statistics"]["retained_bits"])
            item = bob._received[-1]
            assert Path(item["path"]).read_bytes() == binary
            assert item["sha256"] == hashlib.sha256(binary).hexdigest()
            received_id = item["id"]
            status, headers, data = http(bob_ui, f"/api/download/{received_id}", headers={"Range": "bytes=3-22"})
            assert status == 206 and data == binary[3:23]
            assert headers["Content-Range"] == f"bytes 3-22/{len(binary)}"
            assert http(bob_ui, f"/api/download/{received_id}", headers={"Range": "bytes=9999999-"})[0] == 416
            assert http(bob_ui, f"/api/download/{received_id}", headers={"Range": "bytes=-0"})[0] == 416
            assert http(bob_ui, "/api/download/" + "0" * 32)[0] == 404
            for url in ("/", "/app.js", "/shared/styles.css", "/styles.css", "/api/state"):
                assert http(bob_ui, url)[0] == 200
            assert http(bob_ui, "/api/state", headers={"Host": "evil.example"})[0] == 403

            for contents, kind, name in ((b"", "file", "empty.bin"),
                                         ("Chào Bob! <script>alert(1)</script>".encode(), "text", "message.txt")):
                source.write_bytes(contents)
                assert send_transfer(proxy.server_address, psk, source, name, kind)["state"] == "complete"
                idle(bob)
                idle(eve)
                assert Path(bob._received[-1]["path"]).read_bytes() == contents
                if kind == "text":
                    assert bob.snapshot()["received"][-1]["text"] == contents.decode()

            source.write_bytes(binary)
            for mode in ("intercept", "tamper", "replay", "drop", "tamper-public"):
                eve.set_attack(mode, 1)
                before = set((root / "received").iterdir())
                if mode == "intercept":
                    result = send_transfer(proxy.server_address, psk, source)
                    assert result["state"] == "aborted"
                    assert result["statistics"]["status"] == "anomalous"
                else:
                    rejected(lambda: send_transfer(proxy.server_address, psk, source), (ValueError, OSError))
                idle(bob)
                idle(eve)
                assert set((root / "received").iterdir()) == before, mode
                assert not list((root / "received").glob("*.part"))

            eve.set_attack("pass", 1)
            before = set((root / "received").iterdir())
            rejected(lambda: send_transfer(target, secrets.token_bytes(32), source), (ValueError, OSError))
            idle(bob)
            for signals in (16, 1024):
                result = send_transfer(target, psk, source, config=network_config({"signals": signals}))
                idle(bob)
                assert result["state"] == "aborted"
            assert set((root / "received").iterdir()) == before
            rejected(lambda: send_transfer(target, psk, source, max_bytes=1))
            rejected(lambda: network_config({"signals": 65537}))
            rejected(lambda: network_config({"eve_fraction": 1}))
            assert safe_filename("../../a:b.mp4") == "a_b.mp4"
            assert len(safe_filename("đ" * 200).encode()) <= 140

            # Exercise the actual local raw upload and background worker.
            contents = bytes(range(256)) * 9
            status, _, body = http(alice_ui, "/api/upload", contents,
                                    {"Content-Type": "application/octet-stream", "X-Filename": "clip.mp4"})
            assert status == 202 and json.loads(body)["accepted"]
            idle(alice)
            idle(bob)
            idle(eve)
            assert alice.snapshot()["state"] == "complete"
            assert Path(bob._received[-1]["path"]).read_bytes() == contents
            assert http(alice_ui, "/api/send-text", b'{"message":"hello"}',
                        {"Content-Type": "application/json", "Origin": "https://evil.example"})[0] == 403
            snapshot = json.dumps(bob.snapshot())
            assert psk.hex() not in snapshot
            assert not {"psk", "alice_bits", "bob_bits", "key", "sample_alice_bits"} & bob.snapshot().keys()

            # Fresh endpoint keys derive the same channel; counters reject replay.
            key = secrets.token_bytes(32)
            sender = DemoChannel.from_local_model_key(key, "network-test")
            receiver = DemoChannel.from_local_model_key(key, "network-test")
            packets = [sender.encrypt(b"chunk") for _ in range(4)]
            assert len({p.sequence for p in packets}) == 4
            for packet in packets:
                assert receiver.decrypt(packet) == b"chunk"
            rejected(lambda: receiver.decrypt(packets[-1]), AuthenticationError)
        finally:
            for running in servers:
                running.shutdown()
                running.server_close()
            for thread in threads:
                thread.join(timeout=5)

    for raw in (struct.pack("!I", MAX_FRAME_BYTES + 1),
                struct.pack("!I", 13) + b'{"x":1,"x":2}'):
        left, right = socket.socketpair()
        with left, right:
            left.sendall(raw)
            rejected(lambda: receive_frame(right))
