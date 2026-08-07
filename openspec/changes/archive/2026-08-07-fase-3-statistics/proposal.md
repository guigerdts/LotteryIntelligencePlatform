# Proposal: Statistics Engine (Fase 3)

## Intent
Descriptive statistics over normalized draws (Fase 3: frequencies, gaps, distributions, trends, entropy, correlations) as a decoupled, result-only engine writing to an independent `stat_*` domain.

## Binding Decisions (technical contract)
- **D1 Execution**: Hybrid. Precompute costly/accumulative metrics; on-demand ONLY for point queries and small windows (last N, filters).
- **D2 Persistence**: DO NOT reuse `datasets`. Independent `stat_*` schema; datasets remain draw snapshots only.
- **D3 Time axis**: `draw_number` is the official reference; `draw_date` metadata only. Every series MUST be deterministic w.r.t. `draw_number`.
- **D4 jackpot/winners**: optional; MUST ignore NULLs; never impute.
- **D5 Scope**: Statistics ONLY. Probability, Scoring, Analytics, ML, Prediction OUT OF SCOPE.
- **D6 Update**: NO ImportService hooks; generation/update MANUAL (CLI/API), never during import.

## Bound Architectural Principles
Statistics readonly w.r.t. Core (never mutate Draw/Dataset/ImportJob); writes only to `stat_*`; multi-lottery from day one; reproducible; each snapshot records `generator_version`; no full scans.

## Additional Binding Constraints (user-approved contract additions)
- **C1 Versioning**: `generator_version` mandatory on every `stat_*` snapshot; any algorithm change bumps the version; existing snapshots are NEVER recomputed in place.
- **C2 Determinism**: same dataset/checksum + same `generator_version` ⇒ bit-identical results.
- **C3 Strict read-only**: Statistics never modifies `draw`, `draw_number`, `super_number`, `dataset`, `import_*`; writes to `stat_*` only.
- **C4 Incremental mandatory**: forbid recomputing the full history when a valid snapshot exists; spec defines exactly when full-rebuild vs incremental.
- **C5 API**: separate `POST /statistics/generate` from `GET /statistics/...`; NO GET endpoint ever triggers automatic precompute.
- **C6 Scalability**: every massive aggregation operates in batches; forbidding loading all draws into memory.
- **C7 Indexes**: beyond the proposed `(lottery_id, number)` index, design MUST justify any extra index via a concrete query case.

## Scope
### In Scope
- `stat_*` schema: frequency, last-N cache, averages, gaps snapshots.
- Manual generation (CLI/API) + migration incl. `(lottery_id, number)` index on `draw_numbers`.
- On-demand point/small-window queries (D1).
### Out of Scope
- Probability/Scoring/Analytics/ML/Prediction (D5). Writes to `datasets`/`draw`/`imports`; import hooks (D6).

## Capabilities
### New Capabilities
- `statistics-engine` (`openspec/specs/statistics-engine/spec.md`): descriptive stats over normalized draws; `stat_*` snapshots with `generator_version`, checksum, immutable lock (mirrors IE-09 selection→checksum→version→lock on new schema, D2).
### Modified Capabilities
- `backend`: manual stats generation/update API + CLI → delta spec.

## Approach
Per-lottery snapshot engine (D3): select draws → compute metric → checksum + `generator_version` → write `stat_*` → lock immutable. On-demand for bounded queries (D1). CLI/API only (D6); read-only re: core domains (D2).

## Affected Areas
| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/backend/app/statistics/` | New | Stats engine |
| `backend/src/backend/app/services/statistics_service.py` | New | Snapshot orchestration |
| `backend/alembic/versions/0005_*` | New | `stat_*` + index migration |
| `backend/src/backend/app/api/`, `cli.py` | New | Manual stats endpoint/CLI |

## Risks
| Risk | Likelihood | Mitigation |
|------|------------|------------|
| `draw_numbers` full scan | Med | `(lottery_id, number)` index |
| Stats drift | Low | Snapshot `generator_version`+checksum, explicit regen |
| NULL jackpot/winners | Low | Ignore NULLs, never impute (D4) |

## Rollback Plan
Downgrade drops `stat_*` only (additive); no core-schema change; `git revert` of PR, safe since stats never mutates core tables.

## Dependencies
On F1 `core-domain` + F2 `import-engine` specs (stable).

## Success Criteria
- [ ] Same draws+rules regenerate identical checksum
- [ ] Per-`lottery_id` independent stats
- [ ] No path mutates core/dataset/imports tables
- [ ] `generator_version` on every snapshot; never via import

## Recorded (config rules)
- Inconsistency: missing `(lottery_id, number)` index → additive migration needed.
- Improvement: reuse IE-09 snapshot pattern on `stat_*`.