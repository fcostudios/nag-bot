# E1-S1: Project scaffold + CI

Status: Done

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
- [x] pyproject.toml (hatchling; runtime + dev deps per architecture §2; ruff/mypy/pytest config) — AC1, AC2
- [x] src/nagbot/{__init__.py,main.py} with `__version__` + argparse CLI (`--version`, `serve`/`run-once`/`fetch` as placeholders) — AC3
- [x] tests/unit/test_version.py — AC1
- [x] .github/workflows/ci.yml (ruff, mypy, pytest on 3.11 & 3.12) — AC2
- [x] Dockerfile (python:3.12-slim, non-root, HEALTHCHECK /healthz) — AC4
- [x] .gitignore, .dockerignore — AC5

## Dev Notes
Package dir `src/nagbot/`; hatch build target `packages = ["src/nagbot"]`. Ruff rules
E,F,W,I,UP,B,SIM; mypy strict-ish (`disallow_untyped_defs` on src). CLI is argparse (no
click dependency). `requires-python = ">=3.11"` (dev host is 3.11, container 3.12).

## Testing
`tests/unit/test_version.py`: version string import + CLI `--version` via `python -m`.
Commands: `ruff check . && mypy src && pytest`.

## Dev Agent Record
- Added `src/nagbot/__main__.py` (not in original task list) so `python -m nagbot` works — required by AC3's CLI test.
- Hatch version sourced from `src/nagbot/__init__.py` (`dynamic = ["version"]`).
- Dev env runs Python 3.11.15; CI matrix covers 3.11 + 3.12 (container is 3.12-slim).
- Deviation: local `docker build` impossible in this dev sandbox — its network policy 403-blocks Docker Hub/ECR blob CDNs (proxy confirmed, not a Dockerfile issue). AC4 build verification delegated to the CI `docker` job, which runs on every push.

## QA Results
- AC1 ✅ `pip install -e .[dev] && pytest` → 2 passed.
- AC2 ✅ `ruff check .` clean, `mypy src` clean (3 files); both wired in ci.yml with pytest, push+PR triggers.
- AC3 ✅ `python -m nagbot --version` → `nagbot 0.1.0` (test_cli_version).
- AC4 ⚠→✅ Dockerfile complete (non-root user, HEALTHCHECK /healthz, curl installed); local build blocked by sandbox CDN policy — verified green via CI docker job after push.
- AC5 ✅ .gitignore/.dockerignore cover venv, caches, *.db, .env.
- Story-DoD: tests written, suite green, no unrelated changes. **Gate: PASS** (AC4 evidence via CI, noted above).
