# Contributing to BB84 Lab

The project is being prepared for publication. The owner has not selected a license or contribution terms. Discuss those terms with the owner before submitting code for inclusion; do not assume a license from a dependency or GitHub visibility.

## Setup and validation

Use Python 3.14 and follow [README.md](README.md) or [README.vi.md](README.vi.md). Run from the repository root with the virtual environment interpreter:

```sh
python -m pip install -r requirements.txt
python -m pip check
python -m tests.self_check
git diff --check
```

Install `requirements-research.txt` only for plotting or Qiskit/Aer. Preserve dependency pins during unrelated edits. No formatter, linter, type checker or test framework is configured; introduce tooling only for a concrete need. Follow [AGENTS.md](AGENTS.md) and the [architecture reference](docs/REORGANIZATION.md).

## Changes and evidence

Keep changes scoped to domain packages and `python -m` entry points. Extend the relevant `tests/check_*.py` suite through `tests/self_check.py` when behavior needs regression coverage. Never use `-O`, which disables assertions.

For UI changes, exercise the affected dashboard in a browser, including narrow screens, static resources and relevant API errors. Network changes need real loopback socket checks, including PSK mismatch, tampering, replay and interrupted transfer. Cross-host claims require separate device-level evidence.

For research changes, record configuration, seeds, calibration/evaluation separation, uncertainty and unsuccessful detection cases. Use a new output directory. Preserve datasets, manifests and original figures; smoke runs do not substantiate full-study conclusions. See [research documentation](docs/RESEARCH.md).

Preserve Vietnamese proposal numbering, notation and citation identifiers. Keep both READMEs aligned with actual commands; update the unreleased changelog for user-visible changes.

## Privacy and scope

Do not include keys, raw key bits, PSKs, private messages or received files in logs, issues or PR attachments. Use public dummy content. `outputs/` can hold valuable results and private material: never force-add it wholesale. Report suspected secret exposure privately to the owner without posting the secret in an issue.

Use `cryptography` primitives and never reuse a nonce with the same key. Describe findings as classical educational simulation, with no physical QKD security claim.

## Pull requests

Use short imperative subjects, for example `docs: clarify QBER sampling assumptions`. Explain the problem, resulting behavior, affected modules/proposal sections and checks actually run. Include relevant screenshots or regenerated figures when UI or conclusions change. Identify untested platforms and link an existing issue when applicable.

The CI workflow checks the base application on Windows and Ubuntu; a local pass does not replace its hosted result. Publishing, tagging and history changes require separate authorization.
