"""Ma trận BB84, hiệu chỉnh rồi đánh giá độc lập theo đề cương §8.5–8.6."""

import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import platform
import statistics
import sys
import time

from bb84_lab.core.bb84 import Config, evaluate, expected_qber, monitor, simulate, wilson_interval
# Re-export the existing analysis symbols for callers of study/experiments.
from bb84_lab.research.analysis import (
    BASELINE, COMPARISON_NOISE, CRITERIA, EVE_FRACTIONS, SAMPLE_FRACTIONS,
    _quantile, assess_candidates, paired_differences, select_fraction, summarize,
)
from bb84_lab.shared.paths import CONFIG_ROOT

SIGNALS = (1024, 4096, 16384)
NOISE_PROBABILITIES = (0, .01, .03, .05)


def load_study_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    names = {"main_seed", "evaluation_seed", "main_repeats", "evaluation_repeats",
             "bootstrap_seed", "bootstrap_repeats"}
    if type(config) is not dict or set(config) != names:
        raise ValueError("Sai trường cấu hình study")
    for name, value in config.items():
        if type(value) is not int or value < (1 if "repeats" in name else 0):
            raise ValueError(f"{name} phải là số nguyên hợp lệ")
    main_end = config["main_seed"] + 60 * config["main_repeats"]
    evaluation_end = config["evaluation_seed"] + 15 * config["evaluation_repeats"]
    if max(config["main_seed"], config["evaluation_seed"]) < min(main_end, evaluation_end):
        raise ValueError("Khoảng seed chính và đánh giá phải rời nhau")
    return config


def _write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def _write_csv(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _row(transmission, config, session_id, repeat, dataset, calibration=False):
    result = evaluate(transmission, config)
    return {
        "session_id": session_id, "repeat": repeat, "dataset": dataset,
        "is_calibration": calibration, **result.public_summary(),
        "expected_qber": expected_qber(config.eve_fraction, config.noise_probability),
    }


def run_study(output, quick=False, plots=True, config_path=None):
    config = load_study_config(config_path or CONFIG_ROOT / "study.json")
    if type(quick) is not bool or type(plots) is not bool:
        raise ValueError("quick và plots phải là bool")
    if quick:
        config.update(main_repeats=2, evaluation_repeats=3, bootstrap_repeats=100)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    start = time.perf_counter()
    manifest = {
        "state": "running", "mode": "smoke" if quick else "full",
        "created_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
        "platform": platform.platform(), "config": config,
        "grid": {"signals": SIGNALS, "eve_fractions": EVE_FRACTIONS,
                 "noise_probabilities": NOISE_PROBABILITIES, "sample_fractions": SAMPLE_FRACTIONS},
        "scope": "Monitoring and Y_pre only; no Y_final or composable QKD claim",
        "pairing": "One transmission and sample permutation per independent session",
        "seed_policy": "Main and evaluation seed ranges are disjoint; calibration is a main subset",
    }
    _write_json(output / "manifest.json", manifest)
    main_rows, calibration_rows = [], []
    index = 0
    for n, f, p in itertools.product(SIGNALS, EVE_FRACTIONS, NOISE_PROBABILITIES):
        is_calibration = n == 4096 and p in COMPARISON_NOISE
        for repeat in range(config["main_repeats"]):
            base = Config(n, f, p, BASELINE, seed=config["main_seed"] + index)
            transmission = simulate(base)
            session_id = f"main:{index}"
            main_rows.append(_row(transmission, base, session_id, repeat, "main", is_calibration))
            if is_calibration:
                for alpha in SAMPLE_FRACTIONS:
                    calibration_rows.append(_row(transmission, replace(base, sample_fraction=alpha),
                                                 session_id, repeat, "calibration", True))
            index += 1
    main_summary, calibration_summary = summarize(main_rows), summarize(calibration_rows)
    _write_csv(output / "main.csv", main_rows)
    _write_csv(output / "calibration.csv", calibration_rows)
    _write_json(output / "main_summary.json", main_summary)
    _write_json(output / "calibration_summary.json", calibration_summary)
    selection = select_fraction(calibration_summary)
    selection["mode"] = manifest["mode"]
    if quick:
        selection.update(selected_fraction=BASELINE, reason="Smoke test: giữ B0, không đưa ra kết luận nghiên cứu")
    selection["frozen_utc"] = datetime.now(timezone.utc).isoformat()
    _write_json(output / "selection.json", selection)
    selection_digest = hashlib.sha256((output / "selection.json").read_bytes()).hexdigest()

    evaluation_rows = []
    index = 0
    for f, p in itertools.product(EVE_FRACTIONS, COMPARISON_NOISE):
        for repeat in range(config["evaluation_repeats"]):
            base = Config(4096, f, p, BASELINE, seed=config["evaluation_seed"] + index)
            transmission = simulate(base)
            for alpha in SAMPLE_FRACTIONS:
                evaluation_rows.append(_row(transmission, replace(base, sample_fraction=alpha),
                                            f"evaluation:{index}", repeat, "evaluation"))
            index += 1
    assert hashlib.sha256((output / "selection.json").read_bytes()).hexdigest() == selection_digest
    main_seeds = {row["seed"] for row in main_rows}
    evaluation_seeds = {row["seed"] for row in evaluation_rows}
    assert not main_seeds & evaluation_seeds
    evaluation_summary = summarize(evaluation_rows)
    differences, paired_summary = paired_differences(evaluation_rows, config["bootstrap_seed"], config["bootstrap_repeats"])
    _write_csv(output / "evaluation.csv", evaluation_rows)
    _write_csv(output / "paired_differences.csv", differences)
    _write_json(output / "evaluation_summary.json", evaluation_summary)
    _write_json(output / "paired_summary.json", paired_summary)
    evaluation_checks = assess_candidates(evaluation_summary)
    _write_json(output / "evaluation_checks.json", {"selected_fraction": selection["selected_fraction"],
                "candidates": evaluation_checks, "reselection": False})
    threshold_summary = []
    for threshold in (.03, .05, .08):
        alternative_rows = []
        for row in main_rows:
            decision = monitor(row["sample_errors"], row["sample_count"], threshold, row["min_samples"])
            alternative_rows.append({**row, **decision, "threshold": threshold,
                                     "y_pre": row["remaining_count"] if decision["status"] == "continue" else 0})
        threshold_summary.extend({**row, "threshold": threshold} for row in summarize(alternative_rows))
    _write_json(output / "threshold_summary.json", threshold_summary)
    manifest.update(
        state="analyzing", main_sessions=len(main_rows), calibration_sessions=len(calibration_rows) // 3,
        calibration_results=len(calibration_rows), evaluation_sessions=len(evaluation_seeds),
        evaluation_results=len(evaluation_rows), independent_sessions=len(main_rows) + len(evaluation_seeds),
        selection_sha256=selection_digest, elapsed_seconds=time.perf_counter() - start,
    )
    summary = {"manifest": manifest, "selection": selection, "main_summary": main_summary,
               "calibration_summary": calibration_summary, "evaluation_summary": evaluation_summary,
               "evaluation_checks": evaluation_checks, "paired_summary": paired_summary,
               "figures": [], "scope": manifest["scope"]}
    _write_json(output / "manifest.json", manifest)
    _write_json(output / "summary.json", summary)
    if plots:
        from bb84_lab.research.plot_results import plot_study
        summary["figures"] = plot_study(output)
    manifest.update(state="complete", elapsed_seconds=time.perf_counter() - start)
    _write_json(output / "manifest.json", manifest)
    _write_json(output / "summary.json", summary)
    return summary


def check_research():
    """Fast deterministic checks for selection, gates and paired differences."""
    summary = []
    for f, p, alpha in itertools.product(EVE_FRACTIONS, COMPARISON_NOISE, SAMPLE_FRACTIONS):
        summary.append({"eve_fraction": f, "noise_probability": p, "sample_fraction": alpha,
                        "anomalous_rate": 1 if f >= .5 else 0, "inconclusive_rate": 0,
                        "y_pre_mean": 1800 if alpha == .1 else 1500 if alpha == .25 else 1000})
    assert select_fraction(summary)["selected_fraction"] == .1
    for row in summary:
        if row["sample_fraction"] == .1 and row["eve_fraction"] == .5:
            row["anomalous_rate"] = .9
    assert select_fraction(summary)["selected_fraction"] == BASELINE
    for row in summary:
        row["y_pre_mean"] = 0
    assert select_fraction(summary)["selected_fraction"] == BASELINE
    rows = []
    for index in range(4):
        for alpha in SAMPLE_FRACTIONS:
            rows.append({"session_id": str(index), "seed": index, "signals": 4096,
                         "eve_fraction": 0, "noise_probability": 0, "sample_fraction": alpha,
                         "sifted_count": 2048, "y_pre": int(2048 * (1 - alpha))})
    differences, paired = paired_differences(rows, bootstrap_repeats=100)
    assert len(differences) == 12 and len(paired) == 3
    assert next(row for row in paired if row["sample_fraction"] == .1)["ci95"][0] > 0
    assert next(row for row in paired if row["sample_fraction"] == BASELINE)["mean_difference"] == 0
    try:
        paired_differences(rows[:-1])
    except ValueError:
        pass
    else:
        raise AssertionError("Missing paired observation was accepted")


def append_postprocessing(output):
    """Measure Y_final on existing sessions without changing the frozen selection."""
    from bb84_lab.simulation.session import integrated_session

    output = Path(output)
    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((output / "summary.json").read_text(encoding="utf-8"))
    if manifest.get("state") != "complete":
        raise ValueError("Chỉ bổ sung hậu xử lý vào study đã hoàn tất")
    selection_bytes = (output / "selection.json").read_bytes()
    if hashlib.sha256(selection_bytes).hexdigest() != manifest["selection_sha256"]:
        raise ValueError("Tệp lựa chọn đã thay đổi sau khi đóng băng")
    selection = json.loads(selection_bytes)
    selected = selection["selected_fraction"]
    if selected not in SAMPLE_FRACTIONS:
        raise ValueError("Tỷ lệ mẫu đã chọn không hợp lệ")
    reserved = ("postprocessing.csv", "postprocessing_summary.json", "postprocessing_manifest.json")
    if any((output / name).exists() for name in reserved):
        raise FileExistsError("Dữ liệu hậu xử lý đã tồn tại; không ghi đè")
    sources = []
    for dataset in ("main", "evaluation"):
        with (output / f"{dataset}.csv").open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                if dataset == "main" or float(row["sample_fraction"]) in {BASELINE, selected}:
                    sources.append(row)
    unique = {(row["dataset"], row["seed"], row["sample_fraction"]) for row in sources}
    if len(unique) != len(sources):
        raise ValueError("Dữ liệu nguồn hậu xử lý bị trùng")
    expected_rows = manifest["main_sessions"] + manifest["evaluation_sessions"] * len({BASELINE, selected})
    if len(sources) != expected_rows:
        raise ValueError("Số dòng nguồn hậu xử lý không khớp manifest")
    progress = {
        "state": "running", "source_selection_sha256": manifest["selection_sha256"],
        "selected_fraction": selected, "independent_sessions_added": 0,
        "scope": "Educational Y_final under the declared entropy budget; not physical/composable QKD",
        "coverage": "All main sessions; baseline and frozen selected fraction on held-out sessions",
    }
    progress_path = output / "postprocessing_manifest.json"
    with progress_path.open("x", encoding="utf-8") as handle:
        json.dump(progress, handle, indent=2)
    started = time.perf_counter()
    records = []
    try:
        for row in sources:
            config = Config(
                int(row["signals"]), float(row["eve_fraction"]), float(row["noise_probability"]),
                float(row["sample_fraction"]), float(row["threshold"]), int(row["min_samples"]), int(row["seed"]),
            )
            result = integrated_session(config, message="Đo hậu xử lý mô hình BB84")
            if result["status"] != row["status"] or any(
                result[name] != int(row[name])
                for name in ("sifted_count", "sample_count", "sample_errors", "remaining_count", "y_pre")
            ):
                raise ValueError("Mô phỏng hậu xử lý không khớp dữ liệu nguồn")
            processed = result["postprocessing"]
            encrypted = result["encryption"]
            ready = processed["status"] == "ready"
            if ready and (not processed["key_match"] or processed["output_bits"] < 256 or not encrypted
                          or not all(encrypted[name] for name in ("roundtrip_ok", "tamper_rejected", "replay_rejected"))):
                raise ValueError("Phiên phát hành khóa không vượt qua kiểm chứng đầu-cuối")
            records.append({
                "dataset": row["dataset"], "session_id": row["session_id"], **{
                    name: getattr(config, name) for name in (
                        "signals", "eve_fraction", "noise_probability", "sample_fraction", "threshold", "min_samples", "seed",
                    )},
                "monitor_status": result["status"], "sifted_count": result["sifted_count"],
                "remaining_count": result["remaining_count"], "y_pre": result["y_pre"],
                "postprocess_status": processed["status"], "postprocess_reason": processed["reason"],
                **{name: processed[name] for name in (
                    "retained_bits", "corrected_errors", "parity_leak_bits", "confirmation_leak_bits",
                    "entropy_budget_bits", "output_bits", "key_match",
                )},
                "y_final": processed["output_bits"] if ready else 0,
                "roundtrip_ok": bool(encrypted and encrypted["roundtrip_ok"]),
                **result["timings"],
            })
        groups = {}
        for row in records:
            key = tuple(row[name] for name in ("dataset", "signals", "eve_fraction", "noise_probability", "sample_fraction"))
            groups.setdefault(key, []).append(row)
        processed_summary = []
        for (dataset, n, f, p, alpha), group in sorted(groups.items()):
            item = {"dataset": dataset, "signals": n, "eve_fraction": f, "noise_probability": p,
                    "sample_fraction": alpha, "sessions": len(group)}
            for status in ("ready", "skipped", "failed", "insufficient_key"):
                count = sum(row["postprocess_status"] == status for row in group)
                item[f"{status}_count"] = count
                item[f"{status}_rate"] = count / len(group)
                item[f"{status}_ci95"] = wilson_interval(count, len(group))
            for name in ("y_pre", "y_final", "corrected_errors", "parity_leak_bits", "confirmation_leak_bits",
                         "entropy_budget_bits", "postprocessing_seconds", "encryption_seconds", "total_seconds"):
                item[f"{name}_mean"] = statistics.mean(row[name] for row in group)
            item["output_bits_mean"] = item["y_final_mean"]
            item["ready_roundtrip_count"] = sum(row["postprocess_status"] == "ready" and row["roundtrip_ok"] for row in group)
            processed_summary.append(item)
        _write_csv(output / "postprocessing.csv", records)
        _write_json(output / "postprocessing_summary.json", processed_summary)
        if hashlib.sha256((output / "selection.json").read_bytes()).hexdigest() != manifest["selection_sha256"]:
            raise ValueError("Lựa chọn đóng băng bị thay đổi trong khi hậu xử lý")
        progress.update(state="complete", rows=len(records), elapsed_seconds=time.perf_counter() - started,
                        ready_sessions=sum(row["postprocess_status"] == "ready" for row in records),
                        failed_sessions=sum(row["postprocess_status"] == "failed" for row in records))
        summary["postprocessing_summary"] = processed_summary
        summary["postprocessing_manifest"] = progress
        summary["scope"] = "Y_pre and measured Y_final in an educational model; no physical/composable QKD claim"
        manifest["postprocessing_rows"] = len(records)
        manifest["postprocessing_state"] = "complete"
        manifest["scope"] = summary["scope"]
        summary["manifest"] = manifest
        _write_json(output / "manifest.json", manifest)
        _write_json(output / "summary.json", summary)
        if summary.get("figures"):
            from bb84_lab.research.plot_results import plot_study
            summary["figures"] = plot_study(output)
            _write_json(output / "summary.json", summary)
        _write_json(progress_path, progress)
    except Exception:
        progress.update(state="failed", completed_rows=len(records), elapsed_seconds=time.perf_counter() - started)
        _write_json(progress_path, progress)
        raise
    return progress


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--quick", action="store_true", help="Smoke test, không dùng để kết luận nghiên cứu")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--postprocess", action="store_true", help="Bổ sung Y_final trên dữ liệu study có sẵn; không chọn lại alpha")
    args = parser.parse_args()
    try:
        if args.postprocess:
            if args.quick or args.config or args.no_plots:
                raise ValueError("--postprocess chỉ dùng với --output của study đã có")
            progress = append_postprocessing(args.output)
            print(f"Đã đo hậu xử lý {progress['rows']} kết quả; {progress['ready_sessions']} phiên có khóa mô hình.")
            print("Không thêm phiên độc lập, không chọn lại tỷ lệ mẫu.")
            return
        result = run_study(args.output, args.quick, not args.no_plots, args.config)
    except (ValueError, OSError, ImportError) as error:
        parser.exit(2, f"Lỗi: {error}\n")
    print(f"{result['manifest']['independent_sessions']} phiên độc lập; alpha đóng băng = {result['selection']['selected_fraction']:.0%}")
    print(result["selection"]["reason"])
    print(args.output.resolve())


if __name__ == "__main__":
    main()
