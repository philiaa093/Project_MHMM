# Repository Guidelines

## Project Structure & Module Organization

This project contains the Vietnamese research proposal `docs/de_cuong_QKD_3_tuan.md` and a working BB84/QBER simulation with an educational ChaCha20-Poly1305 demonstration. Python implementations live in `bb84_lab/`, research runners in `bb84_lab/research/`, and assert-based checks in `tests/self_check.py`. Root Python compatibility files have been removed at the user's request; use package imports and `python -m` entry points. `docs/` contains documentation, `web/` the local interface, `configs/` source configuration, and `outputs/` generated data and figures.

Treat the proposal as the scope reference. Keep simulation (`bb84.py`), postprocessing (`postprocess.py`), encryption (`secure_channel.py`), orchestration (`demo.py`, `experiments.py`, `study.py`), and shared research analysis (`research_analysis.py`) separate. Document actual module paths in the README. Keep generated CSV data and figures distinguishable from source files. Keep Python source in its packages; do not recreate root compatibility files.

## Build, Test, and Development Commands

No build system, formatter, linter, or type checker is configured. Pinned runtime dependencies are in `requirements.txt`; optional plotting and Qiskit/Aer dependencies are in `requirements-research.txt`.

- `python -m venv .venv`: create an isolated environment when starting Python development.
- `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`: install the runtime dependencies.
- `.\.venv\Scripts\python.exe -m pip check`: check installed dependency compatibility.
- `.\.venv\Scripts\python.exe -m tests.self_check`: run assert-based regression checks without `-O`.
- `.\.venv\Scripts\python.exe -m bb84_lab.app --open`: start the loopback HTTP interface.
- `.\.venv\Scripts\python.exe -m bb84_lab.research.study --quick --no-plots --output outputs/study-new`: run a reproducible smoke study in a new output directory.

Keep verified installation, demo, and experiment commands in the README. Do not upgrade pinned dependencies as part of unrelated refactoring. The base application and self-check must not require optional research dependencies.

## Coding Style & Naming Conventions

Preserve the proposal's Vietnamese prose, numbered headings, citation identifiers such as `[S11]`, and mathematical notation. Clearly distinguish measured results from targets and assumptions.

For new Python code, use four-space indentation, `snake_case` functions and modules, and `UPPER_CASE` constants. Prefer the standard library for orchestration and CSV output. No formatter or linter is configured; avoid introducing tooling without a concrete need.

## Testing Guidelines

No testing framework or coverage threshold exists. Extend the assert-based `tests/self_check.py`, runnable with `python -m tests.self_check`, rather than introducing a test framework.

Check sample-bit removal, session aborts on failure, matching keys before encryption, rejection of modified ciphertext and replayed messages, and nonce uniqueness. Record simulation seeds and configurations so experiments can be reproduced; report uncertainty and unsuccessful detection cases.

## Commit & Pull Request Guidelines

No Git history is available in this checkout. Use short, imperative commit subjects, for example `docs: clarify QBER sampling assumptions`.

PR descriptions should identify the changed proposal sections or modules, explain the rationale, and list validation performed. Link related issues when available; include regenerated figures when conclusions or charts change.

## Security & Research Scope

Use `cryptography`'s `ChaCha20Poly1305` API rather than implementing cryptographic primitives. Never commit or publicly log keys, raw key bits, or authentication secrets. Never reuse a nonce with the same key. Describe results as classical simulation findings; do not claim physical QKD security.
