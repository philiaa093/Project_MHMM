"""Kiểm tra trực tiếp: python -m tests.self_check (không cần test framework)."""

import csv
from dataclasses import replace
import hashlib
from http.client import HTTPConnection
import json
import math
from pathlib import Path
import secrets
import shutil
import sys
import threading

from bb84_lab.bb84 import Config, evaluate, expected_qber, monitor, run_session, simulate, wilson_interval
from bb84_lab.demo import aead_demo, authenticated_session, integrated_session, public_decision
from bb84_lab.education import PacketInspector, lesson_session
from bb84_lab.research.experiments import load_config, run_experiments
from bb84_lab.postprocess import key_budget, pack_bits, postprocess, reconcile, toeplitz_bits
from bb84_lab.secure_channel import AuthenticatedTranscript, AuthenticationError, DemoChannel, check_secure_channel


def rejected(operation, exception=ValueError):
    try:
        operation()
    except exception:
        return
    raise AssertionError("Đầu vào không hợp lệ đã được chấp nhận")


def check_project_structure():
    import importlib

    modules = (
        "bb84_lab.app", "bb84_lab.bb84", "bb84_lab.demo", "bb84_lab.postprocess",
        "bb84_lab.secure_channel", "bb84_lab.research_analysis", "bb84_lab.education",
        "bb84_lab.research.experiments", "bb84_lab.research.study",
        "bb84_lab.research.plot_results", "bb84_lab.research.verify_quantum",
    )
    root = Path(__file__).resolve().parents[1]
    assert not list(root.glob("*.py")), "Mã Python phải nằm trong package hoặc tests"
    for canonical in modules:
        module = importlib.import_module(canonical)
        assert Path(module.__file__).resolve() == root / (canonical.replace(".", "/") + ".py")
    from bb84_lab.app import ROOT, make_server
    assert ROOT == root
    for relative in ("web/index.html", "web/app.js", "web/education.js", "web/styles.css",
                     "configs/smoke.json", "configs/main.json", "configs/study.json",
                     "docs/DEMO.md", "docs/de_cuong_QKD_3_tuan.md"):
        assert (root / relative).is_file(), relative
    assert make_server.__defaults__[1] == root / "outputs" / "study"
    assert not any(name.split(".")[0] in {"matplotlib", "qiskit", "qiskit_aer"}
                   for name in sys.modules)


def check_bb84():
    config = Config()
    transmission = simulate(config)
    result = evaluate(transmission, config)
    assert transmission == simulate(config)
    assert result.qber == 0 and result.status == "continue"
    assert 0.45 * config.signals < result.sifted_count < 0.55 * config.signals
    assert result.sample_count == math.floor(config.sample_fraction * result.sifted_count)
    sample, retained = set(result.sample_indices), set(result.retained_indices)
    assert not sample & retained
    assert sample | retained == set(range(result.sifted_count))
    assert len(sample) == result.sample_count
    assert result.remaining_count == result.sifted_count - result.sample_count
    assert result.y_pre == result.remaining_count
    public = result.public_transcript()
    for index, a, b in zip(result.sample_indices, public["sample_alice_bits"], public["sample_bob_bits"]):
        original = transmission.sifted_indices[index]
        assert a == transmission.alice_bits[original]
        assert b == transmission.bob_bits[original]
    fractions = [evaluate(transmission, replace(config, sample_fraction=alpha)) for alpha in (.1, .25, .5)]
    assert set(fractions[0].sample_indices) <= set(fractions[1].sample_indices) <= set(fractions[2].sample_indices)
    assert "alice_bits" not in repr(transmission) and "_transmission" not in repr(result)
    assert not {"alice_bits", "bob_bits", "key", "psk", "sample_indices"} & result.public_summary().keys()
    for config in (Config(signals=1), Config(sample_fraction=0), Config(signals=100)):
        small = run_session(config)
        assert small.status == "inconclusive" and small.y_pre == 0
        if small.sample_count == 0:
            assert small.qber is None and small.ci_low is None and small.ci_high is None
    all_public = run_session(Config(sample_fraction=1))
    assert all_public.remaining_count == 0 and all_public.y_pre == 0
    assert monitor(0, 99)["status"] == "inconclusive"
    assert monitor(0, 100)["status"] == "continue"
    assert monitor(5, 100)["status"] == "inconclusive"
    assert monitor(25, 100)["status"] == "anomalous"
    low, high = wilson_interval(10, 100)
    assert monitor(10, 100, threshold=high)["status"] == "continue"
    assert monitor(10, 100, threshold=low)["status"] == "inconclusive"
    for change in ({"signals": 0}, {"signals": True}, {"signals": 1.5},
                   {"seed": -1}, {"min_samples": 0}, {"eve_fraction": 1.1},
                   {"noise_probability": -0.1}, {"sample_fraction": float("nan")},
                   {"threshold": float("inf")}, {"sample_fraction": True}):
        rejected(lambda change=change: Config(**change))
    rejected(lambda: monitor(101, 100))
    rejected(lambda: monitor(1, 0))
    rejected(lambda: wilson_interval(0, 0))
    rejected(lambda: evaluate(transmission, replace(result.config, seed=123)))

    for f, p in ((0, 0), (1, 0), (.1, .03), (0, .05), (1, 1)):
        sessions = [run_session(Config(8192, f, p, .5, seed=seed)) for seed in range(12)]
        samples = sum(item.sample_count for item in sessions)
        measured = sum(item.sample_errors for item in sessions) / samples
        expected = expected_qber(f, p)
        tolerance = 5 * math.sqrt(expected * (1 - expected) / samples) + 1 / samples
        assert abs(measured - expected) <= tolerance, (f, p, measured, expected)
    strong = [run_session(Config(eve_fraction=1, seed=seed)) for seed in range(30)]
    assert sum(item.status == "anomalous" for item in strong) / len(strong) >= .95
    assert all(item.y_pre == 0 for item in strong if item.status != "continue")


def check_demo():
    for config in (Config(), Config(eve_fraction=1), Config(signals=1)):
        result = authenticated_session(config)
        assert result["transcript_authenticated"] and not result["bb84_key_released"]
        assert result["status"] == run_session(config).status
    rejected(lambda: authenticated_session(Config(), tamper=True), AuthenticationError)
    config = Config()
    alice = run_session(config).public_transcript()
    bob = {
        "kind": "bb84-bob-sample-v1", "bob_bases": alice.pop("bob_bases"),
        "sample_indices": alice["sample_indices"], "sample_bob_bits": alice.pop("sample_bob_bits"),
    }
    assert public_decision(alice, bob, config)["status"] == "continue"
    rejected(lambda: public_decision({**alice, "threshold": 1}, bob, config), AuthenticationError)
    rejected(lambda: public_decision({**alice, "sample_indices": [-1]}, bob, config), AuthenticationError)
    rejected(lambda: public_decision({**alice, "alice_bases": [True] * config.signals}, bob, config), AuthenticationError)
    result = aead_demo("Kiểm tra UTF-8: tiếng Việt")
    assert result["roundtrip_ok"] and result["tamper_rejected"] and result["replay_rejected"]
    assert "độc lập với BB84" in result["key_source"]
    assert result["implementation"].endswith("ChaCha20Poly1305")
    assert result["key_bytes"] == 32 and result["nonce_bytes"] == 12 and result["tag_bytes"] == 16
    assert result["ciphertext_bytes"] == result["plaintext_bytes"] + result["tag_bytes"]
    assert len(result["aad_sha256"]) == len(result["ciphertext_sha256"]) == 64


def check_education():
    for scenario in ("clean", "eve", "noise", "weak"):
        lesson = lesson_session(scenario, 2026)
        assert lesson == lesson_session(scenario, 2026)
        assert not lesson["key_released"] and not lesson["application_key_material"]
        rows, summary = lesson["signals"], lesson["summary"]
        assert len(rows) == 16 and summary["status"] == "inconclusive"
        assert sum(row["sifted"] for row in rows) == summary["sifted_count"]
        assert sum(row["sampled"] for row in rows) == summary["sample_count"]
        assert sum(row["retained"] for row in rows) == summary["remaining_count"]
        assert sum(row["sampled"] and row["error"] for row in rows) == summary["sample_errors"]
        assert not any(row["retained"] and row["sampled"] for row in rows)
        for row in rows:
            assert sum(row["bob_probabilities"]) == 1
            assert row["bob_bit"] == (row["bob_before_noise"] ^ row["noise_flipped"])
            assert row["sifted"] == (row["alice_basis"] == row["bob_basis"])
        if scenario == "clean":
            assert all(row["alice_bit"] == row["bob_bit"] for row in rows if row["sifted"])
        if scenario == "eve":
            assert all(row["intercepted"] and row["eve_basis"] in (0, 1) for row in rows)
    trace = []
    config = Config(signals=16, eve_fraction=1, noise_probability=.1)
    assert simulate(config, trace=trace) == simulate(config)
    assert len(trace) == 16
    rejected(lambda: simulate(Config(), trace=[]))
    rejected(lambda: lesson_session("invalid"))
    rejected(lambda: lesson_session(seed=True))

    for message in ("Chào Bob!", "", "đ" * 4096, "<img src=x onerror=alert(1)>"):
        inspector = PacketInspector()
        packet = inspector.create(DemoChannel(), message)
        assert packet["plaintext_bytes"] == len(message.encode("utf-8"))
        assert packet["ciphertext_bytes"] == packet["plaintext_bytes"] + 16
        assert len(packet["tag_hex"]) == 32 and len(packet["nonce_hex"]) == 24
        assert len(packet["ciphertext_preview_hex"]) <= 256
        assert "plaintext" not in packet and "key" not in packet
        rejected(lambda: inspector.act(packet["token"], "replay"))
        damaged = inspector.act(packet["token"], "tamper")
        assert damaged["reason"] == "invalid_tag" and not damaged["plaintext_released"]
        assert int(damaged["original_byte"], 16) ^ int(damaged["changed_byte"], 16) == 1
        assert "plaintext" not in damaged
        assert damaged["changed_part"] == ("tag" if not message else "ciphertext")
        recovered = inspector.act(packet["token"], "decrypt")
        assert recovered["plaintext"] == message and recovered["roundtrip_ok"]
        replay = inspector.act(packet["token"], "replay")
        assert replay["reason"] == "replay" and not replay["plaintext_released"]
        assert "plaintext" not in replay
        assert inspector.act(packet["token"], "decrypt")["reason"] == "replay"
        rejected(lambda: inspector.act(packet["token"], "tamper"))
    now = [100.0]
    inspector = PacketInspector(capacity=1, ttl=10, clock=lambda: now[0])
    old = inspector.create(DemoChannel(), "one")
    current = inspector.create(DemoChannel(), "two")
    rejected(lambda: inspector.act(old["token"], "decrypt"), KeyError)
    now[0] += 10
    rejected(lambda: inspector.act(current["token"], "decrypt"), KeyError)
    inspector = PacketInspector()
    packet = inspector.create(DemoChannel(), "two simultaneous deliveries")
    barrier = threading.Barrier(3)
    deliveries = []
    def deliver():
        barrier.wait(timeout=5)
        deliveries.append(inspector.act(packet["token"], "decrypt"))
    threads = [threading.Thread(target=deliver) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait(timeout=5)
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()
    assert sorted(item["status"] for item in deliveries) == ["accepted", "rejected"]
    assert next(item for item in deliveries if item["status"] == "rejected")["reason"] == "replay"


def check_experiments():
    config = load_config(Path(__file__).resolve().parents[1] / "configs" / "smoke.json")
    config.update(signals=[1024], eve_fractions=[0, 1], noise_probabilities=[0], repeats=2)
    scratch_root = Path(__file__).resolve().parents[1] / "outputs"
    scratch_root.mkdir(exist_ok=True)
    directory = scratch_root / f"self-check-{secrets.token_hex(16)}"
    directory.mkdir()
    try:
        runs = []
        for name in ("first", "second"):
            manifest = run_experiments(config, directory / name)
            assert manifest["state"] == "complete"
            assert manifest["independent_sessions"] == 4 and manifest["paired_results"] == 12
            with (directory / name / "sessions.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            assert not {"key", "psk", "alice_bits", "bob_bits", "sample_alice_bits"} & rows[0].keys()
            for row in rows:
                del row["simulation_seconds"], row["evaluation_seconds"]
            runs.append(rows)
            summaries = json.loads((directory / name / "summary.json").read_text(encoding="utf-8"))
            assert len(summaries) == 6
            assert all(sum(item[f"{status}_count"] for status in ("continue", "anomalous", "inconclusive")) == 2 for item in summaries)
        assert runs[0] == runs[1]
        rejected(lambda: run_experiments(config, directory / "first"), FileExistsError)
        assert (directory / "first" / "manifest.json").exists()
        for change in ({"repeats": 0}, {"seed": True}, {"sample_fractions": [0.25, 0.25]},
                       {"signals": [True]}, {"eve_fractions": [float("nan")]}, {"unknown": 1}):
            path = directory / "invalid.json"
            path.write_text(json.dumps({**config, **change}), encoding="utf-8")
            rejected(lambda: load_config(path))
    finally:
        if not directory.resolve().is_relative_to(scratch_root):
            raise ValueError("Thư mục kiểm tra nằm ngoài outputs")
        shutil.rmtree(directory)


def check_study():
    from bb84_lab.research.experiments import summarize as runner_summarize
    from bb84_lab import research_analysis as analysis
    from bb84_lab.research import study

    assert runner_summarize is analysis.summarize is study.summarize
    for name in ("assess_candidates", "select_fraction", "_quantile", "paired_differences",
                 "EVE_FRACTIONS", "COMPARISON_NOISE", "SAMPLE_FRACTIONS", "BASELINE", "CRITERIA"):
        assert getattr(study, name) is getattr(analysis, name)

    scratch_root = Path(__file__).resolve().parents[1] / "outputs"
    scratch_root.mkdir(exist_ok=True)
    directory = scratch_root / f"self-check-study-{secrets.token_hex(16)}"
    directory.mkdir()
    try:
        output = directory / "study"
        summary = study.run_study(output, quick=True, plots=False)
        assert summary["manifest"]["state"] == "complete"
        assert summary["manifest"]["mode"] == "smoke"
        assert summary["manifest"]["independent_sessions"] == 165
        assert summary["selection"]["selected_fraction"] == study.BASELINE
        assert summary["figures"] == []
        rejected(lambda: study.run_study(output, quick=True, plots=False), FileExistsError)

        sources, rows = {}, {}
        for name, count in (("main", 120), ("calibration", 90), ("evaluation", 135)):
            path = output / f"{name}.csv"
            sources[name] = path.read_bytes()
            with path.open(encoding="utf-8", newline="") as handle:
                rows[name] = list(csv.DictReader(handle))
            assert len(rows[name]) == count
        assert not {row["seed"] for row in rows["main"]} & {row["seed"] for row in rows["evaluation"]}
        assert {row["session_id"] for row in rows["calibration"]} <= {row["session_id"] for row in rows["main"]}
        for session_id in {row["session_id"] for row in rows["evaluation"]}:
            pair = [row for row in rows["evaluation"] if row["session_id"] == session_id]
            assert len(pair) == 3 and len({row["seed"] for row in pair}) == 1
            assert {float(row["sample_fraction"]) for row in pair} == set(study.SAMPLE_FRACTIONS)

        selection_path = output / "selection.json"
        selection_bytes = selection_path.read_bytes()
        assert hashlib.sha256(selection_bytes).hexdigest() == summary["manifest"]["selection_sha256"]
        selection_path.write_bytes(selection_bytes + b"\n")
        rejected(lambda: study.append_postprocessing(output))
        assert not (output / "postprocessing_manifest.json").exists()
        selection_path.write_bytes(selection_bytes)
        progress = study.append_postprocessing(output)
        assert progress["state"] == "complete" and progress["rows"] == 165
        assert progress["independent_sessions_added"] == 0
        assert selection_path.read_bytes() == selection_bytes
        for name, content in sources.items():
            assert (output / f"{name}.csv").read_bytes() == content
        with (output / "postprocessing.csv").open(encoding="utf-8", newline="") as handle:
            processed = list(csv.DictReader(handle))
        assert len(processed) == progress["rows"]
        assert sum(row["postprocess_status"] == "ready" for row in processed) == progress["ready_sessions"]
        for row in processed:
            if row["postprocess_status"] == "ready":
                assert row["key_match"] == row["roundtrip_ok"] == "True"
                assert int(row["y_final"]) == int(row["output_bits"]) >= 256
            else:
                assert int(row["y_final"]) == int(row["output_bits"]) == 0
        rejected(lambda: study.append_postprocessing(output), FileExistsError)
    finally:
        if not directory.resolve().is_relative_to(scratch_root):
            raise ValueError("Thư mục kiểm tra nằm ngoài outputs")
        shutil.rmtree(directory)


def check_postprocessing():
    import random
    rng = random.Random(2026)
    for n, m in ((1, 1), (3, 5), (5, 3), (17, 9)):
        bits = tuple(rng.getrandbits(1) for _ in range(n))
        seed = tuple(rng.getrandbits(1) for _ in range(n + m - 1))
        reference = tuple(sum(bits[column] * seed[n - 1 + row - column]
                              for column in range(n)) % 2 for row in range(m))
        assert toeplitz_bits(bits, seed, m) == reference
        assert toeplitz_bits((0,) * n, seed, m) == (0,) * m
    assert pack_bits((1, 0, 1)) == b"\xa0"
    assert key_budget(1024, 0, 0) == (1024, 696)
    assert key_budget(1024, .5, 0) == (0, 0)
    rejected(lambda: toeplitz_bits((1, 0), (0,), 1))
    rejected(lambda: key_budget(1024, float("nan"), 0))

    def auth_pair():
        psk = secrets.token_bytes(32)
        return AuthenticatedTranscript(psk, "postprocess-check"), AuthenticatedTranscript(psk, "postprocess-check")

    for error_positions in ((1,), (1, 3), (0, 1, 2), (3, 5, 15, 24)):
        a, b = auth_pair()
        def exchange(sender, payload):
            source, target = (a, b) if sender == "alice" else (b, a)
            return target.receive(source.seal(sender, payload))
        alice_bits = tuple(rng.getrandbits(1) for _ in range(128))
        bob_bits = list(alice_bits)
        for index in error_positions:
            bob_bits[index] ^= 1
        corrected, leak, corrections = reconcile(alice_bits, bob_bits, .1, exchange, seed=2026)
        assert corrected == alice_bits and corrections == len(error_positions)
        assert leak > 0 and leak % 2 == 0

    config = Config()
    transmission = simulate(config)
    evaluation = evaluate(transmission, config)
    decision = monitor(evaluation.sample_errors, evaluation.sample_count)
    a, b = auth_pair()
    ready = postprocess(transmission, evaluation, decision, a, b)
    assert ready.status == "ready" and ready.key_match and ready.output_bits >= 256
    assert ready._alice_key == ready._bob_key and len(ready._alice_key) == 32
    assert "_alice_key" not in repr(ready) and "_alice_key" not in ready.public_summary()
    assert ready.confirmation_leak_bits == 257 and ready.parity_leak_bits % 2 == 0
    rejected(lambda: DemoChannel.from_simulated_keys(bytes(32), bytes([1]) * 32), AuthenticationError)
    rejected(lambda: DemoChannel.from_simulated_keys(b"short", b"short"))
    first = DemoChannel.from_simulated_keys(ready._alice_key, ready._bob_key)
    second = DemoChannel.from_simulated_keys(ready._alice_key, ready._bob_key)
    assert first.session_id != second.session_id
    packet = first.encrypt(b"model")
    rejected(lambda: second.decrypt(replace(packet, session_id=second.session_id)), AuthenticationError)
    assert first.decrypt(packet) == b"model"

    a, b = auth_pair()
    rejected(lambda: postprocess(transmission, evaluation, decision, a, b, tamper_parity=True), AuthenticationError)
    broken_bits = list(transmission.bob_bits)
    for retained_index in evaluation.retained_indices[:2]:
        broken_bits[transmission.sifted_indices[retained_index]] ^= 1
    broken_transmission = replace(transmission, bob_bits=tuple(broken_bits))
    broken_evaluation = evaluate(broken_transmission, config)
    a, b = auth_pair()
    failed = postprocess(broken_transmission, broken_evaluation, decision, a, b, reconciliation_passes=1)
    assert failed.status == "failed" and failed._alice_key is None and failed.output_bits == 0
    a, b = auth_pair()
    original_seal = a.seal
    def corrupt_seed(sender, payload):
        envelope = original_seal(sender, payload)
        if payload["kind"] == "toeplitz-seed-v1":
            envelope = replace(envelope, payload={**payload, "seed": "00"})
        return envelope
    a.seal = corrupt_seed
    rejected(lambda: postprocess(transmission, evaluation, decision, a, b), AuthenticationError)
    for config in (Config(), Config(signals=1024), Config(eve_fraction=1), Config(signals=16),
                   Config(noise_probability=1, threshold=1)):
        result = integrated_session(config)
        ready = result["postprocessing"]["status"] == "ready"
        verification = result["verification"]
        unsigned = {key: value for key, value in verification.items() if key != "sha256"}
        canonical = json.dumps(unsigned, ensure_ascii=False, sort_keys=True,
                               separators=(",", ":")).encode("utf-8")
        assert hashlib.sha256(canonical).hexdigest() == verification["sha256"]
        assert verification["public_only"] and verification["session_id"] == result["session_id"]
        codes = {entry["code"] for entry in verification["entries"]}
        assert {"BB84-01", "BB84-02", "BB84-03", "BB84-04", "POST-01", "POST-02"} <= codes
        public_keys, pending = set(), [verification]
        while pending:
            item = pending.pop()
            if isinstance(item, dict):
                public_keys.update(item)
                pending.extend(item.values())
            elif isinstance(item, list):
                pending.extend(item)
        assert not {"alice_bits", "bob_bits", "sample_alice_bits", "_alice_key", "_bob_key", "psk", "key"} & public_keys
        assert result["bb84_key_released"] == ready
        if ready:
            assert result["postprocessing"]["key_match"] and result["encryption"]["roundtrip_ok"]
            assert {"AEAD-01", "AEAD-02"} <= codes
        else:
            assert result["encryption"] is None and result["postprocessing"]["output_bits"] == 0
            assert "AEAD-00" in codes
        if result["postprocessing"]["confirmation_leak_bits"]:
            assert result["postprocessing"]["key_match"] or result["postprocessing"]["status"] == "failed"


def check_http():
    from bb84_lab.app import make_server
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
        for url, filename in (("/app.js", "app.js"), ("/education.js", "education.js"), ("/styles.css", "styles.css")):
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


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    if not __debug__:
        raise SystemExit("Chạy python -m tests.self_check; không dùng -O vì sẽ tắt assert.")
    check_project_structure()
    check_bb84()
    check_secure_channel()
    check_demo()
    check_education()
    check_experiments()
    check_postprocessing()
    from bb84_lab.research.study import check_research
    check_research()
    check_study()
    check_http()
    print("PASS: BB84/QBER, Cascade/Toeplitz, xác thực, AEAD/nonce/replay, HTTP và nghiên cứu tái lập.")
    print("Khóa từ seed công khai chỉ dùng minh họa; không bảo vệ dữ liệu thật.")
