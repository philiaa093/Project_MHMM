# Changelog

No version or release tag has been assigned by this document.

## Unreleased

### Organization

- Separate core algorithms, in-process sessions, simulation HTTP, independent network roles, research and shared infrastructure under `bb84_lab/`.
- Separate browser assets and assert suites by responsibility.
- Replace the former application/demo modules with `python -m bb84_lab.local` and `python -m bb84_lab.simulation`. See the [migration mapping](docs/REORGANIZATION.md).

### Release preparation

- Add linked English/Vietnamese READMEs with source-checkout commands, mode distinctions and research/security limits.
- Preserve detailed model/research instructions in `docs/RESEARCH.md`; record cleanup and verification in `docs/RELEASE_AUDIT.md`.
- Add contribution guidance, editor/line-ending rules, Python/research ignore rules and base Windows/Ubuntu GitHub Actions checks.
- Remove verified obsolete work artifacts and bytecode caches while retaining research results and QA evidence.

Licensing and contribution terms remain pending owner confirmation. Release preparation does not change dependency pins or protocol behavior.
