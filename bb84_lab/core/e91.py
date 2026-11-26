"""Classical Monte Carlo of Ekert's singlet measurements, with aggregate output.

Measurement directions are in degrees in a common plane (Ekert, 1991,
Phys. Rev. Lett. 67, 661). Noise probability p mixes the singlet with
white noise, which gives independent, unbiased outcomes on the noisy pairs.
The Bell and key statistics use disjoint sets of measurement directions.
"""

import math
import random

from bb84_lab.core.bb84 import wilson_interval


ALICE_ANGLES = (0, 45, 90)
BOB_ANGLES = (45, 90, 135)
BELL_PAIRS = ((0, 45, 1), (0, 135, -1), (90, 45, 1), (90, 135, 1))
KEY_PAIRS = ((45, 45), (90, 90))
CONFIDENCE_ALPHA = 0.05
BELL_BOUND = 2.0


def _outcome_row(alice_angle, bob_angle, outcomes):
    pp, pm, mp, mm = outcomes
    return {
        "alice_angle": alice_angle, "bob_angle": bob_angle,
        "count": pp + pm + mp + mm, "pp": pp, "pm": pm, "mp": mp, "mm": mm,
    }


def bell_summary(counts):
    """Compute CHSH and its simultaneous interval from observed outcome counts."""
    pairs = []
    for alice_angle, bob_angle, sign in BELL_PAIRS:
        row = _outcome_row(alice_angle, bob_angle, counts[alice_angle, bob_angle])
        support = row["count"]
        correlation = (row["pp"] + row["mm"] - row["pm"] - row["mp"]) / support if support else None
        pairs.append({**row, "sign": sign, "correlation": correlation})

    s = abs_s = ci_low = ci_high = None
    status = "inconclusive"
    if all(pair["count"] for pair in pairs):
        s = lower = upper = 0.0
        # Apply two-sided Hoeffding bounds to four means of numbers in [-1, 1].
        # The union bound gives simultaneous 95% coverage, conditional on counts.
        log_term = 2 * math.log(2 * len(pairs) / CONFIDENCE_ALPHA)
        for pair in pairs:
            signed_correlation = pair["sign"] * pair["correlation"]
            radius = math.sqrt(log_term / pair["count"])
            s += signed_correlation
            lower += max(-1.0, signed_correlation - radius)
            upper += min(1.0, signed_correlation + radius)
        abs_s = abs(s)
        ci_low = 0.0 if lower <= 0.0 <= upper else min(abs(lower), abs(upper))
        ci_high = max(abs(lower), abs(upper))
        if ci_low > BELL_BOUND:
            status = "violation"
        elif ci_high <= BELL_BOUND:
            status = "at_or_below_bound"

    return {
        "pairs": pairs, "s": s, "abs_s": abs_s, "ci_low": ci_low, "ci_high": ci_high,
        "status": status,
    }


def _key_summary(counts, noise_probability):
    pairs = []
    for alice_angle, bob_angle in KEY_PAIRS:
        row = _outcome_row(alice_angle, bob_angle, counts[alice_angle, bob_angle])
        # Equal directions ideally give opposite outcomes. Flip Bob's bit,
        # making original agreements the errors for the sifted key.
        pairs.append({**row, "errors": row["pp"] + row["mm"]})
    count = sum(pair["count"] for pair in pairs)
    errors = sum(pair["errors"] for pair in pairs)
    ci_low, ci_high = wilson_interval(errors, count) if count else (None, None)
    return {
        "pairs": pairs, "count": count, "errors": errors,
        "qber": errors / count if count else None, "ci_low": ci_low, "ci_high": ci_high,
        "expected_qber": noise_probability / 2,
    }


def same_outcome_probability(alice_angle, bob_angle, noise_probability=0.0):
    """Return the probability of equal outcomes at the two spin directions."""
    return (1 - (1 - noise_probability) * math.cos(math.radians(alice_angle - bob_angle))) / 2


def simulate_e91(signals=4096, seed=2026, noise_probability=0.0):
    """Simulate seeded pairs and return aggregate Bell and QBER data for display."""
    if type(signals) is not int or not 1 <= signals <= 65536:
        raise ValueError("Số cặp phải là số nguyên từ 1 đến 65.536.")
    if type(seed) is not int or not 0 <= seed <= 2147483647:
        raise ValueError("Seed phải là số nguyên từ 0 đến 2.147.483.647.")
    if type(noise_probability) not in (int, float) or not 0 <= noise_probability <= 1:
        raise ValueError("Xác suất nhiễu phải là số hữu hạn từ 0 đến 1.")

    rng = random.Random(seed)
    outcomes = {(a, b): [0, 0, 0, 0] for a in ALICE_ANGLES for b in BOB_ANGLES}
    agree = {(a, b): same_outcome_probability(a, b, noise_probability) for a, b in outcomes}
    for _ in range(signals):
        pair = rng.choice(ALICE_ANGLES), rng.choice(BOB_ANGLES)
        # Use 0 for +1 and 1 for -1. Bob shares Alice's unbiased outcome with
        # probability (1 + E)/2, which yields the desired correlation E.
        alice_bit = rng.getrandbits(1)
        bob_bit = alice_bit ^ int(rng.random() >= agree[pair])
        outcomes[pair][2 * alice_bit + bob_bit] += 1

    bell = bell_summary(outcomes)
    bell["expected_s"] = 2 * math.sqrt(2) * (noise_probability - 1)
    key = _key_summary(outcomes, noise_probability)
    return {
        "signals": signals, "seed": seed, "noise_probability": noise_probability,
        "discarded_count": signals - sum(pair["count"] for pair in bell["pairs"]) - key["count"],
        "bell": bell, "key": key,
    }
