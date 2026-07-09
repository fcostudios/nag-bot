# E1-S1: Project scaffold + CI

Status: Draft

## Story
As the maintainer, I want a CI-guarded Python project skeleton with Docker packaging, so
that every subsequent story lands on a repo that installs, lints, type-checks, tests and
builds identically everywhere.

## Context
First story; empty repo (README only). Establishes the layout and quality gates every
later story relies on.

## Acceptance Criteria
- AC1: Fresh clone → `pip install -e .[dev] && pytest` passes (≥1 real test).
- AC2: `ruff check .` and `mypy src` pass and are wired as CI steps with pytest in `.github/workflows/ci.yml` (push + PR).
- AC3: `python -m nagbot --version` prints the package version.
- AC4: `docker build .` succeeds; image runs as non-root and defines a HEALTHCHECK (target may fail until E3-S1 — build must succeed).
- AC5: `.gitignore`/`.dockerignore` exclude venvs, caches, `*.db`, `.env`.

## Tasks
- [ ] pyproject.toml (hatchling; runtime + dev deps per architecture §2; ruff/mypy/pytest config) — AC1, AC2
- [ ] src/nagbot/{__init__.py,main.py} with `__version__` + argparse CLI (`--version`, `serve`/`run-once`/`fetch` as placeholders) — AC3
- [ ] tests/unit/test_version.py — AC1
- [ ] .github/workflows/ci.yml (ruff, mypy, pytest on 3.11 & 3.12) — AC2
- [ ] Dockerfile (python:3.12-slim, non-root, HEALTHCHECK /healthz) — AC4
- [ ] .gitignore, .dockerignore — AC5

## Dev Notes
Package dir `src/nagbot/`; hatch build target `packages = ["src/nagbot"]`. Ruff rules
E,F,W,I,UP,B,SIM; mypy strict-ish (`disallow_untyped_defs` on src). CLI is argparse (no
click dependency). `requires-python = ">=3.11"` (dev host is 3.11, container 3.12).

## Testing
`tests/unit/test_version.py`: version string import + CLI `--version` via `python -m`.
Commands: `ruff check . && mypy src && pytest`.

## Dev Agent Record
_(filled during implementation)_

## QA Results
_(filled at review)_
