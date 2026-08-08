# Archive Report: Fase 5 — Probability Engine

**Change**: fase-5-probability-engine · **Archived**: 2026-08-08
**Verify**: GO (independent, c8b4338) · **Tests**: 80/80 PASS

## Summary

Fase 5 implemented the Probability Engine: 7 canonical probability methods
(hypergeometric, binomial, Poisson, empirical, Monte Carlo, Bayes, conditional
univariate windowed) with deterministic computation, snapshot persistence, and
API/CLI surface.

## Commits (stacked-to-main)

| PR | Commit | Scope |
|----|--------|-------|
| PR1a | 380d1cc | Foundation: seam, fingerprint, determinism, registry, providers |
| PR1b | 3f4e537 | Engine puro (7 methods) + 33 fixtures |
| PR2a | f5fa43d | ORM models + migration 0007 |
| PR2b | d7109ca | snapshot_store + service + adapters |
| PR3a | 520092b | Schemas + API routes |
| PR3b | d635e6f | CLI + E2E tests |
| PR4 | 95b6742 | Docs + final gates |
| fix | 5f0d86a | 3 CRITICAL + 4 HIGH from verify |
| fix | c8b4338 | Conditional divisor fix |

## Spec Synced

- Delta spec → `openspec/specs/probability-engine/spec.md` (187 lines)
- 18 requirements (PES-01..11, PM-01..07), 20 scenarios

## Verification Evidence

| Gate | Status |
|------|--------|
| Tests 80/80 | ✅ |
| Ruff clean | ✅ |
| C1 adapters | ✅ |
| C2 MC persistence | ✅ |
| C3 conditional | ✅ |
| H1 empirical | ✅ |
| Isolation | ✅ |
| No out-of-scope | ✅ |
| Git clean | ✅ |

## Files Created (11 new)

- `probability/__init__.py`
- `probability/engine.py`
- `probability/providers.py`
- `probability/registry.py`
- `probability/fingerprint.py`
- `probability/determinism.py`
- `probability/snapshot_store.py`
- `models/prob_snapshot.py`
- `models/prob_value.py`
- `services/probability_service.py`
- `api/v1/probability.py`
- `schemas/probability.py`
- `alembic/versions/0007_probability_tables.py`

## Tag

`fase-5-probability-engine-complete` at c8b4338
