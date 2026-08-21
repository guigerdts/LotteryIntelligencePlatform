# Release Notes — v1.0.0-rc.1

**Tag**: `v1.0.0-rc.1` (2026-08-21) · **State**: Release Candidate — feature frozen, fixes only.

## What is this?

The Lottery Intelligence Platform (LIP) is a full-stack analytical platform for
lottery draw analysis: historical import, statistics, features, probabilistic
and ML/DL models, hyperparameter optimization, walk-forward backtesting,
experiment tracking, graph analysis, ticket generation, an AI assistant and a
React dashboard — all wired through one FastAPI backend (`/api/v1`), one CLI
(`lip`) and an alembic-managed schema (16 migrations, 38 entities).

This RC marks the end of the 19-phase roadmap (2026-08-05 → 2026-08-21).

## Highlights since the last tagged milestone

- **Release audit passed**: ruff clean, zero TODO/FIXME in app code, zero
  hygiene violations, zero hardcoded secrets.
- **Backend**: 1434 tests passing (1 pre-existing skip), **92% coverage**.
- **Frontend**: 137 tests green across 3 consecutive runs after stabilizing
  suite-under-load flakiness.
- **E2E**: core cycle (seed → statistics → dashboard) green against real
  servers and a fresh migrated database.
- **Performance**: harness baselines recalibrated from controlled
  measurements; all ops within tolerance (cold start ~4 s warm-cache;
  heavy ML/DL deps stay lazy at import).
- **Documentation phase completed earlier**: API spec generated from the real
  OpenAPI surface with an anti-drift contract test; architecture, technical
  and user manuals rewritten to match as-built reality.

## Known limitations / debt (documented, non-blocking)

- DL inference has no HTTP router mounted by design (`future-dl`).
- No type checker (mypy) or security linter (bandit) configured yet — post-1.0.
- Optuna/deap were installed late (F19); dependency allowlist tests now enforce them.

## License

Distributed under the [MIT License](LICENSE). Copyright (c) 2026 guigerdts.

## Validation evidence

See `RELEASE_VALIDATION.md` for exact commands, dates and outputs.

## Install

See `INSTALL.md`. Quick start: `uv sync --all-groups`, `alembic upgrade head`,
`lip --help`; frontend: `npm install && npm run dev`.
