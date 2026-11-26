"""Assert-based local_http checks, run through tests.self_check."""

from http.client import HTTPConnection
import json
from pathlib import Path
import threading


def check_http():
    from bb84_lab.local.server import make_server
    from bb84_lab.core.e91 import simulate_e91
    server = make_server(0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    port = server.server_address[1]
    def request(path, payload=None, headers=None, raw=None):
        connection = HTTPConnection("127.0.0.1", port, timeout=20)
        try:
            body = raw if raw is not None else json.dumps(payload).encode() if payload is not None else None
            actual_headers = {"Content-Type": "application/json", **(headers or {})}
            connection.request("POST" if body is not None else "GET", path, body, actual_headers)
            response = connection.getresponse()
            data = response.read()
            assert "script-src 'self'" in response.getheader("Content-Security-Policy")
            assert response.getheader("Access-Control-Allow-Origin") is None
            return response.status, data
        finally:
            connection.close()
    try:
        assert request("/api/health")[0] == 200
        status, body = request("/")
        assert status == 200
        assert b'class="card crypto-stack"' in body and b'class="alternatives-table"' in body
        assert b'id="verification-title"' in body and b'id="download-verification"' in body
        assert b'data-view="e91"' in body
        for url, filename in (("/app.js", "simulation/app.js"), ("/education.js", "simulation/education.js"),
                              ("/e91.js", "simulation/e91.js"), ("/e91.css", "simulation/e91.css"),
                              ("/shared/styles.css", "shared/styles.css")):
            status, body = request(url)
            assert status == 200
            assert body == (Path(__file__).resolve().parents[1] / "web" / filename).read_bytes()
        status, body = request("/api/session", {})
        session = json.loads(body)
        assert status == 200 and session["encryption"]["roundtrip_ok"]
        assert session["verification"]["version"] == "bb84-lab-verification-v1"
        assert request("/api/session", {"eve_fraction": 1})[0] == 200
        status, body = request("/api/session", {"tamper_transcript": True})
        assert status == 422 and "postprocessing" not in json.loads(body)
        assert request("/api/session", {"signals": 65537})[0] == 400
        assert request("/api/session", {"signals": True})[0] == 400
        assert request("/api/aead", {"message": "x" * 16385})[0] == 400
        assert request("/api/session", raw=b'{"seed":1,"seed":2}')[0] == 400
        assert request("/api/session", raw=b'{"eve_fraction":NaN}')[0] == 400
        assert request("/api/aead", {"message": "UTF-8"})[0] == 200
        status, body = request("/api/lesson", {"scenario": "eve", "seed": 2026})
        lesson = json.loads(body)
        assert status == 200 and len(lesson["signals"]) == 16 and not lesson["key_released"]
        assert request("/api/lesson", {"signals": 4096})[0] == 400
        assert request("/api/lesson", {"seed": True})[0] == 400
        for probability in (0, 0.5):
            config = {"signals": 4096, "seed": 2026, "noise_probability": probability}
            status, body = request("/api/e91/simulate", config)
            assert status == 200 and json.loads(body) == simulate_e91(**config)
        for invalid in ({"eve_fraction": 1}, {"seed": True}, {"noise_probability": -0.1}, {"signals": 65537}):
            assert request("/api/e91/simulate", invalid)[0] == 400
        assert request("/api/e91/simulate", raw=b'{"noise_probability":NaN}')[0] == 400
        status, body = request("/api/packet", {"message": "Chào Bob!"})
        packet = json.loads(body)
        assert status == 200 and packet["postprocessing"]["status"] == "ready"
        token = packet["packet"]["token"]
        assert packet["packet"]["ciphertext_bytes"] == 26
        assert "plaintext" not in packet["packet"]
        status, body = request("/api/packet/action", {"token": token, "action": "tamper"})
        assert status == 200 and json.loads(body)["reason"] == "invalid_tag"
        status, body = request("/api/packet/action", {"token": token, "action": "decrypt"})
        assert status == 200 and json.loads(body)["plaintext"] == "Chào Bob!"
        status, body = request("/api/packet/action", {"token": token, "action": "replay"})
        assert status == 200 and "plaintext" not in json.loads(body)
        for config in ({"eve_fraction": 1}, {"signals": 16}, {"signals": 1024}):
            status, body = request("/api/packet", config)
            assert status == 200 and json.loads(body)["packet"] is None
        assert request("/api/packet", {"tamper_transcript": True})[0] == 422
        assert request("/api/packet", {"message": "x" * 16385})[0] == 400
        assert request("/api/packet/action", {"token": "x" * 43, "action": "decrypt"})[0] == 404
        assert request("/api/packet/action", {"token": token, "action": "unknown"})[0] == 400
        assert request("/api/health", headers={"Host": "evil.example"})[0] == 403
        assert request("/api/session", {}, {"Origin": "https://evil.example"})[0] == 403
        assert request("/results/../requirements.txt")[0] == 404
        assert request("/AGENTS.md")[0] == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
