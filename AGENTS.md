# Repository Guidelines

## Project Structure & Module Organization

This project contains the Vietnamese research proposal `docs/de_cuong_QKD_3_tuan.md`, a working BB84/QBER simulation, and an educational Alice–Eve–Bob network/file-transfer demonstration. Organize Python by responsibility: `bb84_lab/core/` for algorithms and cryptography, `simulation/` for in-process demonstrations, `local/` for the simulation HTTP dashboard, `network/` for independent peers and Eve, `research/` for analysis/runners, and `shared/` for HTTP infrastructure and resource paths. Keep the package root limited to `__init__.py`; do not add flat business modules or compatibility files there or at the repository root. Use package imports and `python -m` entry points.

Treat the proposal as the scope reference. Keep `core/bb84.py`, `core/postprocess.py`, `core/secure_channel.py`, `simulation/session.py`, and `research/analysis.py` separate. Within `network/`, keep configuration, BB84 sessions, packet serialization, file transfer, TCP transport, Eve proxy, service state and HTTP UI separate. Network code must not import the local dashboard or in-process simulation; dashboards share `shared/http.py`. Resolve project resources through `shared/paths.py`. Put frontend source in `web/simulation/` or `web/network/`, with shared CSS in `web/shared/`. `docs/` holds documentation, `configs/` source configuration, and `outputs/` generated data, received files and figures. Document actual paths in the README.

## Build, Test, and Development Commands

No build system, formatter, linter, or type checker is configured. Pinned runtime dependencies are in `requirements.txt`; optional plotting and Qiskit/Aer dependencies are in `requirements-research.txt`.

- `python -m venv .venv`: create an isolated environment when starting Python development.
- `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`: install the runtime dependencies.
- `.\.venv\Scripts\python.exe -m pip check`: check installed dependency compatibility.
- `.\.venv\Scripts\python.exe -m tests.self_check`: run assert-based regression checks without `-O`.
- `.\.venv\Scripts\python.exe -m bb84_lab.local --open`: start the loopback HTTP interface.
- `.\.venv\Scripts\python.exe -m bb84_lab.simulation bb84`: run the in-process CLI demo.
- `.\.venv\Scripts\python.exe -m bb84_lab.network --help`: inspect the independent Alice/Bob/Eve commands.
- `.\.venv\Scripts\python.exe -m bb84_lab.research.study --quick --no-plots --output outputs/study-new`: run a reproducible smoke study in a new output directory.

Keep verified installation, demo, and experiment commands in the README. Do not upgrade pinned dependencies as part of unrelated refactoring. The base application and self-check must not require optional research dependencies.

## Coding Style & Naming Conventions

Preserve the proposal's Vietnamese prose, numbered headings, citation identifiers such as `[S11]`, and mathematical notation. Clearly distinguish measured results from targets and assumptions.

For new Python code, use four-space indentation, `snake_case` functions and modules, and `UPPER_CASE` constants. Prefer the standard library for orchestration and CSV output. No formatter or linter is configured; avoid introducing tooling without a concrete need.

## Testing Guidelines

No testing framework or coverage threshold exists. Keep `tests/self_check.py` as the runner for the assert suites `tests/check_structure.py`, `check_core.py`, `check_simulation.py`, `check_research.py`, `check_local_http.py` and `check_network.py`; shared assertions live in `tests/support.py`. Extend the appropriate suite and include it in the runner rather than introducing a test framework. Structural checks enforce the domain dependency boundaries.

Check sample-bit removal, session aborts on failure, matching keys before encryption, rejection of modified ciphertext and replayed messages, and nonce uniqueness. Record simulation seeds and configurations so experiments can be reproduced; report uncertainty and unsuccessful detection cases.

## Commit & Pull Request Guidelines

Use short, imperative commit subjects, for example `docs: clarify QBER sampling assumptions`. Review existing history and uncommitted changes before editing; preserve work already in progress.

PR descriptions should identify the changed proposal sections or modules, explain the rationale, and list validation performed. Link related issues when available; include regenerated figures when conclusions or charts change.

## Security & Research Scope

Use `cryptography`'s `ChaCha20Poly1305` API rather than implementing cryptographic primitives. Never commit or publicly log keys, raw key bits, or authentication secrets. Never reuse a nonce with the same key. Describe results as classical simulation findings; do not claim physical QKD security.

## Documentation & Release Hygiene

Keep `README.md` and `README.vi.md` aligned with implemented commands. Detailed model assumptions and research reproduction belong in `docs/RESEARCH.md`; architecture and migration mapping live in `docs/REORGANIZATION.md`. Keep the proposal unchanged unless the task explicitly calls for proposal edits.

`outputs/` is ignored, not disposable. Preserve manifests, measured CSV/JSON, figures, received files and QA evidence unless deletion is explicitly authorized. Remove verified caches and obsolete one-off work files only after checking references and active use. Never publish authentication files or demo payloads by force-adding the output directory.

Run the base self-check without optional research dependencies when validating a release. The GitHub workflow runs Python 3.14 on Windows and Linux; a local pass does not prove the hosted workflow has passed. Do not choose a license, commit, tag or push without authorization.
