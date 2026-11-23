"""Distributed educational BB84 key agreement for independent Alice/Bob roles.

Quantum states are readable classical data; the model provides no physical QKD secrecy.
"""

import hashlib
import hmac
import math
import random
import re
import secrets

from bb84_lab.core.bb84 import monitor
from bb84_lab.core.postprocess import cascade_correct, key_budget, pack_bits, toeplitz_bits
from bb84_lab.core.secure_channel import AuthenticationError, DemoChannel
from bb84_lab.network.config import network_config, public_config
from bb84_lab.network.packets import receive_encrypted, send_encrypted
from bb84_lab.network.transport import PublicPeer, receive_frame, send_frame


def _bits(value, length):
    if type(value) is not list or len(value) != length or any(type(v) is not int or v not in (0, 1) for v in value):
        raise ValueError("Chuỗi bit/cơ sở không hợp lệ")
    return value


def _positions(alice_bases, bob_bases, fraction, sample_seed):
    sifted = [i for i, (a, b) in enumerate(zip(alice_bases, bob_bases)) if a == b]
    order = list(sifted)
    random.Random(sample_seed).shuffle(order)
    sample = order[:math.floor(len(sifted) * fraction)]
    excluded = set(sample)
    retained = [i for i in sifted if i not in excluded]
    return sifted, sample, retained


def _confirmation(session_id, bits):
    context = b"bb84-network/confirm/v1\0" + session_id.encode() + len(bits).to_bytes(8, "big")
    return hashlib.sha256(context + pack_bits(bits)).hexdigest()


def _amplify(bits, seed_hex, output_bits):
    length = len(bits) + output_bits - 1
    if type(seed_hex) is not str or len(seed_hex) != 2 * ((length + 7) // 8):
        raise ValueError("Sai seed Toeplitz")
    data = bytes.fromhex(seed_hex)
    seed = tuple((data[i // 8] >> (7 - i % 8)) & 1 for i in range(length))
    return pack_bits(toeplitz_bits(bits, seed, output_bits))[:32]


def hello_alice(connection, psk):
    challenge = receive_frame(connection)
    nonce = challenge.get("nonce")
    if challenge.get("kind") != "challenge" or type(nonce) is not str or not re.fullmatch(r"[0-9a-f]{32}", nonce):
        raise AuthenticationError("Sai challenge Bob")
    session_id = secrets.token_hex(16) + nonce
    send_frame(connection, {"kind": "hello", "session_id": session_id})
    return PublicPeer(connection, psk, session_id, "alice")


def hello_bob(connection, psk):
    nonce = secrets.token_hex(16)
    send_frame(connection, {"kind": "challenge", "nonce": nonce})
    hello = receive_frame(connection)
    session_id = hello.get("session_id")
    if (hello.get("kind") != "hello" or type(session_id) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", session_id) or not session_id.endswith(nonce)):
        raise AuthenticationError("Sai phiên hoặc challenge")
    return PublicPeer(connection, psk, session_id, "bob")


def prepare_alice_channel(peer, config, event):
    peer.send({"kind": "config", "config": public_config(config)})
    bits = [secrets.randbits(1) for _ in range(config.signals)]
    bases = [secrets.randbits(1) for _ in bits]
    # Deliberately unauthenticated simulated quantum states. Never log these.
    send_frame(peer.connection, {"kind": "quantum", "states": [2 * a + b for a, b in zip(bases, bits)]})
    peer.send({"kind": "bases", "bases": bases})
    bob_bases = _bits(peer.receive("bases")["bases"], len(bits))
    sample_seed = secrets.randbits(128)  # Chosen after Bob has already measured.
    sifted, sample, retained = _positions(bases, bob_bases, config.sample_fraction, sample_seed)
    peer.send({"kind": "sample", "sample_seed": sample_seed, "bits": [bits[i] for i in sample]})
    response = peer.receive("decision")
    bob_sample = _bits(response["bits"], len(sample))
    decision = monitor(sum(bits[i] != b for i, b in zip(sample, bob_sample)), len(sample),
                       config.threshold, config.min_samples)
    if response["decision"] != decision:
        raise AuthenticationError("Hai bên tính QBER khác nhau")
    stats = {**decision, "sifted_bits": len(sifted), "retained_bits": len(retained),
             "session_id": peer.session_id, "config": public_config(config),
             "sample_seed": sample_seed, "random_source": "OS; seed chỉ dùng hoán vị công khai"}
    event("qber", "Đã đối chiếu mẫu; bit mẫu bị loại khỏi khóa", **stats)
    if decision["status"] != "continue":
        return None, stats
    local = tuple(bits[i] for i in retained)
    leak = queries = 0
    while True:
        query = peer.receive()
        if query.get("kind") == "confirm":
            break
        indices = query.get("indices")
        if (query.get("kind") != "parity" or type(query.get("query")) is not int
                or query["query"] != queries or queries >= 32 * len(local)
                or type(indices) is not list or not 1 <= len(indices) <= len(local)
                or any(type(i) is not int or not 0 <= i < len(local) for i in indices)
                or len(set(indices)) != len(indices) or type(query.get("parity")) is not int
                or query["parity"] not in (0, 1)):
            raise AuthenticationError("Truy vấn Cascade không hợp lệ")
        parity = sum(local[i] for i in indices) % 2
        peer.send({"kind": "parity", "query": queries, "parity": parity})
        queries += 1
        leak += 2
    accepted = type(query.get("digest")) is str and hmac.compare_digest(query["digest"], _confirmation(peer.session_id, local))
    entropy, output = key_budget(len(local), decision["ci_high"], leak)
    peer.send({"kind": "confirmed", "accepted": accepted, "output_bits": output, "parity_leak_bits": leak})
    stats.update(parity_leak_bits=leak, confirmation_leak_bits=257,
                 entropy_budget_bits=entropy, output_bits=output)
    if not accepted:
        raise AuthenticationError("Xác nhận khóa thất bại; hủy phiên")
    if output < 256:
        stats["status"] = "insufficient_key"
        return None, stats
    seed = secrets.token_hex((len(local) + output - 1 + 7) // 8)
    peer.send({"kind": "toeplitz", "seed": seed})
    channel = DemoChannel.from_local_model_key(_amplify(local, seed, output), peer.session_id)
    send_encrypted(peer, channel, b"bb84-network-key-confirm-v1")
    if peer.receive("ready").get("accepted") is not True:
        raise AuthenticationError("Bob chưa xác nhận khóa ứng dụng")
    event("key", "Cascade, xác nhận khóa và Toeplitz hoàn tất", **stats)
    return channel, stats


def prepare_bob_channel(peer, event, noise=0):
    config = network_config(peer.receive("config")["config"])
    quantum = receive_frame(peer.connection)
    states = quantum.get("states")
    if (quantum.get("kind") != "quantum" or type(states) is not list or len(states) != config.signals
            or any(type(s) is not int or not 0 <= s <= 3 for s in states)):
        raise ValueError("Tín hiệu mô phỏng không hợp lệ")
    bases = [secrets.randbits(1) for _ in states]
    rng = secrets.SystemRandom()
    bits = [(s % 2 if s // 2 == b else secrets.randbits(1)) ^ int(rng.random() < noise)
            for s, b in zip(states, bases)]
    alice_bases = _bits(peer.receive("bases")["bases"], len(states))
    peer.send({"kind": "bases", "bases": bases})
    sample_payload = peer.receive("sample")
    sample_seed = sample_payload.get("sample_seed")
    if type(sample_seed) is not int or not 0 <= sample_seed < 2**128:
        raise ValueError("Seed lấy mẫu không hợp lệ")
    sifted, sample, retained = _positions(alice_bases, bases, config.sample_fraction, sample_seed)
    alice_sample = _bits(sample_payload["bits"], len(sample))
    decision = monitor(sum(bits[i] != a for i, a in zip(sample, alice_sample)), len(sample),
                       config.threshold, config.min_samples)
    peer.send({"kind": "decision", "decision": decision, "bits": [bits[i] for i in sample]})
    stats = {**decision, "sifted_bits": len(sifted), "retained_bits": len(retained),
             "session_id": peer.session_id, "config": public_config(config),
             "sample_seed": sample_seed, "noise_probability": noise,
             "random_source": "OS; seed chỉ dùng hoán vị công khai"}
    event("qber", "Đã đo tín hiệu, loại mẫu và tính QBER", **stats)
    if decision["status"] != "continue":
        return None, stats
    leak = queries = 0

    def parity(indices, corrected):
        nonlocal leak, queries
        local = sum(corrected[i] for i in indices) % 2
        peer.send({"kind": "parity", "query": queries, "indices": list(indices), "parity": local})
        reply = peer.receive("parity")
        if reply.get("query") != queries or type(reply.get("parity")) is not int or reply["parity"] not in (0, 1):
            raise AuthenticationError("Sai phản hồi parity")
        queries += 1
        leak += 2
        return local != reply["parity"]

    corrected, corrections = cascade_correct(tuple(bits[i] for i in retained), decision["qber"], parity, config.seed)
    peer.send({"kind": "confirm", "digest": _confirmation(peer.session_id, corrected)})
    reply = peer.receive("confirmed")
    entropy, output = key_budget(len(corrected), decision["ci_high"], leak)
    if reply != {"kind": "confirmed", "accepted": True, "output_bits": output, "parity_leak_bits": leak}:
        raise AuthenticationError("Xác nhận khóa/ngân sách không khớp")
    stats.update(parity_leak_bits=leak, confirmation_leak_bits=257, corrected_errors=corrections,
                 entropy_budget_bits=entropy, output_bits=output)
    if output < 256:
        stats["status"] = "insufficient_key"
        return None, stats
    seed = peer.receive("toeplitz")["seed"]
    channel = DemoChannel.from_local_model_key(_amplify(corrected, seed, output), peer.session_id)
    if receive_encrypted(peer, channel) != b"bb84-network-key-confirm-v1":
        raise AuthenticationError("Khóa ứng dụng không khớp")
    peer.send({"kind": "ready", "accepted": True})
    event("key", "Khóa ứng dụng đã khớp; sẵn sàng nhận", **stats)
    return channel, stats
