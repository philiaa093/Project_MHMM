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
