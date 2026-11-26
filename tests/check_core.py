"""Assert-based core checks, run through tests.self_check."""

from dataclasses import replace
import hashlib
import json
import math
import secrets
from bb84_lab.core.bb84 import Config, evaluate, expected_qber, monitor, run_session, simulate, wilson_interval
from bb84_lab.core.e91 import simulate_e91
from bb84_lab.simulation.session import integrated_session
from bb84_lab.core.postprocess import key_budget, pack_bits, postprocess, reconcile, toeplitz_bits
from bb84_lab.core.secure_channel import AuthenticatedTranscript, AuthenticationError, DemoChannel
from tests.support import rejected


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


def check_e91():
    ideal = simulate_e91()
    assert ideal == simulate_e91(signals=4096, seed=2026, noise_probability=0)
    assert set(ideal) == {"signals", "seed", "noise_probability", "discarded_count", "bell", "key"}
    bell, key = ideal["bell"], ideal["key"]
    assert [(row["alice_angle"], row["bob_angle"], row["sign"]) for row in bell["pairs"]] == [
        (0, 45, 1), (0, 135, -1), (90, 45, 1), (90, 135, 1)
    ]
    assert [(row["alice_angle"], row["bob_angle"]) for row in key["pairs"]] == [(45, 45), (90, 90)]
    assert math.isclose(bell["expected_s"], -2 * math.sqrt(2))
    assert key["qber"] == key["expected_qber"] == 0
    assert bell["status"] == "violation" and bell["ci_low"] > 2

    for probability in (0.3, 1):
        run = simulate_e91(signals=16384, noise_probability=probability)
        bell, key = run["bell"], run["key"]
        assert math.isclose(bell["expected_s"], -2 * math.sqrt(2) * (1 - probability), abs_tol=1e-12)
        assert math.isclose(key["expected_qber"], probability / 2)
        assert abs(bell["s"] - bell["expected_s"]) < 0.15
        assert abs(key["qber"] - key["expected_qber"]) < 0.04
        if probability == 1:
            assert bell["status"] == "at_or_below_bound" and bell["ci_high"] <= 2

    for run in (ideal, simulate_e91(noise_probability=0.3)):
        bell, key = run["bell"], run["key"]
        for row in bell["pairs"] + key["pairs"]:
            assert row["count"] == sum(row[term] for term in ("pp", "pm", "mp", "mm"))
        for row in bell["pairs"]:
            assert math.isclose(row["correlation"], (row["pp"] + row["mm"] - row["pm"] - row["mp"]) / row["count"])
        for row in key["pairs"]:
            assert row["errors"] == row["pp"] + row["mm"]
        assert math.isclose(bell["s"], sum(row["sign"] * row["correlation"] for row in bell["pairs"]))
        assert bell["ci_low"] <= abs(bell["s"]) <= bell["ci_high"]
        assert key["qber"] == key["errors"] / key["count"]
        assert key["count"] == sum(row["count"] for row in key["pairs"])
        assert key["errors"] == sum(row["errors"] for row in key["pairs"])
        assert key["count"] + sum(row["count"] for row in bell["pairs"]) + run["discarded_count"] == run["signals"]
        assert (key["ci_low"], key["ci_high"]) == wilson_interval(key["errors"], key["count"])

    tiny_runs = [simulate_e91(signals=1, seed=seed) for seed in range(12)]
    for run in tiny_runs:
        bell = run["bell"]
        assert bell["status"] == "inconclusive"
        assert all(bell[field] is None for field in ("s", "abs_s", "ci_low", "ci_high"))
        assert all(row["correlation"] is None for row in bell["pairs"] if row["count"] == 0)
    empty_key = next(run["key"] for run in tiny_runs if run["key"]["count"] == 0)
    assert all(empty_key[field] is None for field in ("qber", "ci_low", "ci_high"))
    for change in ({"signals": 0}, {"signals": 65537}, {"signals": True}, {"seed": -1},
                   {"seed": 2**31}, {"noise_probability": True}, {"noise_probability": 1.1},
                   {"noise_probability": float("inf")}):
        rejected(lambda change=change: simulate_e91(**change))


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
