"""Comparable authenticated BB84/E91 runs; return public aggregate metrics only."""

from dataclasses import replace
import hashlib
import secrets
import time

from bb84_lab.core.bb84 import Config, evaluate, expected_qber, monitor, simulate
from bb84_lab.core.e91 import bell_summary
from bb84_lab.core.e91_key import (
    BELL_DIRECTIONS, E91Config, combine_monitoring, evaluate_transmission,
    expected_key_qber, simulate_transmission,
)
from bb84_lab.core.postprocess import postprocess_bits
from bb84_lab.core.secure_channel import AuthenticatedTranscript, AuthenticationError, DemoChannel, ReplayError, _json_bytes


class _MeasuredTranscript(AuthenticatedTranscript):
    """Count a declared JSON envelope encoding, never save payloads or tags."""

    def __init__(self, psk, session_id):
        super().__init__(psk, session_id)
        self.public_json_bytes = 0

    def seal(self, sender, payload):
        envelope = super().seal(sender, payload)
        self.public_json_bytes += len(_json_bytes({
            "version": envelope.version, "session_id": envelope.session_id,
            "sender": sender, "sequence": envelope.sequence, "payload": payload,
            "tag": envelope.tag.hex(),
        }))
        return envelope


def _auth_pair():
    psk, session_id = secrets.token_bytes(32), secrets.token_hex(16)
    return _MeasuredTranscript(psk, session_id), _MeasuredTranscript(psk, session_id)


def _exchange(auth, sender, payload):
    origin, destination = auth if sender == "alice" else reversed(auth)
    return destination.receive(origin.seal(sender, payload))


def _check_aead(processed):
    if processed.status != "ready":
        return False
    if not processed.key_match or processed.output_bits < 256:
        raise AssertionError("Unconfirmed or undersized key was released")
    channel = DemoChannel.from_simulated_keys(processed._alice_key, processed._bob_key)
    packet = channel.encrypt(b"comparison-key-confirmation")
    damaged = replace(packet, ciphertext=bytes([packet.ciphertext[0] ^ 1]) + packet.ciphertext[1:])
    try:
        channel.decrypt(damaged)
    except AuthenticationError:
        pass
    else:
        raise AssertionError("Modified ciphertext accepted")
    if channel.decrypt(packet) != b"comparison-key-confirmation":
        raise AssertionError("AEAD roundtrip mismatch")
    try:
        channel.decrypt(packet)
    except ReplayError:
        return True
    raise AssertionError("Replay accepted")


def run_session(protocol, signals, seed, *, disturbance_fraction=0., noise_probability=0.,
                sample_fraction=.25, threshold=.05, min_samples=100, ablation=True):
    """E91's QBER-only variant reuses measurements, not an independent session.

    The ablation is diagnostic; it must never be used by the operational demo.
    p is a Bob bit-flip probability in both models. f labels different physical
    mechanisms and is deliberately called disturbance_fraction in the dataset.
    """
    if protocol not in ("bb84", "e91"):
        raise ValueError("Protocol must be bb84 or e91")
    if type(ablation) is not bool:
        raise ValueError("ablation must be bool")
    start, cpu_start = time.perf_counter(), time.process_time()
    if protocol == "bb84":
        config = Config(signals, disturbance_fraction, noise_probability, sample_fraction, threshold, min_samples, seed)
        transmission = simulate(config)
        evaluation = evaluate(transmission, config)
        sample = tuple(transmission.sifted_indices[i] for i in evaluation.sample_indices)
        retained = tuple(transmission.sifted_indices[i] for i in evaluation.retained_indices)
        settings_a, settings_b = transmission.alice_bases, transmission.bob_bases
        bell_positions = ()
        q_expected = expected_qber(disturbance_fraction, noise_probability)
    else:
        config = E91Config(signals, disturbance_fraction, noise_probability, sample_fraction, threshold, min_samples, seed)
        transmission = simulate_transmission(config)
        _, sample, retained = evaluate_transmission(transmission)
        settings_a, settings_b = transmission.alice_settings, transmission.bob_settings
        bell_positions = transmission.bell_indices
        q_expected = expected_key_qber(disturbance_fraction, noise_probability)
    simulation_seconds = time.perf_counter() - start
    auth = _auth_pair()
    monitoring_start = time.perf_counter()
    a = _exchange(auth, "alice", {
        "kind": protocol + "-comparison-sample", "settings": list(settings_a),
        "sample_positions": list(sample), "bits": [transmission.alice_bits[i] for i in sample],
        "bell_bits": [transmission.alice_bits[i] for i in bell_positions],
    })
    b = _exchange(auth, "bob", {
        "kind": protocol + "-comparison-sample", "settings": list(settings_b),
        "sample_positions": list(sample), "bits": [transmission.bob_bits[i] for i in sample],
        "bell_bits": [1 ^ transmission.bob_bits[i] for i in bell_positions],
    })
    qber = monitor(sum(x != y for x, y in zip(a["bits"], b["bits"])), len(sample), threshold, min_samples)
    bell_start = time.perf_counter()
    if protocol == "e91":
        counts = {pair: [0, 0, 0, 0] for pair in BELL_DIRECTIONS}
        for index, alice, bob in zip(bell_positions, a["bell_bits"], b["bell_bits"]):
            counts[a["settings"][index], b["settings"][index]][2 * alice + bob] += 1
        bell = bell_summary(counts)
        decision = combine_monitoring(qber, bell)
    else:
        bell = None
        decision = qber
    bell_seconds = time.perf_counter() - bell_start if bell else 0.
    monitoring_seconds = time.perf_counter() - monitoring_start
    monitor_json_bytes = sum(endpoint.public_json_bytes for endpoint in auth)
    policies = [("qber_chsh" if bell else "qber", decision)]
    if bell and ablation:
        policies.append(("qber_only_ablation", qber))
    rows, cache = [], {}
    recon_seed = int.from_bytes(hashlib.sha256(f"comparison-cascade:{seed}".encode("ascii")).digest()[:16], "big")
    for policy, gate in policies:
        cache_key = gate["status"] == "continue"
        if cache_key not in cache:
            post_auth = _auth_pair()
            post_start, post_cpu = time.perf_counter(), time.process_time()
            processed = postprocess_bits(
                tuple(transmission.alice_bits[i] for i in retained),
                tuple(transmission.bob_bits[i] for i in retained), gate, *post_auth,
                reconciliation_seed=recon_seed, protocol=protocol,
            )
            post_seconds = time.perf_counter() - post_start
            post_cpu_seconds = time.process_time() - post_cpu
            aead_start = time.perf_counter()
            verified = _check_aead(processed)
            cache[cache_key] = (processed, post_seconds, post_cpu_seconds, verified,
                               time.perf_counter() - aead_start if verified else 0.,
                               sum(endpoint.public_json_bytes for endpoint in post_auth))
            reused = False
        else:
            reused = True
        processed, post_seconds, post_cpu_seconds, verified, aead_seconds, post_json_bytes = cache[cache_key]
        ready = processed.status == "ready"
        alarm = qber["status"] == "anomalous" or bool(bell and policy != "qber_only_ablation"
                                                        and bell["status"] == "at_or_below_bound")
        output = processed.output_bits if ready else 0
        seed_bits = len(retained) + output - 1 if ready else 0
        rows.append({
            "protocol": protocol, "policy": policy, "seed": seed, "signals": signals,
            "disturbance_fraction": disturbance_fraction, "noise_probability": noise_probability,
            "expected_qber": q_expected, "sample_fraction": sample_fraction, "threshold": threshold,
            "min_samples": min_samples, "sifted_bits": len(transmission.sifted_indices),
            "sample_bits": len(sample), "sample_errors": qber["sample_errors"],
            "retained_bits": len(retained), "bell_pairs": len(bell_positions),
            "discarded_signals": signals - len(bell_positions) - len(transmission.sifted_indices),
            "qber": qber["qber"], "qber_ci_low": qber["ci_low"], "qber_ci_high": qber["ci_high"],
            "qber_status": qber["status"], "monitor_status": gate["status"], "alarm": alarm,
            "monitor_pass": gate["status"] == "continue", "aborted": not ready,
            "not_flagged": disturbance_fraction > 0 and not alarm,
            "missed_intervention": disturbance_fraction > 0 and gate["status"] == "continue",
            "intervention_key_released": disturbance_fraction > 0 and ready,
            "false_alarm": disturbance_fraction == 0 and q_expected <= threshold and alarm,
            "no_intervention_alarm": disturbance_fraction == 0 and alarm,
            "bell_status": bell["status"] if bell else "not_applicable",
            "chsh_abs_s": bell["abs_s"] if bell else None,
            "chsh_ci_low": bell["ci_low"] if bell else None,
            "chsh_ci_high": bell["ci_high"] if bell else None,
            "postprocess_status": processed.status, "postprocess_reason": processed.reason,
            "corrected_errors": processed.corrected_errors, "parity_leak_bits": processed.parity_leak_bits,
            "confirmation_leak_bits": processed.confirmation_leak_bits,
            "entropy_budget_bits": processed.entropy_budget_bits,
            "after_cascade_bits": len(retained) if processed.confirmation_leak_bits else None,
            "after_confirmation_bits": len(retained) if processed.key_match else None,
            "toeplitz_seed_bits": seed_bits, "y_final": output, "ready": ready,
            "key_match": processed.key_match, "aead_verified": verified,
            "application_key_bits": 256 if ready else 0,
            "monitor_public_outcome_bits": 2 * (len(sample) + len(bell_positions)),
            "total_public_outcome_bits": 2 * (len(sample) + len(bell_positions))
                + processed.parity_leak_bits + processed.confirmation_leak_bits,
            "monitor_public_json_bytes": monitor_json_bytes,
            "postprocess_public_json_bytes": post_json_bytes,
            "simulation_seconds": simulation_seconds, "monitoring_seconds": monitoring_seconds,
            "bell_calculation_seconds": bell_seconds if policy != "qber_only_ablation" else 0.,
            "postprocessing_seconds": post_seconds,
            "key_setup_seconds": simulation_seconds + monitoring_seconds + post_seconds,
            "aead_verification_seconds": aead_seconds,
            "postprocessing_cpu_seconds": post_cpu_seconds, "postprocessing_reused": reused,
        })
    # Session CPU includes any ablation work, unlike policy-specific wall times.
    rows[0]["session_cpu_seconds"] = time.process_time() - cpu_start
    rows[0]["session_wall_seconds"] = time.perf_counter() - start
    for row in rows[1:]:
        row["session_cpu_seconds"] = None
        row["session_wall_seconds"] = None
    return rows
