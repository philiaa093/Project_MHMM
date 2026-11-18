"""Chạy Monte Carlo BB84; chỉ lưu thống kê công khai, không tạo khóa."""

import argparse
import csv
from dataclasses import replace
from datetime import datetime, timezone
import itertools
import json
from pathlib import Path
import platform
import sys
import time

from bb84_lab.bb84 import Config, evaluate, expected_qber, simulate
from bb84_lab.research_analysis import summarize as summarize


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {
        "signals", "eve_fractions", "noise_probabilities", "sample_fractions",
        "repeats", "seed", "threshold", "min_samples",
    }
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError(f"Cấu hình phải có đúng các trường: {sorted(required)}")
    for field in ("signals", "eve_fractions", "noise_probabilities", "sample_fractions"):
        values = config[field]
        if not isinstance(values, list) or not values:
            raise ValueError(f"{field} phải là danh sách không rỗng")
        if any(type(value) not in (int, float) for value in values):
            raise ValueError(f"{field} chỉ nhận số")
        if len(values) != len(set(values)):
            raise ValueError(f"{field} không được lặp giá trị")
    if type(config["repeats"]) is not int or config["repeats"] < 1:
        raise ValueError("repeats phải là số nguyên dương")
    for n, f, p, alpha in itertools.product(
        config["signals"], config["eve_fractions"],
        config["noise_probabilities"], config["sample_fractions"],
    ):
        Config(n, f, p, alpha, config["threshold"], config["min_samples"], config["seed"])
    return config


def run_experiments(config, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    manifest = {
        "state": "running", "created_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version, "platform": platform.platform(), "config": config,
        "scope": "classical Monte Carlo; no BB84 key release; no postprocessing",
        "pairing": "same transmission and sample permutation for every sample_fraction",
        "randomness": "public deterministic seeds, unsuitable for real encryption keys",
    }
    manifest_path = output / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    started = time.perf_counter()
    rows = []
    independent_sessions = 0
    for n, f, p in itertools.product(
        config["signals"], config["eve_fractions"], config["noise_probabilities"],
    ):
        for repeat in range(config["repeats"]):
            seed = config["seed"] + independent_sessions
            base = Config(n, f, p, config["sample_fractions"][0],
                          config["threshold"], config["min_samples"], seed)
            simulation_started = time.perf_counter()
            transmission = simulate(base)
            simulation_seconds = time.perf_counter() - simulation_started
            for alpha in config["sample_fractions"]:
                evaluation_started = time.perf_counter()
                result = evaluate(transmission, replace(base, sample_fraction=alpha))
                rows.append({
                    "session_index": independent_sessions, "repeat": repeat,
                    **result.public_summary(),
                    "expected_qber": expected_qber(f, p),
                    "simulation_seconds": simulation_seconds,
                    "evaluation_seconds": time.perf_counter() - evaluation_started,
                })
            independent_sessions += 1
    with (output / "sessions.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summaries = summarize(rows)
    (output / "summary.json").write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    manifest.update(state="complete", independent_sessions=independent_sessions,
                    paired_results=len(rows), elapsed_seconds=time.perf_counter() - started)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parents[2] / "configs" / "smoke.json")
    parser.add_argument("--output", type=Path, required=True, help="Thư mục mới, không ghi đè dữ liệu cũ")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        manifest = run_experiments(config, args.output)
    except (ValueError, OSError) as error:
        parser.exit(2, f"Lỗi: {error}\n")
    print(f"{manifest['independent_sessions']} phiên độc lập; {manifest['paired_results']} kết quả phương án.")
    print(f"Dữ liệu: {args.output.resolve()}")
    print("Chỉ thống kê mô phỏng cổ điển; chưa phát hành khóa BB84.")


if __name__ == "__main__":
    main()
