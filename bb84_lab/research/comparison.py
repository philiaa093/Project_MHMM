"""Predeclared BB84/E91 operational comparison, with actual shared postprocessing."""

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import itertools
import json
from pathlib import Path
import platform
import sys
import time

from bb84_lab.core.bb84 import Config
from bb84_lab.research.comparison_analysis import ablation_summary, summarize
from bb84_lab.shared.paths import CONFIG_ROOT, PROJECT_ROOT
from bb84_lab.simulation.comparison import run_session


SCHEMA_VERSION = "bb84-e91-operational-v1"


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")


def write_csv(path, rows):
    if not rows:
        raise ValueError("No observations")
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _coerce_row(row):
    """Recover CSV scalar types when resuming an interrupted measurement."""
    converted = {}
    for key, value in row.items():
        if value == "":
            converted[key] = None
        elif value == "True":
            converted[key] = True
        elif value == "False":
            converted[key] = False
        else:
            try:
                converted[key] = float(value) if any(mark in value for mark in (".", "e", "E")) else int(value)
            except (TypeError, ValueError):
                converted[key] = value
    return converted


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    expected = {"seed", "repeats", "bootstrap_seed", "bootstrap_repeats", "sample_fraction", "threshold", "min_samples",
                "yield_budgets", "yield_noise", "detection_budget", "detection_noise", "disturbance_fractions",
                "noise_budget", "noise_probabilities"}
    if type(config) is not dict or set(config) != expected:
        raise ValueError("Invalid comparison config fields")
    for name in ("seed", "bootstrap_seed", "repeats", "bootstrap_repeats", "min_samples"):
        if type(config[name]) is not int or config[name] < (0 if "seed" in name else 1):
            raise ValueError(f"Invalid {name}")
    for name in ("yield_budgets", "yield_noise", "detection_noise", "disturbance_fractions", "noise_probabilities"):
        values = config[name]
        if type(values) is not list or not values or len(set(values)) != len(values):
            raise ValueError(f"Invalid or duplicate {name}")
        for value in values:
            if name == "yield_budgets":
                if type(value) is not int or value < 2 or value % 2 or value > 65536:
                    raise ValueError("Budgets must be even integers in [2, 65536]")
            elif type(value) not in (int, float) or not 0 <= value <= 1:
                raise ValueError(f"Invalid probability in {name}")
    for name in ("detection_budget", "noise_budget"):
        value = config[name]
        if type(value) is not int or not 2 <= value <= 65536 or value % 2:
            raise ValueError("Budgets must be even integers in [2, 65536]")
    Config(sample_fraction=config["sample_fraction"], threshold=config["threshold"], min_samples=config["min_samples"])
    return config


def cases(config):
    for mode, budget, noise in itertools.product(("equal_signals", "equal_measurements"),
                                                 config["yield_budgets"], config["yield_noise"]):
        yield "key_yield", mode, budget, 0., noise
    for noise, disturbance in itertools.product(config["detection_noise"], config["disturbance_fractions"]):
        yield "detection", "equal_signals", config["detection_budget"], disturbance, noise
    for mode, noise in itertools.product(("equal_signals", "equal_measurements"), config["noise_probabilities"]):
        yield "noise", mode, config["noise_budget"], 0., noise


def source_fingerprint():
    paths = [PROJECT_ROOT / "bb84_lab" / domain for domain in ("core", "simulation", "research", "network")]
    return {str(path.relative_to(PROJECT_ROOT)).replace("\\", "/"): hashlib.sha256(path.read_bytes()).hexdigest()
            for root in paths for path in sorted(root.glob("*.py"))}


def run_comparison(output, config_path=None, *, quick=False, plots=True, resume=False):
    config = load_config(config_path or CONFIG_ROOT / "comparison.json")
    if type(quick) is not bool or type(plots) is not bool:
        raise ValueError("quick and plots must be bool")
    if quick:
        config.update(repeats=2, bootstrap_repeats=50, yield_budgets=[4096], yield_noise=[0., .03],
                      detection_noise=[0.], disturbance_fractions=[0., 1.], noise_probabilities=[0., .05])
    output = Path(output)
    resuming = resume and output.exists()
    if resuming:
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        if manifest.get("state") != "running" or manifest.get("mode") != ("smoke" if quick else "full"):
            raise ValueError("Only an interrupted matching comparison can be resumed")
        stored_config = json.loads((output / "config.json").read_text(encoding="utf-8"))
        if stored_config != config:
            raise ValueError("Resume config differs from the interrupted run")
        with (output / "sessions.csv").open(encoding="utf-8", newline="") as handle:
            rows = [_coerce_row(row) for row in csv.DictReader(handle)]
        start_case = int(manifest.get("completed_cases", 0))
        # Each repeat has two independent protocol runs: one BB84 row and two
        # E91 policy rows (operational + same-measurement ablation).
        if len(rows) != start_case * config["repeats"] * 3:
            raise ValueError("Interrupted observation count does not match completed cases")
        initial_fingerprint = manifest.get("source_sha256")
        fingerprint = source_fingerprint()
        manifest["resumed_utc"] = datetime.now(timezone.utc).isoformat()
        manifest["source_sha256_at_resume"] = fingerprint
        manifest["resume_note"] = (
            "The interrupted prefix was measured before the resume. The simulation and runner hashes are retained; "
            "aggregation-only source changes are recorded separately."
        )
    else:
        output.mkdir(parents=True, exist_ok=False)
        start_case = 0
        rows = []
        fingerprint = source_fingerprint()
        initial_fingerprint = fingerprint
    config_bytes = json.dumps(config, sort_keys=True, allow_nan=False).encode("ascii")
    config_digest = hashlib.sha256(config_bytes).hexdigest()
    if not resuming:
        manifest = {
        "schema_version": SCHEMA_VERSION, "state": "running", "mode": "smoke" if quick else "full",
        "created_utc": datetime.now(timezone.utc).isoformat(), "python": sys.version,
        "platform": platform.platform(), "processor": platform.processor(), "config": config,
        "config_sha256": config_digest, "source_sha256": fingerprint,
        "cryptography_version": importlib.metadata.version("cryptography"),
        "protocol_order": "Alternates by repeat; serial execution",
        "seed_policy": "Unique SHA256-derived seeds per experiment/budget/noise/f/protocol/repeat; no cross-protocol pairing",
        "independent_unit": "One protocol measurement realization; E91 ablation is a reused realization",
        "budgets": {
            "equal_signals": "BB84 N signals versus E91 N pairs (N versus 2N endpoint measurements)",
            "equal_measurements": "BB84 B signals versus E91 B/2 pairs; ignores preparation/source and hardware costs",
            "public_bits": "Measured outcome disclosures and declared authenticated JSON bytes; not constrained equal",
        },
        "noise": "Independent Bob bit flips p in both protocols; E91 dashboard white-noise fraction would be 2p",
        "attacks": {"bb84": "intercept-measure-resend with independent random Eve basis",
                    "e91": "independent-outcome replacement, not an equivalent cryptographic attack"},
        "alarm_definition": "QBER anomalous OR CHSH upper bound <=2; CHSH inconclusive is an abort, not an alarm",
        "miss_definition": "Under nonzero disturbance: monitor continues; also record not-flagged and key-released separately",
        "false_alarm_definition": "Alarm only under f=0 and expected QBER <= threshold; high-noise f=0 alarms reported separately",
        "key_yield": "Actual full Toeplitz output when ready, otherwise zero; first 256 bits used by application",
        "stage_counts": "Cascade/confirmation preserve retained length; leakage is a separate budget deduction",
        "ablation": "QBER-only diagnostic on identical E91 data, still discards Bell outcomes; does not remove Bell acquisition cost",
        "timing": "perf_counter wall seconds; policy setup includes shared simulation and monitoring; not physical QKD speed",
        "scope": "Classical simulation, public seeds, shared educational entropy assumption; no physical/finite-key/DI security claim",
        "figures": [],
        }
        write_json(output / "manifest.json", manifest)
        write_json(output / "config.json", config)
    started = time.perf_counter()
    seen_seeds = {int(row["seed"]) for row in rows}
    try:
        for case_index, (experiment, mode, budget, disturbance, noise) in enumerate(cases(config)):
            if case_index < start_case:
                continue
            for repeat in range(config["repeats"]):
                for protocol in (("bb84", "e91") if repeat % 2 == 0 else ("e91", "bb84")):
                    signals = budget // 2 if mode == "equal_measurements" and protocol == "e91" else budget
                    domain = f"{SCHEMA_VERSION}:{config['seed']}:{case_index}:{protocol}:{repeat}"
                    seed = int.from_bytes(hashlib.sha256(domain.encode("ascii")).digest()[:16], "big")
                    if seed in seen_seeds:
                        raise AssertionError("Seed collision")
                    seen_seeds.add(seed)
                    results = run_session(protocol, signals, seed, disturbance_fraction=disturbance,
                                          noise_probability=noise, sample_fraction=config["sample_fraction"],
                                          threshold=config["threshold"], min_samples=config["min_samples"])
                    for result in results:
                        rows.append({"session_id": f"{experiment}:{case_index}:{protocol}:{repeat}", "experiment": experiment,
                                     "budget_mode": mode, "budget": budget, "repeat": repeat,
                                     "endpoint_measurements": signals * (2 if protocol == "e91" else 1), **result})
            # Retain completed observations even if a subsequent case fails.
            write_csv(output / "sessions.csv", rows)
            manifest.update(completed_cases=case_index + 1, independent_sessions=len(seen_seeds), observations=len(rows),
                            elapsed_seconds=time.perf_counter() - started)
            write_json(output / "manifest.json", manifest)
            print(f"{case_index + 1}: {experiment}/{mode}/B={budget}/f={disturbance}/p={noise}; {len(seen_seeds)} sessions", flush=True)
        summary = summarize(rows, config["bootstrap_seed"], config["bootstrap_repeats"])
        write_json(output / "summary.json", summary)
        write_json(output / "chsh_ablation.json", ablation_summary(rows))
        if plots:
            from bb84_lab.research.plot_comparison import plot_comparison
            manifest["figures"] = plot_comparison(output)
        if source_fingerprint() != fingerprint:
            raise RuntimeError("Source changed during measurement; do not publish mixed-code results")
        manifest.update(state="complete", elapsed_seconds=time.perf_counter() - started,
                        ready_operational_sessions=sum(row["ready"] for row in rows if row["policy"] != "qber_only_ablation"),
                        artifacts_sha256={name: hashlib.sha256((output / name).read_bytes()).hexdigest()
                                          for name in ("sessions.csv", "summary.json", "chsh_ablation.json", "config.json")})
        write_json(output / "manifest.json", manifest)
    except Exception as error:
        manifest.update(state="failed", error_type=type(error).__name__, elapsed_seconds=time.perf_counter() - started)
        write_json(output / "manifest.json", manifest)
        raise
    return manifest


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--quick", action="store_true", help="Smoke only; no research conclusions")
    parser.add_argument("--no-plots", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Continue an interrupted matching run")
    args = parser.parse_args()
    result = run_comparison(args.output, args.config, quick=args.quick, plots=not args.no_plots, resume=args.resume)
    print(json.dumps({name: result[name] for name in ("state", "mode", "independent_sessions", "observations", "elapsed_seconds")}))


if __name__ == "__main__":
    main()
