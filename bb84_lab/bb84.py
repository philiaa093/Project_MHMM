"""Classical BB84 Monte Carlo and public-sample QBER monitoring; no key output."""

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import math
import random


def _integer(name: str, value: int, minimum: int) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def _probability(name: str, value: float) -> None:
    if type(value) not in (int, float) or not 0 <= value <= 1:
        raise ValueError(f"{name} must be finite and between 0 and 1")


@dataclass(frozen=True)
class Config:
    signals: int = 4096
    eve_fraction: float = 0.0
    noise_probability: float = 0.0
    sample_fraction: float = 0.25
    threshold: float = 0.05
    min_samples: int = 100
    seed: int = 2026

    def __post_init__(self) -> None:
        _integer("signals", self.signals, 1)
        _integer("min_samples", self.min_samples, 1)
        _integer("seed", self.seed, 0)
        for name in ("eve_fraction", "noise_probability", "sample_fraction", "threshold"):
            _probability(name, getattr(self, name))


@dataclass(frozen=True)
class Transmission:
    config: Config
    alice_bits: tuple[int, ...] = field(repr=False)
    bob_bits: tuple[int, ...] = field(repr=False)
    alice_bases: tuple[int, ...] = field(repr=False)
    bob_bases: tuple[int, ...] = field(repr=False)
    sifted_indices: tuple[int, ...] = field(repr=False)
    sample_order: tuple[int, ...] = field(repr=False)


@dataclass(frozen=True)
class Evaluation:
    config: Config
    signals: int
    sifted_count: int
    sample_count: int
    sample_errors: int
    qber: float | None
    ci_low: float | None
    ci_high: float | None
    status: str
    reason: str
    remaining_count: int
    y_pre: int
    sample_indices: tuple[int, ...] = field(repr=False)
    retained_indices: tuple[int, ...] = field(repr=False)
    _transmission: Transmission = field(repr=False)

    def public_summary(self) -> dict:
        summary = asdict(self.config)
        for name in (
            "sifted_count", "sample_count", "sample_errors", "qber", "ci_low",
            "ci_high", "status", "reason", "remaining_count", "y_pre",
        ):
            summary[name] = getattr(self, name)
        return summary

    def public_transcript(self) -> dict:
        """Only bases and disclosed sample bits; authenticate before accepting them."""
        transmission = self._transmission
        positions = [transmission.sifted_indices[i] for i in self.sample_indices]
        return {
            "kind": "bb84-sample-v1",
            "signals": self.signals,
            "sample_fraction": self.config.sample_fraction,
            "threshold": self.config.threshold,
            "min_samples": self.config.min_samples,
            "alice_bases": list(transmission.alice_bases),
            "bob_bases": list(transmission.bob_bases),
            "sample_indices": list(self.sample_indices),
            "sample_alice_bits": [transmission.alice_bits[i] for i in positions],
            "sample_bob_bits": [transmission.bob_bits[i] for i in positions],
        }


def expected_qber(eve_fraction: float, noise_probability: float) -> float:
    _probability("eve_fraction", eve_fraction)
    _probability("noise_probability", noise_probability)
    return noise_probability + eve_fraction / 4 - noise_probability * eve_fraction / 2


def wilson_interval(errors: int, total: int) -> tuple[float, float]:
    """Wilson 95% interval for monitoring, not a QKD security parameter."""
    _integer("total", total, 1)
    _integer("errors", errors, 0)
    if errors > total:
        raise ValueError("errors must not exceed total")
    z = 1.959963984540054
    qber = errors / total
    denominator = 1 + z * z / total
    center = (qber + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(qber * (1 - qber) / total + z * z / (4 * total**2)) / denominator
    return max(0.0, center - radius), min(1.0, center + radius)


def monitor(
    sample_errors: int, sample_count: int, threshold: float = 0.05, min_samples: int = 100,
) -> dict:
    """Decide using public sample statistics only; never use Eve/noise labels."""
    _integer("sample_count", sample_count, 0)
    _integer("sample_errors", sample_errors, 0)
    _integer("min_samples", min_samples, 1)
    _probability("threshold", threshold)
    if sample_errors > sample_count:
        raise ValueError("sample_errors must not exceed sample_count")
    qber = sample_errors / sample_count if sample_count else None
    low, high = wilson_interval(sample_errors, sample_count) if sample_count else (None, None)
    if sample_count < min_samples:
        status, reason = "inconclusive", "insufficient_samples"
    elif high <= threshold:
        status, reason = "continue", "upper_bound_at_or_below_threshold"
    elif low > threshold:
        status, reason = "anomalous", "lower_bound_above_threshold"
    else:
        status, reason = "inconclusive", "interval_crosses_threshold"
    return {
        "sample_count": sample_count, "sample_errors": sample_errors, "qber": qber,
        "ci_low": low, "ci_high": high, "status": status, "reason": reason,
    }


def simulate(config: Config) -> Transmission:
    if not isinstance(config, Config):
        raise TypeError("config must be a Config")
    rng = random.Random(config.seed)
    alice_bits = []
    bob_bits = []
    alice_bases = []
    bob_bases = []
    # ponytail: independent-signal Monte Carlo, checked by verify_quantum.py;
    # add a defined physical channel model before studying device-level noise.
    # Public seeds are for reproducible research, never for generating secret keys.
    for _ in range(config.signals):
        alice_bit, alice_basis, bob_basis = (rng.getrandbits(1) for _ in range(3))
        sent_bit, sent_basis = alice_bit, alice_basis
        if rng.random() < config.eve_fraction:
            eve_basis = rng.getrandbits(1)
            sent_bit = alice_bit if eve_basis == alice_basis else rng.getrandbits(1)
            sent_basis = eve_basis
        bob_bit = sent_bit if bob_basis == sent_basis else rng.getrandbits(1)
        bob_bit ^= int(rng.random() < config.noise_probability)
        alice_bits.append(alice_bit)
        bob_bits.append(bob_bit)
        alice_bases.append(alice_basis)
        bob_bases.append(bob_basis)
    sifted = tuple(i for i in range(config.signals) if alice_bases[i] == bob_bases[i])
    order = list(range(len(sifted)))
    sample_seed = sha256(f"bb84-sample:{config.seed}".encode("ascii")).digest()
    random.Random(sample_seed).shuffle(order)
    return Transmission(
        config, tuple(alice_bits), tuple(bob_bits), tuple(alice_bases),
        tuple(bob_bases), sifted, tuple(order),
    )


def evaluate(transmission: Transmission, config: Config) -> Evaluation:
    if not isinstance(transmission, Transmission) or not isinstance(config, Config):
        raise TypeError("expected Transmission and Config")
    for name in ("signals", "eve_fraction", "noise_probability", "seed"):
        if getattr(transmission.config, name) != getattr(config, name):
            raise ValueError(f"{name} differs from the simulated transmission")
    sifted_count = len(transmission.sifted_indices)
    sample_count = math.floor(config.sample_fraction * sifted_count)
    sample_indices = transmission.sample_order[:sample_count]
    sample_set = set(sample_indices)
    retained = tuple(i for i in range(sifted_count) if i not in sample_set)
    errors = sum(
        transmission.alice_bits[transmission.sifted_indices[i]]
        != transmission.bob_bits[transmission.sifted_indices[i]]
        for i in sample_indices
    )
    decision = monitor(errors, sample_count, config.threshold, config.min_samples)
    remaining = len(retained)
    return Evaluation(
        config, config.signals, sifted_count, sample_count, errors, decision["qber"],
        decision["ci_low"], decision["ci_high"], decision["status"], decision["reason"],
        remaining, remaining if decision["status"] == "continue" else 0,
        sample_indices, retained, transmission,
    )


def run_session(config: Config) -> Evaluation:
    return evaluate(simulate(config), config)
