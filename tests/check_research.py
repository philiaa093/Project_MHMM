"""Assert-based research checks, run through tests.self_check."""

import csv
import hashlib
import json
from pathlib import Path
import secrets
import shutil
from bb84_lab.research.experiments import load_config, run_experiments
from tests.support import rejected


def check_experiments():
    config = load_config(Path(__file__).resolve().parents[1] / "configs" / "smoke.json")
    config.update(signals=[1024], eve_fractions=[0, 1], noise_probabilities=[0], repeats=2)
    scratch_root = Path(__file__).resolve().parents[1] / "outputs"
    scratch_root.mkdir(exist_ok=True)
    directory = scratch_root / f"self-check-{secrets.token_hex(16)}"
    directory.mkdir()
    try:
        runs = []
        for name in ("first", "second"):
            manifest = run_experiments(config, directory / name)
            assert manifest["state"] == "complete"
            assert manifest["independent_sessions"] == 4 and manifest["paired_results"] == 12
            with (directory / name / "sessions.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            assert not {"key", "psk", "alice_bits", "bob_bits", "sample_alice_bits"} & rows[0].keys()
            for row in rows:
                del row["simulation_seconds"], row["evaluation_seconds"]
            runs.append(rows)
            summaries = json.loads((directory / name / "summary.json").read_text(encoding="utf-8"))
            assert len(summaries) == 6
            assert all(sum(item[f"{status}_count"] for status in ("continue", "anomalous", "inconclusive")) == 2 for item in summaries)
        assert runs[0] == runs[1]
        rejected(lambda: run_experiments(config, directory / "first"), FileExistsError)
        assert (directory / "first" / "manifest.json").exists()
        for change in ({"repeats": 0}, {"seed": True}, {"sample_fractions": [0.25, 0.25]},
                       {"signals": [True]}, {"eve_fractions": [float("nan")]}, {"unknown": 1}):
            path = directory / "invalid.json"
            path.write_text(json.dumps({**config, **change}), encoding="utf-8")
            rejected(lambda: load_config(path))
    finally:
        if not directory.resolve().is_relative_to(scratch_root):
            raise ValueError("Thư mục kiểm tra nằm ngoài outputs")
        shutil.rmtree(directory)


def check_study():
    from bb84_lab.research.experiments import summarize as runner_summarize
    from bb84_lab.research import analysis
    from bb84_lab.research import study

    assert runner_summarize is analysis.summarize is study.summarize
    for name in ("assess_candidates", "select_fraction", "_quantile", "paired_differences",
                 "EVE_FRACTIONS", "COMPARISON_NOISE", "SAMPLE_FRACTIONS", "BASELINE", "CRITERIA"):
        assert getattr(study, name) is getattr(analysis, name)

    scratch_root = Path(__file__).resolve().parents[1] / "outputs"
    scratch_root.mkdir(exist_ok=True)
    directory = scratch_root / f"self-check-study-{secrets.token_hex(16)}"
    directory.mkdir()
    try:
        output = directory / "study"
        summary = study.run_study(output, quick=True, plots=False)
        assert summary["manifest"]["state"] == "complete"
        assert summary["manifest"]["mode"] == "smoke"
        assert summary["manifest"]["independent_sessions"] == 165
        assert summary["selection"]["selected_fraction"] == study.BASELINE
        assert summary["figures"] == []
        rejected(lambda: study.run_study(output, quick=True, plots=False), FileExistsError)

        sources, rows = {}, {}
        for name, count in (("main", 120), ("calibration", 90), ("evaluation", 135)):
            path = output / f"{name}.csv"
            sources[name] = path.read_bytes()
            with path.open(encoding="utf-8", newline="") as handle:
                rows[name] = list(csv.DictReader(handle))
            assert len(rows[name]) == count
        assert not {row["seed"] for row in rows["main"]} & {row["seed"] for row in rows["evaluation"]}
        assert {row["session_id"] for row in rows["calibration"]} <= {row["session_id"] for row in rows["main"]}
        for session_id in {row["session_id"] for row in rows["evaluation"]}:
            pair = [row for row in rows["evaluation"] if row["session_id"] == session_id]
            assert len(pair) == 3 and len({row["seed"] for row in pair}) == 1
            assert {float(row["sample_fraction"]) for row in pair} == set(study.SAMPLE_FRACTIONS)

        selection_path = output / "selection.json"
        selection_bytes = selection_path.read_bytes()
        assert hashlib.sha256(selection_bytes).hexdigest() == summary["manifest"]["selection_sha256"]
        selection_path.write_bytes(selection_bytes + b"\n")
        rejected(lambda: study.append_postprocessing(output))
        assert not (output / "postprocessing_manifest.json").exists()
        selection_path.write_bytes(selection_bytes)
        progress = study.append_postprocessing(output)
        assert progress["state"] == "complete" and progress["rows"] == 165
        assert progress["independent_sessions_added"] == 0
        assert selection_path.read_bytes() == selection_bytes
        for name, content in sources.items():
            assert (output / f"{name}.csv").read_bytes() == content
        with (output / "postprocessing.csv").open(encoding="utf-8", newline="") as handle:
            processed = list(csv.DictReader(handle))
        assert len(processed) == progress["rows"]
        assert sum(row["postprocess_status"] == "ready" for row in processed) == progress["ready_sessions"]
        for row in processed:
            if row["postprocess_status"] == "ready":
                assert row["key_match"] == row["roundtrip_ok"] == "True"
                assert int(row["y_final"]) == int(row["output_bits"]) >= 256
            else:
                assert int(row["y_final"]) == int(row["output_bits"]) == 0
        rejected(lambda: study.append_postprocessing(output), FileExistsError)
    finally:
        if not directory.resolve().is_relative_to(scratch_root):
            raise ValueError("Thư mục kiểm tra nằm ngoài outputs")
        shutil.rmtree(directory)


def check_comparison():
    """Actual E91 postprocessing, disclosure separation and independent budgets."""
    from dataclasses import replace
    import statistics

    from bb84_lab.core.bb84 import Config, monitor
    from bb84_lab.core.e91_key import E91Config, evaluate_transmission, expected_key_qber, simulate_transmission
    from bb84_lab.core.postprocess import postprocess_bits
    from bb84_lab.core.secure_channel import AuthenticatedTranscript
    from bb84_lab.network.e91_session import _check_session
    from bb84_lab.research.comparison import load_config as comparison_config, run_comparison
    from bb84_lab.research.comparison_analysis import ablation_summary, summarize
    from bb84_lab.simulation.comparison import run_session

    config = E91Config(signals=16384, seed=1707)
    transmission = simulate_transmission(config)
    decision, sample, retained = evaluate_transmission(transmission)
    assert decision["status"] == "continue" and decision["bell"]["status"] == "violation"
    assert not set(sample) & set(retained)
    assert not (set(sample) | set(retained)) & set(transmission.bell_indices)
    assert set(sample) | set(retained) == set(transmission.sifted_indices)
    assert all(transmission.alice_settings[i] == transmission.bob_settings[i] for i in retained)
    assert all(transmission.alice_bits[i] == transmission.bob_bits[i] for i in transmission.sifted_indices)
    bell_positions = [(i, (transmission.alice_settings[i], transmission.bob_settings[i])) for i in transmission.bell_indices]
    network_decision = _check_session(
        Config(signals=config.signals), bell_positions,
        [transmission.alice_bits[i] for i in transmission.bell_indices],
        [1 ^ transmission.bob_bits[i] for i in transmission.bell_indices],
        [transmission.alice_bits[i] for i in sample], [transmission.bob_bits[i] for i in sample],
    )
    assert decision == network_decision
    assert simulate_transmission(config) == transmission
    noisy = simulate_transmission(replace(config, disturbance_fraction=.25, noise_probability=.03))
    observed = statistics.fmean(noisy.alice_bits[i] != noisy.bob_bits[i] for i in noisy.sifted_indices)
    assert abs(observed - expected_key_qber(.25, .03)) < .025
    for change in ({"signals": True}, {"seed": -1}, {"disturbance_fraction": float("nan")},
                   {"noise_probability": 1.01}, {"sample_fraction": False}):
        rejected(lambda change=change: replace(config, **change))

    runs = [run_session("e91", 8192, 203), run_session("e91", 8192, 203)]
    for run in runs:
        assert len(run) == 2 and all(row["ready"] and row["aead_verified"] for row in run)
        assert run[1]["postprocessing_reused"] and run[0]["y_final"] == run[1]["y_final"] >= 256
        assert all(row["after_cascade_bits"] == row["after_confirmation_bits"] == row["retained_bits"] for row in run)
        assert all(row["confirmation_leak_bits"] == 257 and row["parity_leak_bits"] % 2 == 0 for row in run)
    deterministic = lambda run: [{k: v for k, v in row.items() if not k.endswith("_seconds")} for row in run]
    assert deterministic(runs[0]) == deterministic(runs[1])
    stopped = run_session("e91", 16, 203)
    assert all(not row["ready"] and row["y_final"] == 0 and row["postprocess_status"] == "skipped" for row in stopped)
    disturbed = run_session("e91", 8192, 203, disturbance_fraction=1.)
    assert disturbed[0]["alarm"] and not disturbed[0]["monitor_pass"] and not disturbed[0]["ready"]
    assert disturbed[0]["bell_status"] == "at_or_below_bound"
    psk = secrets.token_bytes(32)
    auth = [AuthenticatedTranscript(psk, "failed-confirmation") for _ in range(2)]
    alice_bits = (0,) * 1024
    bob_bits = tuple(int(i in (0, 1)) for i in range(1024))
    failed = postprocess_bits(alice_bits, bob_bits, monitor(0, 500), *auth,
                              reconciliation_seed=1, reconciliation_passes=1, protocol="e91")
    assert failed.status == "failed" and failed.output_bits == 0 and failed._alice_key is None

    scratch_root = Path(__file__).resolve().parents[1] / "outputs"
    directory = scratch_root / f"self-check-comparison-{secrets.token_hex(16)}"
    directory.mkdir()
    try:
        results = []
        for name in ("first", "second"):
            target = directory / name
            manifest = run_comparison(target, quick=True, plots=False)
            assert manifest["state"] == "complete" and manifest["mode"] == "smoke"
            assert manifest["independent_sessions"] == 40 and manifest["observations"] == 60
            with (target / "sessions.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            assert len({row["seed"] for row in rows}) == 40
            assert not {"alice_bits", "bob_bits", "key", "psk", "sample_positions"} & rows[0].keys()
            for row in rows:
                for field in list(row):
                    if field.endswith("_seconds"):
                        del row[field]
                if row["budget_mode"] == "equal_measurements":
                    assert int(row["endpoint_measurements"]) == int(row["budget"])
                if row["ready"] == "True":
                    assert int(row["y_final"]) >= 256 and row["aead_verified"] == "True"
                else:
                    assert int(row["y_final"]) == 0
            results.append(rows)
            summary = json.loads((target / "summary.json").read_text(encoding="utf-8"))
            assert all(row["sessions"] == 2 for row in summary)
            assert all(row["false_alarm_rate"] is None for row in summary if row["disturbance_fraction"] > 0)
            ablations = json.loads((target / "chsh_ablation.json").read_text(encoding="utf-8"))
            assert len(ablations) == 10
            rejected(lambda: run_comparison(target, quick=True, plots=False), FileExistsError)
        assert results[0] == results[1]
        base = comparison_config(Path(__file__).resolve().parents[1] / "configs/comparison.json")
        for change in ({"repeats": 0}, {"seed": True}, {"noise_probabilities": [float("nan")]},
                       {"yield_budgets": [4097]}, {"yield_noise": [.01, .01]}, {"unknown": 1}):
            path = directory / "invalid.json"
            path.write_text(json.dumps({**base, **change}), encoding="utf-8")
            rejected(lambda: comparison_config(path))
    finally:
        if not directory.resolve().is_relative_to(scratch_root):
            raise ValueError("Comparison scratch directory outside outputs")
        shutil.rmtree(directory)
