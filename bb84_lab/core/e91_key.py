"""Seeded E91 key-material model, with disjoint Bell/sample/retained sets.

Unlike the dashboard's white-noise mixture, p here flips Bob's measured bit,
as in the network implementation. Disturbance replaces a fraction of pairs
with independent outcomes; this is not BB84 intercept/resend.
"""

from dataclasses import dataclass, field
import hashlib
import math
import random

from bb84_lab.core.bb84 import Config, monitor
from bb84_lab.core.e91 import ALICE_ANGLES, BELL_PAIRS, BOB_ANGLES, bell_summary, same_outcome_probability


BELL_DIRECTIONS = tuple((a, b) for a, b, _ in BELL_PAIRS)


@dataclass(frozen=True)
class E91Config:
    signals: int = 8192
    disturbance_fraction: float = 0.0
    noise_probability: float = 0.0
    sample_fraction: float = .25
    threshold: float = .05
    min_samples: int = 100
    seed: int = 2026

    def __post_init__(self):
        Config(self.signals, self.disturbance_fraction, self.noise_probability,
               self.sample_fraction, self.threshold, self.min_samples, self.seed)


@dataclass(frozen=True)
class E91Transmission:
    config: E91Config
    alice_bits: tuple[int, ...] = field(repr=False)
    bob_bits: tuple[int, ...] = field(repr=False)  # already flipped for key agreement
    alice_settings: tuple[int, ...] = field(repr=False)
    bob_settings: tuple[int, ...] = field(repr=False)
    sifted_indices: tuple[int, ...] = field(repr=False)
    sample_order: tuple[int, ...] = field(repr=False)
    bell_indices: tuple[int, ...] = field(repr=False)
    bell: dict


def expected_key_qber(disturbance_fraction, noise_probability):
    E91Config(disturbance_fraction=disturbance_fraction, noise_probability=noise_probability)
    return noise_probability + disturbance_fraction / 2 - noise_probability * disturbance_fraction


def combine_monitoring(qber, bell):
    """The operational E91 gate; no knowledge of noise or attack labels."""
    status, reason = qber["status"], qber["reason"]
    if bell["status"] == "at_or_below_bound":
        status, reason = "chsh_rejected", "chsh_at_or_below_bound"
    elif bell["status"] != "violation":
        status, reason = "chsh_inconclusive", "chsh_insufficient_evidence"
    return {**qber, "status": status, "reason": reason, "bell": bell,
            "qber_status": qber["status"], "qber_reason": qber["reason"]}


def simulate_transmission(config):
    if not isinstance(config, E91Config):
        raise TypeError("config must be E91Config")
    rng = random.Random(config.seed)
    counts = {pair: [0, 0, 0, 0] for pair in BELL_DIRECTIONS}
    agreement = {(a, b): same_outcome_probability(a, b) for a in ALICE_ANGLES for b in BOB_ANGLES}
    alice_bits, bob_bits, alice_settings, bob_settings, sifted, bell_positions = [], [], [], [], [], []
    for index in range(config.signals):
        a, b = rng.choice(ALICE_ANGLES), rng.choice(BOB_ANGLES)
        alice = rng.getrandbits(1)
        bob = (rng.getrandbits(1) if rng.random() < config.disturbance_fraction
               else alice ^ int(rng.random() >= agreement[a, b]))
        bob ^= int(rng.random() < config.noise_probability)
        alice_settings.append(a)
        bob_settings.append(b)
        alice_bits.append(alice)
        bob_bits.append(1 ^ bob)
        if (a, b) in counts:
            counts[a, b][2 * alice + bob] += 1
            bell_positions.append(index)
        elif a == b:
            sifted.append(index)
    order = list(range(len(sifted)))
    random.Random(hashlib.sha256(f"e91-sample:{config.seed}".encode("ascii")).digest()).shuffle(order)
    return E91Transmission(config, tuple(alice_bits), tuple(bob_bits), tuple(alice_settings),
                           tuple(bob_settings), tuple(sifted), tuple(order), tuple(bell_positions), bell_summary(counts))


def evaluate_transmission(transmission):
    config = transmission.config
    sample_count = math.floor(config.sample_fraction * len(transmission.sifted_indices))
    sample = tuple(transmission.sifted_indices[i] for i in transmission.sample_order[:sample_count])
    excluded = set(sample)
    retained = tuple(i for i in transmission.sifted_indices if i not in excluded)
    errors = sum(transmission.alice_bits[i] != transmission.bob_bits[i] for i in sample)
    qber = monitor(errors, sample_count, config.threshold, config.min_samples)
    return combine_monitoring(qber, transmission.bell), sample, retained
