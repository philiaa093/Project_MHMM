"""Thống kê BB84, tiêu chí chọn tỷ lệ mẫu và đối sánh ghép cặp."""

import hashlib
import itertools
import random
import statistics

from bb84_lab.core.bb84 import expected_qber, wilson_interval

EVE_FRACTIONS = (0, .1, .25, .5, 1)
COMPARISON_NOISE = (0, .01, .03)
SAMPLE_FRACTIONS = (.1, .25, .5)
BASELINE = .25
CRITERIA = {
    "strong_detection_min": .95, "detection_drop_max": .05,
    "no_eve_alarm_max": .05, "no_eve_inconclusive_max": .10,
    "y_pre_relative_gain_min": .05,
}


def summarize(rows):
    groups = {}
    for row in rows:
        key = tuple(row[field] for field in (
            "signals", "eve_fraction", "noise_probability", "sample_fraction",
        ))
        groups.setdefault(key, []).append(row)
    summaries = []
    for (n, f, p, alpha), group in sorted(groups.items()):
        count = len(group)
        qbers = [row["qber"] for row in group if row["qber"] is not None]
        item = {
            "signals": n, "eve_fraction": f, "noise_probability": p,
            "sample_fraction": alpha, "sessions": count,
            "expected_qber": expected_qber(f, p),
            "qber_observations": len(qbers),
            "qber_mean": statistics.mean(qbers) if qbers else None,
            "qber_stdev": statistics.stdev(qbers) if len(qbers) > 1 else None,
            "sifted_mean": statistics.mean(row["sifted_count"] for row in group),
            "remaining_mean": statistics.mean(row["remaining_count"] for row in group),
            "y_pre_mean": statistics.mean(row["y_pre"] for row in group),
        }
        for status in ("continue", "anomalous", "inconclusive"):
            total = sum(row["status"] == status for row in group)
            item[f"{status}_count"] = total
            item[f"{status}_rate"] = total / count
            item[f"{status}_ci95"] = wilson_interval(total, count)
        item["abort_rate"] = 1 - item["continue_rate"]
        item["eve_not_flagged_count"] = count - item["anomalous_count"] if f > 0 else None
        summaries.append(item)
    return summaries


def assess_candidates(summary):
    """Predeclared empirical gates; estimates are not security guarantees."""
    lookup = {(row["eve_fraction"], row["noise_probability"], row["sample_fraction"]): row for row in summary}
    expected = set(itertools.product(EVE_FRACTIONS, COMPARISON_NOISE, SAMPLE_FRACTIONS))
    if set(lookup) != expected:
        raise ValueError("Thiếu hoặc trùng cấu hình đối sánh")
    if len(summary) != len(expected):
        raise ValueError("Trùng cấu hình đối sánh")
    baseline_mean = statistics.mean(lookup[(0, p, BASELINE)]["y_pre_mean"] for p in (0, .01))
    candidates = []
    for alpha in SAMPLE_FRACTIONS:
        strong_min = min(lookup[(f, p, alpha)]["anomalous_rate"]
                         for f in (.5, 1) for p in COMPARISON_NOISE)
        detection_drop = max(lookup[(f, p, BASELINE)]["anomalous_rate"] - lookup[(f, p, alpha)]["anomalous_rate"]
                             for f in EVE_FRACTIONS if f > 0 for p in COMPARISON_NOISE)
        alarm = max(lookup[(0, p, alpha)]["anomalous_rate"] for p in (0, .01))
        inconclusive = max(lookup[(0, p, alpha)]["inconclusive_rate"] for p in (0, .01))
        yield_mean = statistics.mean(lookup[(0, p, alpha)]["y_pre_mean"] for p in (0, .01))
        gain = yield_mean / baseline_mean - 1 if baseline_mean > 0 else None
        checks = {
            "strong_detection": strong_min >= CRITERIA["strong_detection_min"],
            "detection_noninferiority": detection_drop <= CRITERIA["detection_drop_max"] + 1e-12,
            "no_eve_alarm": alarm <= CRITERIA["no_eve_alarm_max"],
            "no_eve_inconclusive": inconclusive <= CRITERIA["no_eve_inconclusive_max"],
            "y_pre_gain": gain is not None and gain >= CRITERIA["y_pre_relative_gain_min"],
        }
        candidates.append({
            "sample_fraction": alpha, "checks": checks, "eligible": all(checks.values()),
            "strong_detection_min": strong_min, "detection_drop_max": detection_drop,
            "no_eve_alarm_max": alarm, "no_eve_inconclusive_max": inconclusive,
            "y_pre_mean_no_eve_low_noise": yield_mean, "relative_gain": gain,
        })
    return candidates


def select_fraction(summary):
    candidates = assess_candidates(summary)
    eligible = [row for row in candidates if row["eligible"] and row["sample_fraction"] != BASELINE]
    if eligible:
        chosen = max(eligible, key=lambda row: row["y_pre_mean_no_eve_low_noise"])
        selected = chosen["sample_fraction"]
        reason = "Ứng viên đạt các mục tiêu quan sát trên bộ hiệu chỉnh"
    else:
        selected = BASELINE
        reason = "Chưa tìm được ứng viên cải thiện đạt đủ tiêu chí; giữ B0"
    return {"selected_fraction": selected, "baseline_fraction": BASELINE,
            "criteria": CRITERIA, "candidates": candidates, "reason": reason,
            "selection_dataset": "calibration", "frozen_before_evaluation": True}


def _quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def paired_differences(rows, bootstrap_seed=1701, bootstrap_repeats=2000):
    if type(bootstrap_seed) is not int or bootstrap_seed < 0:
        raise ValueError("bootstrap_seed phải là số nguyên không âm")
    if type(bootstrap_repeats) is not int or bootstrap_repeats < 1:
        raise ValueError("bootstrap_repeats phải là số nguyên dương")
    if not rows:
        raise ValueError("Thiếu dữ liệu ghép cặp")
    sessions = {}
    for row in rows:
        key = row["session_id"]
        by_alpha = sessions.setdefault(key, {})
        if row["sample_fraction"] in by_alpha:
            raise ValueError("Phương án ghép cặp bị lặp")
        by_alpha[row["sample_fraction"]] = row
    differences = []
    groups = {}
    for session_id, by_alpha in sessions.items():
        if set(by_alpha) != set(SAMPLE_FRACTIONS):
            raise ValueError("Thiếu phương án trong một phiên ghép cặp")
        base = by_alpha[BASELINE]
        for alpha in SAMPLE_FRACTIONS:
            row = by_alpha[alpha]
            if any(row[name] != base[name] for name in ("seed", "signals", "eve_fraction", "noise_probability", "sifted_count")):
                raise ValueError("Các phương án không cùng phiên mô phỏng")
            difference = row["y_pre"] - base["y_pre"]
            item = {"session_id": session_id, "seed": row["seed"],
                    "eve_fraction": row["eve_fraction"], "noise_probability": row["noise_probability"],
                    "sample_fraction": alpha, "y_pre": row["y_pre"], "baseline_y_pre": base["y_pre"],
                    "y_pre_difference": difference}
            differences.append(item)
            groups.setdefault((row["eve_fraction"], row["noise_probability"], alpha), []).append(difference)
    summary = []
    for (f, p, alpha), values in sorted(groups.items()):
        seed_bytes = hashlib.sha256(f"paired:{bootstrap_seed}:{f}:{p}:{alpha}".encode()).digest()
        rng = random.Random(seed_bytes)
        if len(set(values)) == 1:
            interval = [float(values[0]), float(values[0])]
        else:
            means = [statistics.mean(rng.choices(values, k=len(values))) for _ in range(bootstrap_repeats)]
            interval = [_quantile(means, .025), _quantile(means, .975)]
        summary.append({
            "eve_fraction": f, "noise_probability": p, "sample_fraction": alpha,
            "pairs": len(values), "mean_difference": statistics.mean(values),
            "ci95": interval, "minimum": min(values), "q25": _quantile(values, .25),
            "median": _quantile(values, .5), "q75": _quantile(values, .75), "maximum": max(values),
            "inference": "Y_pre tăng trong mô hình" if interval[0] > 0 else "Chưa đủ bằng chứng về cải thiện",
            "method": "paired percentile bootstrap of session means; 95% descriptive interval",
        })
    return differences, summary
