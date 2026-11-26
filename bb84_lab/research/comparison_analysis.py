"""Aggregate operational comparison; independent protocols, paired E91 ablation."""

import hashlib
import random
import statistics

from bb84_lab.core.bb84 import wilson_interval
from bb84_lab.research.analysis import _quantile


GROUP_FIELDS = ("experiment", "budget_mode", "budget", "protocol", "policy",
                "disturbance_fraction", "noise_probability")
RATE_FIELDS = ("alarm", "monitor_pass", "aborted", "not_flagged", "missed_intervention",
               "intervention_key_released", "false_alarm", "no_intervention_alarm", "ready", "aead_verified")
MEAN_FIELDS = ("signals", "sifted_bits", "sample_bits", "retained_bits", "bell_pairs",
               "qber", "chsh_abs_s", "corrected_errors", "parity_leak_bits",
               "confirmation_leak_bits", "entropy_budget_bits", "y_final",
               "monitor_public_outcome_bits", "total_public_outcome_bits",
               "monitor_public_json_bytes", "postprocess_public_json_bytes",
               "simulation_seconds", "monitoring_seconds", "postprocessing_seconds",
               "key_setup_seconds", "bell_calculation_seconds")


def mean_interval(values, seed, repeats):
    """Descriptive percentile bootstrap of independent session means."""
    if not values:
        return None
    if len(set(values)) == 1:
        return [float(values[0]), float(values[0])]
    rng = random.Random(seed)
    draws = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(repeats))
    return [_quantile(draws, .025), _quantile(draws, .975)]


def summarize(rows, bootstrap_seed=1701, bootstrap_repeats=1000):
    groups = {}
    for row in rows:
        groups.setdefault(tuple(row[name] for name in GROUP_FIELDS), []).append(row)
    summary = []
    for key, group in sorted(groups.items()):
        item = dict(zip(GROUP_FIELDS, key))
        item["sessions"] = len(group)
        for field in RATE_FIELDS:
            applicable = not ((field in ("not_flagged", "missed_intervention", "intervention_key_released")
                               and not item["disturbance_fraction"])
                              or (field in ("false_alarm", "no_intervention_alarm") and item["disturbance_fraction"])
                              or (field == "false_alarm" and group[0]["expected_qber"] > group[0]["threshold"]))
            count = sum(row[field] for row in group)
            item[field + "_count"] = count if applicable else None
            item[field + "_rate"] = count / len(group) if applicable else None
            item[field + "_ci95"] = wilson_interval(count, len(group)) if applicable else None
        for field in MEAN_FIELDS:
            values = [row[field] for row in group if row[field] is not None]
            item[field + "_mean"] = statistics.fmean(values) if values else None
        values = [row["y_final"] for row in group]
        seed = hashlib.sha256(repr((bootstrap_seed, key)).encode()).digest()
        item["y_final_ci95"] = mean_interval(values, seed, bootstrap_repeats)
        successful = [row["y_final"] for row in group if row["ready"]]
        item["y_final_given_ready_mean"] = statistics.fmean(successful) if successful else None
        for field in ("after_cascade_bits", "after_confirmation_bits"):
            item[field + "_per_attempt_mean"] = statistics.fmean(row[field] or 0 for row in group)
        item["y_final_per_signal"] = sum(values) / sum(row["signals"] for row in group)
        item["y_final_per_endpoint_measurement"] = sum(values) / sum(row["endpoint_measurements"] for row in group)
        for field in ("monitor_status", "qber_status", "bell_status", "postprocess_status"):
            item[field + "_counts"] = {value: sum(row[field] == value for row in group)
                                        for value in sorted({row[field] for row in group})}
        summary.append(item)
    return summary


def ablation_summary(rows):
    sessions = {}
    for row in rows:
        if row["protocol"] == "e91":
            sessions.setdefault(row["session_id"], {})[row["policy"]] = row
    groups = {}
    for session_id, policies in sessions.items():
        if set(policies) != {"qber_chsh", "qber_only_ablation"}:
            raise ValueError("E91 ablation requires both policies on the same measurements")
        full, qber = policies["qber_chsh"], policies["qber_only_ablation"]
        for field in ("seed", "signals", "sifted_bits", "sample_bits", "sample_errors", "retained_bits"):
            if full[field] != qber[field]:
                raise ValueError("Ablation measurement mismatch")
        if full["ready"] and (not qber["ready"] or full["y_final"] != qber["y_final"]):
            raise AssertionError("Additional CHSH gate unexpectedly improved same-session output")
        key = tuple(full[name] for name in ("experiment", "budget_mode", "budget", "disturbance_fraction", "noise_probability"))
        groups.setdefault(key, []).append((full, qber))
    return [{**dict(zip(("experiment", "budget_mode", "budget", "disturbance_fraction", "noise_probability"), key)),
             "paired_sessions": len(pairs),
             "additional_monitor_aborts": sum(q["monitor_pass"] and not f["monitor_pass"] for f, q in pairs),
             "additional_key_aborts": sum(q["ready"] and not f["ready"] for f, q in pairs),
             "mean_y_final_change": statistics.fmean(f["y_final"] - q["y_final"] for f, q in pairs),
             "chsh_blocked_despite_qber_pass": sum(q["monitor_pass"] and f["bell_status"] != "violation" for f, q in pairs)}
            for key, pairs in sorted(groups.items())]
