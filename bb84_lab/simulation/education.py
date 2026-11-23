"""Explicit public lessons and ephemeral packet inspection for the local UI."""

from collections import OrderedDict
from dataclasses import dataclass, field, replace
import hashlib
import hmac
import secrets
from threading import Lock
import time

from bb84_lab.core.bb84 import Config, evaluate, simulate
from bb84_lab.core.secure_channel import AuthenticationError, ReplayError


LESSON_SCENARIOS = {"clean": (0, 0), "eve": (1, 0), "noise": (0, .1), "weak": (.1, 0)}


def lesson_session(scenario="clean", seed=2026):
    """Run the shared simulator on 16 public signals; never invoke postprocessing."""
    if type(scenario) is not str or scenario not in LESSON_SCENARIOS:
        raise ValueError("Unknown teaching scenario")
    if type(seed) is not int or not 0 <= seed <= 2**63 - 1:
        raise ValueError("Invalid teaching seed")
    f, p = LESSON_SCENARIOS[scenario]
    domain_seed = int.from_bytes(hashlib.sha256(f"bb84-public-lesson:{seed}".encode()).digest()[:8])
    config = Config(signals=16, eve_fraction=f, noise_probability=p, seed=domain_seed)
    rows = []
    transmission = simulate(config, trace=rows)
    evaluation = evaluate(transmission, config)
    samples = {transmission.sifted_indices[i] for i in evaluation.sample_indices}
    retained = {transmission.sifted_indices[i] for i in evaluation.retained_indices}
    states = {(0, 0): "|0⟩", (1, 0): "|1⟩", (0, 1): "|+⟩", (1, 1): "|−⟩"}
    for row in rows:
        row["state"] = states[row["alice_bit"], row["alice_basis"]]
        row["sifted"] = row["alice_basis"] == row["bob_basis"]
        row["sampled"] = row["index"] in samples
        row["retained"] = row["index"] in retained
        row["error"] = row["alice_bit"] != row["bob_bit"]
        one = float(row["sent_bit"]) if row["sent_basis"] == row["bob_basis"] else .5
        row["bob_probabilities"] = [1 - one, one]
    summary = evaluation.public_summary()
    summary["seed"] = str(domain_seed)  # Keep all 64 bits exact in JavaScript/JSON readers.
    return {"kind": "public-bb84-lesson-v1", "scenario": scenario, "seed": seed,
            "signals": rows, "summary": summary,
            "key_released": False, "application_key_material": False,
            "scope": "16 tín hiệu công khai cho bài học; không tạo khóa ứng dụng. "
                     "Xác suất đo là lý thuyết trước lỗi bit nền, không phải histogram thực nghiệm."}


@dataclass(repr=False)
class _Inspection:
    channel: object = field(repr=False)
    packet: object = field(repr=False)
    plaintext_digest: bytes = field(repr=False)
    expires: float
    received: bool = False


class PacketInspector:
    """Bounded, locked, memory-only channels. Plaintext is not retained."""

    def __init__(self, *, capacity=32, ttl=600, clock=time.monotonic):
        if type(capacity) is not int or capacity < 1 or type(ttl) not in (int, float) or not 0 < ttl < float("inf"):
            raise ValueError("Invalid inspection limits")
        self._capacity, self._ttl, self._clock = capacity, ttl, clock
        self._items = OrderedDict()
        self._lock = Lock()

    def _prune(self):
        now = self._clock()
        for token in [key for key, item in self._items.items() if item.expires <= now]:
            del self._items[token]

    def create(self, channel, message):
        if type(message) is not str or len(message.encode("utf-8")) > 16384:
            raise ValueError("Invalid inspection message")
        plaintext = message.encode("utf-8")
        packet = channel.encrypt(plaintext)
        aad = channel._aad(packet.version, packet.session_id, packet.sender, packet.sequence)
        token = secrets.token_urlsafe(32)
        with self._lock:
            self._prune()
            while len(self._items) >= self._capacity:
                self._items.popitem(last=False)
            self._items[token] = _Inspection(channel, packet, hashlib.sha256(plaintext).digest(),
                                             self._clock() + self._ttl)
        ciphertext = packet.ciphertext[:-16]
        return {"token": token, "expires_in_seconds": self._ttl, "session_id": packet.session_id,
                "algorithm": "ChaCha20-Poly1305", "key_source": channel.key_source,
                "key_bytes": 32, "nonce_hex": packet.sequence.to_bytes(12, "big").hex(),
                "nonce_bytes": 12, "sequence": packet.sequence, "aad_text": aad.decode("utf-8"),
                "aad_bytes": len(aad), "plaintext_bytes": len(plaintext),
                "ciphertext_body_bytes": len(ciphertext), "ciphertext_bytes": len(packet.ciphertext),
                "ciphertext_preview_hex": ciphertext[:128].hex(), "preview_bytes": min(128, len(ciphertext)),
                "preview_truncated": len(ciphertext) > 128, "tag_hex": packet.ciphertext[-16:].hex(),
                "tag_bytes": 16, "ciphertext_sha256": hashlib.sha256(packet.ciphertext).hexdigest(),
                "received": False}

    def act(self, token, action):
        if type(token) is not str or not 20 <= len(token) <= 100 or action not in ("decrypt", "tamper", "replay"):
            raise ValueError("Invalid packet action")
        with self._lock:
            self._prune()
            item = self._items.get(token)
            if item is None:
                raise KeyError("Inspection expired or evicted")
            if action == "tamper":
                if item.received:
                    raise ValueError("Create a new packet before testing tampering")
                damaged = bytes([item.packet.ciphertext[0] ^ 1]) + item.packet.ciphertext[1:]
                try:
                    item.channel.decrypt(replace(item.packet, ciphertext=damaged))
                except ReplayError:
                    raise AssertionError("A fresh tamper test was rejected as replay") from None
                except AuthenticationError:
                    return {"action": action, "status": "rejected", "reason": "invalid_tag",
                            "received": False, "changed_offset": 0,
                            "changed_part": "ciphertext" if len(damaged) > 16 else "tag",
                            "original_byte": f"{item.packet.ciphertext[0]:02x}",
                            "changed_byte": f"{damaged[0]:02x}",
                            "changed_preview_hex": damaged[:min(128, len(damaged))].hex(),
                            "plaintext_released": False}
                raise AssertionError("Modified ciphertext was accepted")
            if action == "replay" and not item.received:
                raise ValueError("Deliver the original packet before replaying it")
            try:
                recovered = item.channel.decrypt(item.packet)
            except ReplayError:
                return {"action": action, "status": "rejected", "reason": "replay",
                        "received": item.received, "plaintext_released": False}
            if action == "replay":
                raise AssertionError("Replayed packet was accepted")
            if not hmac.compare_digest(hashlib.sha256(recovered).digest(), item.plaintext_digest):
                raise AssertionError("Recovered message differs")
            item.received = True
            return {"action": action, "status": "accepted", "received": True,
                    "plaintext": recovered.decode("utf-8"), "plaintext_bytes": len(recovered),
                    "roundtrip_ok": True, "plaintext_released": True}
