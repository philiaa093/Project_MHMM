"""Assert-based simulation checks, run through tests.self_check."""

import threading
from bb84_lab.core.bb84 import Config, run_session, simulate
from bb84_lab.simulation.session import aead_demo, authenticated_session, public_decision
from bb84_lab.simulation.education import PacketInspector, lesson_session
from bb84_lab.core.secure_channel import AuthenticationError, DemoChannel
from tests.support import rejected


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
