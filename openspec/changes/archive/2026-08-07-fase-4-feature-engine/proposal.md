# Proposal: Feature Engine (Fase 4) — Core-Domain First Slice

## Intent

Stand up an independent, deterministic, provider-driven Feature Engine turning draws
into auditable, versioned features for later ML/DL consumers. Fase 3 proved the
snapshot pattern (`stat_*`). This first slice validates the ENGINE — registry,
providers, fingerprint, snapshot persistence — with ~8-10 Core-Domain-only features.

## Scope

### In Scope
- `feature_engineering/` seams: `registry.py`, `providers.py` (Protocols), `engine.py` (pure, no DB), `fingerprint.py` (canonical SHA-256), `features/` (base modules).
- `FeatureRegistry` with dependency registration, cycle detection, topological order.
- Providers: `DrawProvider` adapter (keyset `ORDER BY draw_number, id`), `StatisticsProvider` adapter (passive active-snapshot reads; validates provider architecture only).
- ~8-10 Core-Domain base features: draw identity (parity/primes/Fibonacci/multiples/high-low), per-draw distribution (sum/mean/median/mode/range/var/std/skew/kurtosis), tens bucketing, current gap/age.
- `feature_snapshots` + `feature_values` schema (migration 0006) mirroring `stat_*`; normalized payload, not per-row independent values.
- Declarative-only registration of `future-statistics`/stats-sourced features (extensibility proof; no computation).

### Out of Scope
- Statistics-sourced feature computation (frequencies/gaps/positions/entropy) — contract validation only.
- Meta-features, incremental fold, co-occurrences (D6 → Fase 6 Graph Engine), ML, Probability, Prediction, scheduler.
- Any modification of Statistics, Core Domain, or `stat_*`.

## Capabilities

### New Capabilities
- `feature-engine`: registry w/ cycle detection + topo order; provider protocols; pure deterministic engine + fingerprint; snapshots/values persistence; versioning/fingerprint decoupled from Statistics.

### Modified Capabilities
None — read-only w.r.t. Core Domain and Statistics; no existing spec behavior changes.

## Approach

Reuse the Fase 3 snapshot contract as seam: `feature_snapshots` header (lottery_id,
feature_set, version, feature_engine_version, checksum, input_fingerprint, status,
is_locked, draw_count, draws_from, draws_to) + `feature_values`. Snapshots immutable,
versioned, locked, checksummed, reproducible; `draw_number` axis (draw_date = metadata
only). Input fingerprint = canonical SHA-256 over {draws range+checksum,
per-feature {id, version, params}, optional stats snapshot identity}. Engine depends
only on provider protocols; writes confined to `feature_*`; strict read-only to
Core/Statistics; no circular deps. Entropy consumed via StatisticsProvider (available),
never recomputed (D4).

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `app/feature_engineering/` | New | Registry, providers, engine, fingerprint, features |
| `app/repositories/feature_*_repository.py` | New | Snapshot + values persistence |
| `app/models/feature_snapshot.py`, `feature_value.py` | New | Schema models |
| `app/services/feature_engine_service.py` | New | Orchestration seam |
| `backend/migrations/*.py` | New | Migration 0006 schema |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Determinism drift (multi-source) | Med | Canonical fingerprint; Decimal-exact accumulators; explicit ordering |
| Coupling to Statistics internals | Med | Provider protocols are the only seam |
| Stats `core` absent | Med | Stats-sourced `skipped`, never guessed; Core features run regardless |
| Cycling dependency graph | Med | Cycle detection + topo sort at registration, fail-fast |

## Rollback Plan

Down-migration 0006 drops `feature_*` tables; remove `feature_engineering/` package.
No writes touch Core/Statistics — revert is clean and non-destructive.

## Dependencies

- Fase 3 Statistics `stat_*` contract (stable read-only seam; STE-10 no precompute).
- Core Domain draw/lottery reads (read-only).
- Co-occurrences deferred to Fase 6 (Graph Engine).

## Success Criteria

- [ ] Registry loads with cycle detection; illegal cycle rejected with reported set.
- [ ] Determinism: same inputs ⇒ byte-identical `feature_values` (fingerprint reproducible).
- [ ] Stats-sourced features declared but not computed; Core features produce values.
- [ ] All writes confined to `feature_*`; Core/Statistics never mutated.
- [ ] `backend/.venv/bin/pytest` green; ruff clean.