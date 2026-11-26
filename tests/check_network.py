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


def http(ui, path, body=None, headers=None):
    connection = HTTPConnection("127.0.0.1", ui.server_address[1], timeout=20)
    try:
        connection.request("GET" if body is None else "POST", path, body, headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def read_trace_page(ui, session_id, stage, offset):
    status, _, body = http(ui, f"/api/key-trace/{session_id}/{stage}/{offset}")
    assert status == 200
    page = json.loads(body)
    assert set(page) == {"session_id", "stage", "offset", "page_size", "recorded", "omitted", "steps"}
    assert (page["session_id"], page["stage"], page["offset"], page["page_size"]) == (session_id, stage, offset, 100)
    assert len(page["steps"]) == min(page["page_size"], max(0, page["recorded"] - offset))
    assert all(set(step) == {"time", "stage", "title", "detail", "status"} for step in page["steps"])
    assert all(step["stage"] == stage for step in page["steps"])
    return page


def check_browser_setup(root, idle):
    import socket
    from bb84_lab.network.config import network_config
    from bb84_lab.network.setup import NetworkSetup
    from bb84_lab.network.transport import receive_frame
    from bb84_lab.network.ui import make_ui_server

    bob_key = root / "bob.key"
    alice_key = root / "alice.key"
    bob = NetworkSetup(bob_key, root / "setup-inbox")
    alice = NetworkSetup(alice_key)
    bob_ui, alice_ui = [make_ui_server(port=0, launcher=launcher) for launcher in (bob, alice)]
    servers = bob_ui, alice_ui
    for server in servers:
        threading.Thread(target=server.serve_forever, daemon=True).start()

    def post(ui, route, data, origin=None):
        headers = {"Content-Type": "application/json"}
        if origin:
            headers["Origin"] = origin
        return http(ui, route, json.dumps(data).encode("utf-8"), headers)

    start = "/api/setup/start"
    create = "/api/setup/psk"
    load = "/api/setup/psk-import"
    eve_state = "/api/eve/state"
    eve_attack = "/api/eve/attack"
    intercept = {"mode": "intercept", "fraction": 1}
    binary = {"Content-Type": "application/octet-stream"}
    try:
        assert b"setup.js" in http(bob_ui, "/")[2]
        assert http(bob_ui, "/api/state")[0] == 409
        for page in ("/setup", "/setup.js", "/setup.css", "/key-lesson", "/key-lesson.js", "/key-lesson.css"):
            assert http(bob_ui, page)[0] == 200, page
        assert post(bob_ui, create, {}, "https://evil.example")[0] == 403
        assert http(bob_ui, create, b"{}", {"Host": "evil.example", "Content-Type": "application/json"})[0] == 403
        assert not bob_key.exists()

        invalid_address = {"role": "bob", "host": "0.0.0.0", "port": 9100}
        assert post(bob_ui, start, invalid_address)[0] == 400
        assert post(bob_ui, start, {**invalid_address, "host": "127.0.0.1", "port": True})[0] == 400
        assert post(bob_ui, start, {**invalid_address, "host": "127.0.0.1"})[0] == 409

        status, _, response = post(bob_ui, create, {})
        secret = bob_key.read_bytes()
        assert status == 200 and len(secret) == 32
        assert json.loads(response)["psk_ready"] and secret.hex().encode() not in response
        assert post(bob_ui, create, {})[0] == 409 and bob_key.read_bytes() == secret
        assert http(alice_ui, load, secret[:-1], binary)[0] == 400 and not alice_key.exists()
        assert http(alice_ui, load, secret, {**binary, "Origin": "https://evil.example"})[0] == 403
        assert http(alice_ui, load, secret, binary)[0] == 200 and alice_key.read_bytes() == secret
        assert http(alice_ui, load, bytes(32), binary)[0] == 409 and alice_key.read_bytes() == secret

        with socket.socket() as occupied:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
                occupied.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            role_params = {"role": "bob", "host": "127.0.0.1", "port": occupied.getsockname()[1]}
            assert post(bob_ui, start, role_params)[0] == 400
            assert json.loads(http(bob_ui, "/api/setup")[2])["role"] is None
        assert post(bob_ui, start, {**role_params, "eve": True})[0] == 400
        assert post(bob_ui, start, role_params)[0] == 200
        assert post(bob_ui, start, {**role_params, "role": "alice"})[0] == 409
        assert not json.loads(http(bob_ui, "/api/setup")[2])["eve_enabled"]
        for server in servers:
            assert http(server, "/eve")[0] == http(server, eve_state)[0] == 404
            assert post(server, eve_attack, intercept)[0] == 404
        alice_params = {**role_params, "role": "alice"}
        assert post(alice_ui, start, {**alice_params, "eve": "true"})[0] == 400
        status, _, response = post(alice_ui, start, {**alice_params, "eve": True})
        assert status == 200 and json.loads(response)["eve_enabled"]
        assert json.loads(http(alice_ui, "/api/setup")[2])["eve_enabled"]
        assert b"setup-link" in http(alice_ui, "/")[2]
        assert http(alice_ui, "/eve")[0] == 200
        status, _, response = http(alice_ui, eve_state)
        eve = json.loads(response)
        assert status == 200 and eve["role"] == "eve" and eve["mode"] == "pass"
        assert eve["listen"][0] == "127.0.0.1" and eve["listen"][1] != role_params["port"]
        assert eve["target"] == ["127.0.0.1", role_params["port"]]
        assert "key_trace" not in eve and secret.hex().encode() not in response
        assert post(alice_ui, eve_attack, intercept, "https://evil.example")[0] == 403
        for server in servers:
            assert json.loads(http(server, "/api/state")[2])["key_trace"]["steps"] == []

        message = "Khóa phiên từ hai trình khởi chạy"
        assert post(alice_ui, "/api/send-text", {"message": message})[0] == 202
        idle(alice.node)
        idle(bob.node)
        idle(alice.eve)
        status, _, state = http(bob_ui, "/api/state")
        snapshot = json.loads(state)
        assert status == 200 and snapshot["setup_available"]
        assert snapshot["state"] == "complete" and snapshot["received"][-1]["text"] == message

        alice_snapshot = json.loads(http(alice_ui, "/api/state")[2])
        assert alice_snapshot["role"] == "alice" and alice_snapshot["eve_available"]
        assert alice_snapshot["target"] == eve["listen"]
        assert json.loads(http(alice_ui, eve_state)[2])["state"] == "complete"
        session_id = snapshot["statistics"]["session_id"]
        data_hash = snapshot["received"][-1]["sha256"]
        private_values = message, data_hash, secret.hex()
        for ui, current in ((bob_ui, snapshot), (alice_ui, alice_snapshot)):
            trace = current["key_trace"]
            stats = current["statistics"]
            assert trace["session_id"] == current["statistics"]["session_id"] == session_id
            assert set(trace) == {"session_id", "steps", "details"}
            assert {step["stage"] for step in trace["steps"]} == {"auth", "bb84", "cascade", "toeplitz", "transfer"}
            assert all(set(step) == {"time", "stage", "title", "detail", "status"} for step in trace["steps"])
            assert all(step["status"] in {"info", "ok"} for step in trace["steps"])
            serialized = json.dumps(trace, ensure_ascii=False)
            assert not any(value in serialized for value in private_values)
            minimum_records = {
                "bb84": stats["config"]["signals"],
                "cascade": stats["parity_leak_bits"] // 2,
                "toeplitz": stats["output_bits"],
            }
            assert trace["details"].keys() == minimum_records.keys()
            for stage, count in minimum_records.items():
                meta = trace["details"][stage]
                assert meta["recorded"] >= count and meta["omitted"] == 0
                first_page = read_trace_page(ui, session_id, stage, 0)
                assert all(first_page[key] == value for key, value in meta.items())
                assert all(step["status"] in {"info", "ok"} for step in first_page["steps"])
                assert not any(value in json.dumps(first_page, ensure_ascii=False) for value in private_values)

                if stage == "bb84":
                    later_page = read_trace_page(ui, session_id, stage, first_page["page_size"])
                    first_rows = {(step["title"], step["detail"]) for step in first_page["steps"]}
                    assert all((step["title"], step["detail"]) not in first_rows for step in later_page["steps"])
                    assert first_page["steps"][-1]["time"] <= later_page["steps"][0]["time"]
                    sample_offset = stats["config"]["signals"] + 1
                    sample_page = read_trace_page(ui, session_id, stage, sample_offset)
                    assert sample_page["steps"][0]["title"].startswith("Mẫu 1 · tín hiệu ")
                    assert "Bit công khai" in sample_page["steps"][0]["detail"]
                    qber_page = read_trace_page(ui, session_id, stage, sample_offset + stats["sample_count"])
                    assert [row["title"] for row in qber_page["steps"]] == ["QBER và khoảng Wilson", "Quyết định QBER"]
                if stage == "toeplitz":
                    rows = first_page["steps"]
                    seed = "".join(row["detail"] for row in rows if row["title"].startswith("Seed công khai "))
                    size = stats["retained_bits"]
                    assert len(seed) == size + stats["output_bits"] - 1
                    coefficients = seed[:size][::-1]
                    first_row = next(row for row in rows if row["title"] == "Hàng Toeplitz 1")
                    assert f"24 hệ số đầu {coefficients[:24]}" in first_row["detail"]
                    assert f"có {coefficients.count('1')} hệ số bằng 1" in first_row["detail"]
            assert http(ui, f"/api/key-trace/{session_id}/auth/0")[0] == 404
            assert http(ui, f"/api/key-trace/{session_id}/bb84/-1")[0] == 404
        bob_steps = snapshot["key_trace"]["steps"]
        assert [step["title"] for step in bob_steps if step["title"].startswith("Cascade lượt ")] == [
            f"Cascade lượt {number}" for number in range(1, 5)
        ]
        with socket.create_connection(("127.0.0.1", role_params["port"]), timeout=5) as probe:
            assert receive_frame(probe)["kind"] == "challenge"
        idle(bob.node)
        assert json.loads(http(bob_ui, "/api/state")[2])["key_trace"] == snapshot["key_trace"]

        # A new, deliberately undersampled run replaces the previous completed trace.
        alice_ui.config = network_config({"signals": 16})
        assert post(alice_ui, "/api/send-text", {"message": message})[0] == 202
        idle(alice.node)
        idle(bob.node)
        idle(alice.eve)
        aborted_bob = json.loads(http(bob_ui, "/api/state")[2])
        aborted_alice = json.loads(http(alice_ui, "/api/state")[2])
        new_id = aborted_bob["statistics"]["session_id"]
        assert new_id != session_id
        for ui, current in ((bob_ui, aborted_bob), (alice_ui, aborted_alice)):
            trace = current["key_trace"]
            assert current["state"] == "aborted" and trace["session_id"] == new_id
            assert {step["stage"] for step in trace["steps"]}.isdisjoint({"cascade", "toeplitz"})
            assert any(step["stage"] == "bb84" and step["status"] == "stopped" for step in trace["steps"])
            assert http(ui, f"/api/key-trace/{session_id}/bb84/0")[0] == 409
            assert read_trace_page(ui, new_id, "cascade", 0)["steps"] == []
            assert read_trace_page(ui, new_id, "toeplitz", 0)["steps"] == []
        assert len(aborted_bob["received"]) == 1

        # Change the embedded proxy from its dashboard and observe a real rejection.
        alice_ui.config = network_config()
        assert post(alice_ui, eve_attack, intercept)[0] == 200
        assert post(alice_ui, "/api/send-text", {"message": "Phải dừng tại QBER"})[0] == 202
        idle(alice.node)
        idle(bob.node)
        idle(alice.eve)
        intercepted_bob = json.loads(http(bob_ui, "/api/state")[2])
        intercepted_eve = json.loads(http(alice_ui, eve_state)[2])
        assert intercepted_bob["state"] == "aborted" and len(intercepted_bob["received"]) == 1
        assert intercepted_eve["mode"] == "intercept" and intercepted_eve["state"] == "aborted"
        assert intercepted_bob["statistics"]["status"] == intercepted_eve["statistics"]["status"] == "anomalous"
        assert any(event["code"] == "attack" for event in intercepted_eve["events"])
    finally:
        for server in servers:
            server.shutdown()
            server.server_close()
        bob.close()
        alice.close()


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
        assert "key_trace" not in eve.snapshot()
        proxy = make_transport_server(eve)
        bob_ui = make_ui_server(bob, 0)
        alice = NetworkNode("alice", psk, target=proxy.server_address, max_bytes=CHUNK_BYTES * 4)
        alice_ui = make_ui_server(alice, 0)
        servers = (server, proxy, bob_ui, alice_ui)
        threads = [threading.Thread(target=s.serve_forever, daemon=True) for s in servers]
        for thread in threads:
            thread.start()

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
            auth_failure = bob.snapshot()["key_trace"]["steps"]
            assert auth_failure[-1]["stage"] == "auth" and auth_failure[-1]["status"] == "error"
            assert all(step["stage"] == "auth" for step in auth_failure)
            for signals in (16, 1024):
                result = send_transfer(target, psk, source, config=network_config({"signals": signals}))
                idle(bob)
                assert result["state"] == "aborted"
                if result["statistics"]["status"] == "insufficient_key":
                    toeplitz = [step for step in bob.snapshot()["key_trace"]["steps"] if step["stage"] == "toeplitz"]
                    assert len(toeplitz) == 1 and toeplitz[0]["status"] == "stopped"
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
        check_browser_setup(root, idle)

    for raw in (struct.pack("!I", MAX_FRAME_BYTES + 1),
                struct.pack("!I", 13) + b'{"x":1,"x":2}'):
        left, right = socket.socketpair()
        with left, right:
            left.sendall(raw)
            rejected(lambda: receive_frame(right))
