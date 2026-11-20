"""CLI BB84, hậu xử lý giáo dục và ChaCha20-Poly1305."""

import argparse
from dataclasses import asdict, replace
import hashlib
import json
import math
import secrets
import sys
import time

from bb84_lab.bb84 import Config, evaluate, expected_qber, monitor, simulate
from bb84_lab.secure_channel import (
    AuthenticatedTranscript, AuthenticationError, DemoChannel, ReplayError,
)
from bb84_lab.postprocess import postprocess


def public_decision(alice, bob, config):
    """Validate authenticated public data before the monitor can consume it."""
    alice_fields = {
        "kind", "signals", "sample_fraction", "threshold", "min_samples",
        "alice_bases", "sample_indices", "sample_alice_bits",
    }
    bob_fields = {"kind", "bob_bases", "sample_indices", "sample_bob_bits"}
    if type(alice) is not dict or type(bob) is not dict:
        raise AuthenticationError("Transcript phải là đối tượng JSON")
    if set(alice) != alice_fields or set(bob) != bob_fields:
        raise AuthenticationError("Sai cấu trúc transcript")
    if alice["kind"] != "bb84-sample-v1" or bob["kind"] != "bb84-bob-sample-v1":
        raise AuthenticationError("Sai loại thông điệp")
    for name in ("signals", "sample_fraction", "threshold", "min_samples"):
        value = alice[name]
        expected_type = int if name in ("signals", "min_samples") else (int, float)
        if isinstance(value, bool) or not isinstance(value, expected_type) or value != getattr(config, name):
            raise AuthenticationError(f"Sai tham số đã thống nhất: {name}")
    for payload, field, length in (
        (alice, "alice_bases", config.signals), (bob, "bob_bases", config.signals),
    ):
        values = payload[field]
        if type(values) is not list or len(values) != length:
            raise AuthenticationError("Sai độ dài cơ sở")
        if any(type(bit) is not int or bit not in (0, 1) for bit in values):
            raise AuthenticationError("Cơ sở phải là Z/X mã hóa 0/1")
    sifted = sum(a == b for a, b in zip(alice["alice_bases"], bob["bob_bases"]))
    sample_count = math.floor(config.sample_fraction * sifted)
    indices = alice["sample_indices"]
    if type(indices) is not list or len(indices) != sample_count:
        raise AuthenticationError("Sai số vị trí mẫu")
    if any(type(index) is not int or not 0 <= index < sifted for index in indices):
        raise AuthenticationError("Vị trí mẫu ngoài phạm vi")
    bob_indices = bob["sample_indices"]
    if type(bob_indices) is not list or any(type(index) is not int for index in bob_indices):
        raise AuthenticationError("Sai kiểu vị trí mẫu phía Bob")
    if len(set(indices)) != len(indices) or bob_indices != indices:
        raise AuthenticationError("Mẫu bị trùng hoặc hai phía chọn mẫu khác nhau")
    for payload, field in ((alice, "sample_alice_bits"), (bob, "sample_bob_bits")):
        bits = payload[field]
        if type(bits) is not list or len(bits) != sample_count:
            raise AuthenticationError("Sai độ dài mẫu công khai")
        if any(type(bit) is not int or bit not in (0, 1) for bit in bits):
            raise AuthenticationError("Mẫu công khai phải chứa bit 0/1")
    errors = sum(a != b for a, b in zip(alice["sample_alice_bits"], bob["sample_bob_bits"]))
    decision = monitor(errors, sample_count, config.threshold, config.min_samples)
    return {
        **decision, "sifted_count": sifted, "remaining_count": sifted - sample_count,
        "y_pre": sifted - sample_count if decision["status"] == "continue" else 0,
    }


def _authenticated_exchange(config, tamper=False):
    transmission = simulate(config)
    # evaluate prepares the public sample; the accepted decision is recomputed
    # below from authenticated payloads, without private bits or Eve/noise labels.
    evaluation = evaluate(transmission, config)
    sample = evaluation.public_transcript()
    bob_sample = {
        "kind": "bb84-bob-sample-v1", "bob_bases": sample.pop("bob_bases"),
        "sample_indices": sample["sample_indices"],
        "sample_bob_bits": sample.pop("sample_bob_bits"),
    }
    psk = secrets.token_bytes(32)  # Provisioned outside the simulated BB84 exchange.
    session_id = secrets.token_hex(16)
    alice = AuthenticatedTranscript(psk, session_id)
    bob = AuthenticatedTranscript(psk, session_id)
    alice_message = alice.seal("alice", sample)
    if tamper:
        alice_message = replace(alice_message, payload={**sample, "threshold": 1.0})
    verified_alice = bob.receive(alice_message)
    verified_bob = alice.receive(bob.seal("bob", bob_sample))
    decision = public_decision(verified_alice, verified_bob, config)
    return transmission, evaluation, decision, alice, bob


def authenticated_session(config, tamper=False):
    _, _, decision, alice, _ = _authenticated_exchange(config, tamper)
    return {
        "session_id": alice.session_id, **asdict(config),
        **decision, "transcript_authenticated": True, "bb84_key_released": False,
        "scope": "Chưa đối soát/xác nhận/Toeplitz; continue chỉ cho phép hậu xử lý tiếp.",
    }


def _exercise_aead(channel, message):
    plaintext = message.encode("utf-8")
    packet = channel.encrypt(plaintext)
    aad = DemoChannel._aad(packet.version, packet.session_id, packet.sender, packet.sequence)
    damaged = replace(packet, ciphertext=bytes([packet.ciphertext[0] ^ 1]) + packet.ciphertext[1:])
    try:
        channel.decrypt(damaged)
    except AuthenticationError:
        tamper_rejected = True
    else:
        raise AssertionError("Bản mã bị sửa đã được chấp nhận")
    recovered = channel.decrypt(packet)
    if recovered != plaintext:
        raise AssertionError("Bản rõ không khớp")
    try:
        channel.decrypt(packet)
    except ReplayError:
        replay_rejected = True
    else:
        raise AssertionError("Gói phát lại đã được chấp nhận")
    return {
        "session_id": channel.session_id, "key_source": channel.key_source,
        "algorithm": "ChaCha20-Poly1305",
        "implementation": "cryptography.hazmat.primitives.ciphers.aead.ChaCha20Poly1305",
        "key_bytes": 32, "nonce_bytes": 12, "tag_bytes": len(packet.ciphertext) - len(plaintext),
        "aad_bytes": len(aad), "sequence": packet.sequence,
        "aad_sha256": hashlib.sha256(aad).hexdigest(),
        "ciphertext_sha256": hashlib.sha256(packet.ciphertext).hexdigest(),
        "plaintext_bytes": len(plaintext),
        "ciphertext_bytes": len(packet.ciphertext), "roundtrip_ok": recovered == plaintext,
        "tamper_rejected": tamper_rejected, "replay_rejected": replay_rejected,
    }


def _verification_log(session_id, config, decision, processed, encryption):
    def entry(code, group, title, status, implementation, formula, result, values):
        return {
            "code": code, "group": group, "title": title, "status": status,
            "implementation": implementation, "formula": formula,
            "result": result, "values": values,
        }

    sample_count = decision["sample_count"]
    sample_errors = decision["sample_errors"]
    qber = decision["qber"]
    ci_low = decision["ci_low"]
    ci_high = decision["ci_high"]
    entries = [
        entry(
            "BB84-01", "bb84", "Chuẩn bị và đo", "passed",
            "bb84_lab.bb84.simulate",
            "Alice chọn bit/cơ sở Z-X; Bob chọn cơ sở Z-X; Eve tùy chọn chặn-đo-gửi lại.",
            f"N={config.signals}; seed={config.seed}; f={config.eve_fraction}; "
            f"p={config.noise_probability}; QBER kỳ vọng mô hình={expected_qber(config.eve_fraction, config.noise_probability):.8f}.",
            {"signals": config.signals, "seed": config.seed,
             "eve_fraction": config.eve_fraction, "noise_probability": config.noise_probability,
             "expected_qber": expected_qber(config.eve_fraction, config.noise_probability)},
        ),
        entry(
            "BB84-02", "bb84", "Sàng lọc và lấy mẫu", "passed",
            "bb84_lab.bb84.evaluate",
            "n_sample = floor(alpha * n_sift); n_retained = n_sift - n_sample",
            f"n_sift={decision['sifted_count']}; floor({config.sample_fraction} × "
            f"{decision['sifted_count']})={sample_count}; n_retained={decision['remaining_count']}.",
            {"sifted_count": decision["sifted_count"], "sample_fraction": config.sample_fraction,
             "sample_count": sample_count, "remaining_count": decision["remaining_count"]},
        ),
    ]
    if qber is None:
        entries.append(entry(
            "BB84-03", "bb84", "QBER và Wilson 95%", "stopped",
            "bb84_lab.bb84.monitor / wilson_interval",
            "q_hat = errors / n_sample; Wilson chỉ tính khi n_sample > 0",
            "Không có mẫu công khai nên QBER và khoảng Wilson không xác định.",
            {"sample_errors": sample_errors, "sample_count": sample_count,
             "qber": None, "ci_low": None, "ci_high": None},
        ))
    else:
        entries.append(entry(
            "BB84-03", "bb84", "QBER và Wilson 95%", "passed",
            "bb84_lab.bb84.monitor / wilson_interval",
            "q_hat = errors / n_sample; Wilson 95% dùng z = 1.959963984540054",
            f"{sample_errors} / {sample_count} = {qber:.8f}; "
            f"CI95=[{ci_low:.8f}, {ci_high:.8f}].",
            {"sample_errors": sample_errors, "sample_count": sample_count,
             "qber": qber, "ci_low": ci_low, "ci_high": ci_high,
             "z": 1.959963984540054},
        ))
    rules = {
        "continue": "ci_high <= threshold",
        "anomalous": "ci_low > threshold",
        "inconclusive": "thiếu mẫu hoặc khoảng Wilson cắt ngưỡng",
    }
    entries.append(entry(
        "BB84-04", "bb84", "Quyết định giám sát",
        "passed" if decision["status"] == "continue" else "stopped",
        "bb84_lab.bb84.monitor",
        "continue nếu cận trên <= ngưỡng; anomalous nếu cận dưới > ngưỡng; còn lại inconclusive",
        f"{rules[decision['status']]}; threshold={config.threshold}; "
        f"status={decision['status']}; reason={decision['reason']}.",
        {"threshold": config.threshold, "min_samples": config.min_samples,
         "status": decision["status"], "reason": decision["reason"]},
    ))

    post_ran = processed.status not in ("skipped",)
    entries.append(entry(
        "POST-01", "postprocess", "Đối soát và xác nhận",
        "passed" if processed.key_match else "failed" if processed.status == "failed" else "stopped",
        "bb84_lab.postprocess.reconcile / postprocess",
        "Cascade sửa Bob qua truy vấn parity; SHA-256 xác nhận hai chuỗi trước khi phát hành khóa.",
        (f"retained={processed.retained_bits}; corrected={processed.corrected_errors}; "
         f"parity_leak={processed.parity_leak_bits}; confirmation_leak={processed.confirmation_leak_bits}; "
         f"key_match={processed.key_match}; status={processed.status}.") if post_ran
        else f"Không chạy vì monitor status={decision['status']}.",
        {"retained_bits": processed.retained_bits, "corrected_errors": processed.corrected_errors,
         "parity_leak_bits": processed.parity_leak_bits,
         "confirmation_leak_bits": processed.confirmation_leak_bits,
         "key_match": processed.key_match, "status": processed.status},
    ))
    entries.append(entry(
        "POST-02", "postprocess", "Ngân sách và Toeplitz",
        "passed" if processed.status == "ready" else "stopped",
        "bb84_lab.postprocess.key_budget / toeplitz_bits",
        "entropy=floor(n_retained*(1-h2(ci_high))); output=floor8(max(0, entropy-leak_parity-leak_confirm-64))",
        f"entropy={processed.entropy_budget_bits}; output={processed.output_bits}; "
        f"cần >=256 bit; status={processed.status}; reason={processed.reason}.",
        {"qber_upper": ci_high, "entropy_budget_bits": processed.entropy_budget_bits,
         "parity_leak_bits": processed.parity_leak_bits,
         "confirmation_leak_bits": processed.confirmation_leak_bits,
         "safety_bits": 64, "output_bits": processed.output_bits,
         "status": processed.status, "reason": processed.reason},
    ))

    if encryption:
        entries.extend((
            entry(
                "AEAD-01", "aead", "Mã hóa ChaCha20-Poly1305", "passed",
                encryption["implementation"] + ".encrypt",
                "ciphertext_and_tag = encrypt(nonce_96_bit, plaintext, AAD)",
                f"key={encryption['key_bytes']} byte; nonce={encryption['nonce_bytes']} byte; "
                f"AAD={encryption['aad_bytes']} byte; plaintext={encryption['plaintext_bytes']} byte; "
                f"ciphertext+tag={encryption['ciphertext_bytes']} byte; tag={encryption['tag_bytes']} byte.",
                {name: encryption[name] for name in (
                    "key_bytes", "nonce_bytes", "aad_bytes", "plaintext_bytes",
                    "ciphertext_bytes", "tag_bytes", "sequence", "aad_sha256",
                    "ciphertext_sha256",
                )},
            ),
            entry(
                "AEAD-02", "aead", "Giải mã và chống sửa/phát lại", "passed",
                encryption["implementation"] + ".decrypt",
                "decrypt hợp lệ; lật 1 bit phải InvalidTag; sequence đã nhận phải bị từ chối khi phát lại",
                f"roundtrip={encryption['roundtrip_ok']}; tamper_rejected={encryption['tamper_rejected']}; "
                f"replay_rejected={encryption['replay_rejected']}.",
                {"roundtrip_ok": encryption["roundtrip_ok"],
                 "tamper_rejected": encryption["tamper_rejected"],
                 "replay_rejected": encryption["replay_rejected"]},
            ),
        ))
    else:
        entries.append(entry(
            "AEAD-00", "aead", "ChaCha20-Poly1305 chưa chạy", "not_run",
            "bb84_lab.demo.integrated_session",
            "Chỉ gọi ChaCha20Poly1305 khi postprocessing.status == 'ready'.",
            f"postprocessing.status={processed.status}; không tạo bản mã.",
            {"postprocessing_status": processed.status, "encryption": None},
        ))

    log = {
        "version": "bb84-lab-verification-v1", "session_id": session_id,
        "public_only": True,
        "scope": "Dấu vết thực thi phần mềm; không phải bằng chứng QKD vật lý hoặc chứng minh an toàn mật mã.",
        "omitted": ["raw bits", "sample bit values", "keys", "PSK", "nonce value", "plaintext", "ciphertext"],
        "canonicalization": "UTF-8 JSON; ensure_ascii=false; sort_keys=true; separators=(',', ':')",
        "entries": entries,
    }
    canonical = json.dumps(log, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    log["sha256"] = hashlib.sha256(canonical).hexdigest()
    return log


def aead_demo(message):
    return _exercise_aead(DemoChannel(), message)


def prepare_packet_session(config, tamper=False):
    """Prepare a fresh BB84 model channel for user-driven packet delivery."""
    transmission, evaluation, decision, alice, bob = _authenticated_exchange(config, tamper)
    processed = postprocess(transmission, evaluation, decision, alice, bob)
    channel = (DemoChannel.from_simulated_keys(processed._alice_key, processed._bob_key)
               if processed.status == "ready" else None)
    result = {"session_id": alice.session_id, **asdict(config), **decision,
              "transcript_authenticated": True, "postprocessing": processed.public_summary(),
              "bb84_key_released": channel is not None, "packet": None}
    return result, channel


def integrated_session(config, tamper=False, message="Xin chào từ BB84"):
    if type(message) is not str or len(message.encode("utf-8")) > 16384:
        raise ValueError("Thông điệp phải là văn bản UTF-8 tối đa 16 KB")
    started = time.perf_counter()
    transmission, evaluation, decision, alice, bob = _authenticated_exchange(config, tamper)
    simulation_seconds = time.perf_counter() - started
    post_started = time.perf_counter()
    processed = postprocess(transmission, evaluation, decision, alice, bob)
    post_seconds = time.perf_counter() - post_started
    encryption = None
    encrypt_started = time.perf_counter()
    if processed.status == "ready":
        channel = DemoChannel.from_simulated_keys(processed._alice_key, processed._bob_key)
        encryption = _exercise_aead(channel, message)
    verification = _verification_log(alice.session_id, config, decision, processed, encryption)
    return {
        "session_id": alice.session_id, **asdict(config), **decision,
        "transcript_authenticated": True,
        "bb84_key_released": processed.status == "ready",
        "postprocessing": processed.public_summary(), "encryption": encryption,
        "verification": verification,
        "timings": {"simulation_seconds": simulation_seconds,
                    "postprocessing_seconds": post_seconds,
                    "encryption_seconds": time.perf_counter() - encrypt_started if encryption else 0,
                    "total_seconds": time.perf_counter() - started},
        "scope": "Mô phỏng cổ điển; seed công khai. Khóa mô phỏng không bảo vệ dữ liệu thật. "
                 "Ngân sách entropy giáo dục và Wilson không phải chứng minh an toàn finite-key.",
    }


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    bb84 = subparsers.add_parser("bb84", help="Mô phỏng, giám sát và hậu xử lý giáo dục")
    bb84.add_argument("--signals", type=int, default=4096)
    bb84.add_argument("--eve", type=float, default=0.0)
    bb84.add_argument("--noise", type=float, default=0.0)
    bb84.add_argument("--sample", type=float, default=0.25)
    bb84.add_argument("--threshold", type=float, default=0.05)
    bb84.add_argument("--min-samples", type=int, default=100)
    bb84.add_argument("--seed", type=int, default=2026)
    bb84.add_argument("--tamper-transcript", action="store_true")
    bb84.add_argument("--monitor-only", action="store_true", help="Chỉ giám sát, bỏ hậu xử lý")
    bb84.add_argument("--message", default="Xin chào từ BB84")
    aead = subparsers.add_parser("aead", help="Demo riêng bằng khóa ngẫu nhiên, không dùng khóa BB84")
    aead.add_argument("--message", default="Xin chào từ mô phỏng BB84")
    args = parser.parse_args()
    try:
        if args.command == "bb84":
            config = Config(args.signals, args.eve, args.noise, args.sample,
                            args.threshold, args.min_samples, args.seed)
            result = (authenticated_session(config, args.tamper_transcript) if args.monitor_only
                      else integrated_session(config, args.tamper_transcript, args.message))
        else:
            result = aead_demo(args.message)
    except AuthenticationError as error:
        parser.exit(2, f"Hủy phiên: {error}. Không phát hành khóa hoặc bản rõ.\n")
    except ValueError as error:
        parser.exit(2, f"Lỗi tham số: {error}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
