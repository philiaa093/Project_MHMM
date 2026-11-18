"""Educational Cascade and Toeplitz; the entropy budget is not a security proof."""

from collections import deque
from dataclasses import dataclass, field
import hashlib
import hmac
import math
import random
import secrets

from bb84_lab.secure_channel import AuthenticationError


CONFIRMATION_BITS = 257
SAFETY_BITS = 64


def pack_bits(bits):
    if any(type(bit) is not int or bit not in (0, 1) for bit in bits):
        raise ValueError("Expected binary bits")
    value = 0
    for bit in bits:
        value = (value << 1) | bit
    padding = (-len(bits)) % 8
    return (value << padding).to_bytes((len(bits) + 7) // 8, "big")


def toeplitz_bits(bits, seed, output_bits):
    """T[i,j] = seed[n-1+i-j], using integer bit parity for each row."""
    if type(output_bits) is not int or output_bits < 1 or not bits:
        raise ValueError("Toeplitz dimensions must be positive")
    if len(seed) != len(bits) + output_bits - 1:
        raise ValueError("Wrong Toeplitz seed length")
    pack_bits(bits)
    pack_bits(seed)
    vector = int("".join(map(str, bits)), 2)
    seed_value = int("".join(map(str, reversed(seed))), 2)
    mask = (1 << len(bits)) - 1
    return tuple((vector & ((seed_value >> row) & mask)).bit_count() % 2
                 for row in range(output_bits))


def key_budget(length, q_upper, parity_leak, confirmation_leak=CONFIRMATION_BITS):
    if type(length) is not int or length < 0:
        raise ValueError("Invalid retained length")
    if type(q_upper) not in (int, float) or not math.isfinite(q_upper) or not 0 <= q_upper <= 1:
        raise ValueError("Invalid public QBER bound")
    for value in (parity_leak, confirmation_leak):
        if type(value) is not int or value < 0:
            raise ValueError("Invalid leakage count")
    if q_upper >= .5:
        return 0, 0
    entropy = 0 if q_upper == 0 else -q_upper * math.log2(q_upper) - (1 - q_upper) * math.log2(1 - q_upper)
    # ponytail: a declared educational entropy assumption, not finite-key QKD.
    # Replace with a full compatible phase-error/finite-key proof for real QKD.
    assumed_entropy = math.floor(length * (1 - entropy))
    output_bits = max(0, assumed_entropy - parity_leak - confirmation_leak - SAFETY_BITS) // 8 * 8
    return assumed_entropy, output_bits


def reconcile(alice_bits, bob_bits, qber, exchange, seed=None, passes=4):
    """Correct Bob only through authenticated public parity queries and lookback."""
    if len(alice_bits) != len(bob_bits) or not alice_bits:
        raise ValueError("Reconciliation needs nonempty equally sized bit strings")
    pack_bits(alice_bits)
    pack_bits(bob_bits)
    if type(qber) not in (int, float) or not math.isfinite(qber) or not 0 <= qber <= .5:
        raise ValueError("Invalid QBER estimate")
    if type(passes) is not int or not 1 <= passes <= 8:
        raise ValueError("Invalid pass count")
    length = len(alice_bits)
    corrected = list(bob_bits)
    seed = secrets.randbits(128) if seed is None else seed
    if type(seed) is not int or seed < 0:
        raise ValueError("Invalid public permutation seed")
    received = exchange("alice", {"kind": "cascade-config-v1", "seed": seed, "passes": passes})
    if received != {"kind": "cascade-config-v1", "seed": seed, "passes": passes}:
        raise AuthenticationError("Cascade configuration differs")
    rng = random.Random(seed)
    block_size = min(length, 128 if qber == 0 else max(1, math.floor(.73 / qber)))
    blocks = []
    memberships = [[] for _ in range(length)]
    leakage = corrections = queries = 0

    def odd(indices):
        nonlocal leakage, queries
        query = queries
        queries += 1
        a_parity = sum(alice_bits[index] for index in indices) % 2
        b_parity = sum(corrected[index] for index in indices) % 2
        a_payload = {"kind": "cascade-parity-v1", "query": query,
                     "indices": list(indices), "parity": a_parity}
        b_payload = {"kind": "cascade-parity-v1", "query": query,
                     "indices": list(indices), "parity": b_parity}
        received_a = exchange("alice", a_payload)
        received_b = exchange("bob", b_payload)
        if received_a != a_payload or received_b != b_payload:
            raise AuthenticationError("Parity transcript differs")
        leakage += 2  # Both parties disclose a parity, including repeated queries.
        return received_a["parity"] != received_b["parity"]

    for pass_index in range(passes):
        permutation = list(range(length))
        if pass_index:
            rng.shuffle(permutation)
        size = min(length, block_size * 2**pass_index)
        current = []
        for start in range(0, length, size):
            indices = tuple(permutation[start:start + size])
            block_id = len(blocks)
            blocks.append(indices)
            current.append(block_id)
            for index in indices:
                memberships[index].append(block_id)
        pending = deque(current)
        queued = set(current)
        while pending:
            block_id = pending.popleft()
            queued.remove(block_id)
            indices = blocks[block_id]
            if not odd(indices):
                continue
            while len(indices) > 1:
                middle = len(indices) // 2
                left = indices[:middle]
                indices = left if odd(left) else indices[middle:]
            position = indices[0]
            corrected[position] ^= 1
            corrections += 1
            if corrections > 2 * length:
                raise ValueError("Cascade correction limit exceeded")
            for affected in memberships[position]:
                if affected != block_id and affected not in queued:
                    pending.append(affected)
                    queued.add(affected)
    return tuple(corrected), leakage, corrections


@dataclass(frozen=True)
class PostprocessResult:
    status: str
    reason: str
    retained_bits: int = 0
    corrected_errors: int = 0
    parity_leak_bits: int = 0
    confirmation_leak_bits: int = 0
    entropy_budget_bits: int = 0
    output_bits: int = 0
    key_match: bool = False
    _alice_key: bytes | None = field(default=None, repr=False)
    _bob_key: bytes | None = field(default=None, repr=False)

    def public_summary(self):
        return {name: getattr(self, name) for name in (
            "status", "reason", "retained_bits", "corrected_errors", "parity_leak_bits",
            "confirmation_leak_bits", "entropy_budget_bits", "output_bits", "key_match",
        )}


def postprocess(transmission, evaluation, decision, alice_auth, bob_auth, *,
                reconciliation_seed=None, reconciliation_passes=4, tamper_parity=False):
    if decision["status"] != "continue":
        return PostprocessResult("skipped", "Phiên không đủ điều kiện hậu xử lý")
    if decision["ci_high"] >= .5:
        return PostprocessResult("insufficient_key", "Cận lỗi không cho ngân sách entropy dương")
    if evaluation.config != transmission.config:
        # evaluate supports paired alpha; physical parameters must still match.
        for field_name in ("signals", "eve_fraction", "noise_probability", "seed"):
            if getattr(evaluation.config, field_name) != getattr(transmission.config, field_name):
                raise ValueError("Evaluation does not belong to transmission")
    positions = [transmission.sifted_indices[index] for index in evaluation.retained_indices]
    alice_bits = tuple(transmission.alice_bits[index] for index in positions)
    bob_bits = tuple(transmission.bob_bits[index] for index in positions)
    length = len(positions)
    if not length:
        return PostprocessResult("insufficient_key", "Không còn bit sau loại mẫu")
    if reconciliation_seed is None:
        domain = f"bb84-cascade-v1:{evaluation.config.seed}:{evaluation.config.sample_fraction}"
        reconciliation_seed = int.from_bytes(hashlib.sha256(domain.encode("ascii")).digest()[:16], "big")
    tampered = False

    def exchange(sender, payload):
        nonlocal tampered
        sender_auth, receiver_auth = (alice_auth, bob_auth) if sender == "alice" else (bob_auth, alice_auth)
        envelope = sender_auth.seal(sender, payload)
        if tamper_parity and not tampered and payload["kind"] == "cascade-parity-v1":
            from dataclasses import replace
            envelope = replace(envelope, payload={**payload, "parity": 1 - payload["parity"]})
            tampered = True
        return receiver_auth.receive(envelope)

    corrected, leak, corrections = reconcile(
        alice_bits, bob_bits, decision["qber"], exchange,
        seed=reconciliation_seed, passes=reconciliation_passes,
    )
    context = b"bb84-model/confirm/v1\0" + alice_auth.session_id.encode() + length.to_bytes(8, "big")
    alice_tag = hashlib.sha256(context + pack_bits(alice_bits)).hexdigest()
    bob_tag = hashlib.sha256(context + pack_bits(corrected)).hexdigest()
    received = exchange("alice", {"kind": "key-confirm-v1", "digest": alice_tag})
    matches = hmac.compare_digest(received["digest"], bob_tag)
    acknowledgement = exchange("bob", {"kind": "key-confirm-ack-v1", "accepted": matches})
    stats = dict(retained_bits=length, corrected_errors=corrections,
                 parity_leak_bits=leak, confirmation_leak_bits=CONFIRMATION_BITS)
    if not acknowledgement["accepted"]:
        return PostprocessResult("failed", "Xác nhận khóa thất bại; hủy phiên", **stats)
    entropy, output_length = key_budget(length, decision["ci_high"], leak)
    stats["entropy_budget_bits"] = entropy
    if output_length < 256:
        return PostprocessResult("insufficient_key", "Ngân sách mô hình không đủ 256 bit", **stats)
    seed_length = length + output_length - 1
    seed_bytes = secrets.token_bytes((seed_length + 7) // 8)
    seed_bits = tuple((seed_bytes[index // 8] >> (7 - index % 8)) & 1 for index in range(seed_length))
    received = exchange("alice", {"kind": "toeplitz-seed-v1", "seed": seed_bytes.hex(),
                                  "seed_bits": seed_length, "output_bits": output_length})
    if received != {"kind": "toeplitz-seed-v1", "seed": seed_bytes.hex(),
                    "seed_bits": seed_length, "output_bits": output_length}:
        raise AuthenticationError("Toeplitz configuration differs")
    alice_output = pack_bits(toeplitz_bits(alice_bits, seed_bits, output_length))
    bob_output = pack_bits(toeplitz_bits(corrected, seed_bits, output_length))
    if not hmac.compare_digest(alice_output, bob_output):
        return PostprocessResult("failed", "Khóa đầu ra khác nhau; hủy phiên", **stats)
    return PostprocessResult("ready", "Hoàn tất hậu xử lý giáo dục", **stats,
                             output_bits=output_length, key_match=True,
                             _alice_key=alice_output[:32], _bob_key=bob_output[:32])
