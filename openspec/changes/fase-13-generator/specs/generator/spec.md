# Spec — Generator (`generator`)

**Change**: `fase-13-generator` · **Store**: `openspec` · **Date**: 2026-08-11

## Purpose

Generate reproducible lottery combinations weighted by F12 scores and F5 distributions. MVP: generate + persist only.

## Requirements

| ID | Requirement | P |
|----|-------------|---|
| GEN-001 | Generate: selection→allocation→sample→validate→persist. Exactly `count`. | P0 |
| GEN-002 | Count: integer [1,100], default 10. Invalid → GEN_COUNT_INVALID (422). | P0 |
| GEN-003 | Selection: active F12 required. Absent → GEN_NO_SELECTION (404). `selection_id` override. | P0 |
| GEN-004 | Allocation: `cᵢ = floor(sᵢ × count / total_score)`. Remainder desc score, rank tie-break. `Σcᵢ == count`. | P0 |
| GEN-005 | Sampling: F5 distributions, `isolated_rng(seed)`. Same inputs → identical output. | P0 |
| GEN-006 | Lottery: distinct in [min,max], super in range, sorted. Invalid → resample. | P0 |
| GEN-007 | Lifecycle: `active\|retired\|failed`. Atomic. Version monotonic per (lottery_id, selection_id). | P0 |
| GEN-008 | Fingerprint: SHA-256(lottery_id, selection_id, count, seed, VERSION). Same → existing. | P0 |
| GEN-009 | Seed: `derive_seed(fingerprint, lottery_id, count, VERSION)` SHA-256. Override allowed. | P0 |
| GEN-010 | API: POST /gen/generate, GET /gen/combinations, POST /gen/snapshot, GET /gen/snapshots. | P0 |
| GEN-011 | CLI: `lip gen generate\|combinations\|snapshot\|snapshots`. JSON. | P0 |
| GEN-012 | Persistence: `gen_snapshots` + `gen_combinations` (score NULLABLE). Migration 0015. | P0 |
| GEN-013 | Errors: GenServiceError. Codes: GEN_NO_SELECTION(404), GEN_NO_DISTRIBUTION(404), GEN_LOTTERY_NOT_FOUND(404), GEN_COUNT_INVALID(422), GEN_SNAPSHOT_NOT_FOUND(404), GEN_DUPLICATE_SNAPSHOT(409), GEN_SPACE_EXHAUSTED(422). GEN_SPACE_EXHAUSTED: valid combination space is insufficient, or MAX_ATTEMPTS=1000 is reached without completing exactly `count`. No partial count. No warning fallback. | P0 |
| GEN-014 | No-distribution: no F5 → GEN_NO_DISTRIBUTION (404). No fallback. | P0 |
| GEN-015 | F5 boundary: ProbabilityService unmodified. Reuses ONLY derive_seed, isolated_rng, _canonical_json. | P0 |
| GEN-016 | F11/F12 boundary: consumes selection + F5. No re-rank, no re-score. | P0 |
| GEN-017 | No evaluation in MVP. | P1 |
| GEN-018 | No filters in MVP. | P1 |

### Scenarios

- **GEN-001**: lottery active selection + F5, count=10 → 10 combos.
- **GEN-002**: count=0 → 422.
- **GEN-003**: no active selection → 404.
- **GEN-004**: scores [0.5,0.3,0.2] count=10 → [5,3,2]. scores [0.34,0.33,0.33] ranks[1,2,3] count=10 → [4,3,3].
- **GEN-005**: same inputs twice → identical combos.
- **GEN-006**: [1,15,22,33,41,49] valid → persisted. Duplicate → resampled.
- **GEN-007**: new fingerprint → old retired, new active.
- **GEN-008**: same fingerprint → returned, no new rows.
- **GEN-009**: same inputs → identical seed. seed=42 → deterministic.
- **GEN-010**: POST generate → GenerationResult. GET combinations → list.
- **GEN-011**: `lip gen generate --lottery-id 1` → JSON.
- **GEN-012**: upgrade → tables. downgrade → dropped.
- **GEN-013**: no selection → 404. no distribution → 404. space exhausted → 422, zero combos persisted.
- **GEN-014**: no F5 → 404, zero combos.
- **GEN-015**: probability/ unchanged.
- **GEN-016**: scores as weights only.

## API

| Method | Path | Request | Errors |
|--------|------|---------|--------|
| POST | /gen/generate | `{lottery_id, count?, seed?, selection_id?}` | 404, 422 |
| GET | /gen/combinations | `?lottery_id&snapshot_id?` | 404 |
| POST | /gen/snapshot | `{lottery_id, snapshot_id, status}` | 404, 422 |
| GET | /gen/snapshots | `?lottery_id` | 404 |

## CLI

| Command | Args |
|---------|------|
| lip gen generate | --lottery-id, [--count], [--seed], [--selection-id] |
| lip gen combinations | --lottery-id, [--snapshot-id] |
| lip gen snapshot | --lottery-id, --snapshot-id, --status |
| lip gen snapshots | --lottery-id |

## NFRs

| ID | Category | Requirement |
|----|----------|-------------|
| NFR-GEN-01 | Determinism | Same (selection, lottery, count, seed) → identical output |
| NFR-GEN-02 | Correctness | Exactly `count` combinations |
| NFR-GEN-03 | Performance | Bounded by max count=100 |
| NFR-GEN-04 | Security | No secrets; inputs validated |
| NFR-GEN-05 | Maintainability | generators/ isolated; F5 boundary |
| NFR-GEN-06 | Testability | Strict TDD; pytest verifiable |

## Traceability

| Proposal | Requirements |
|----------|--------------|
| N1 | GEN-001, GEN-002 |
| N2 | GEN-004, GEN-005 |
| N3 | GEN-009 |
| N4 | GEN-015, GEN-016 |
| N5 | GEN-012 |
| C1 | GEN-006 |
| C6 | GEN-014 |
| C7 | GEN-007, GEN-008, GEN-012 |
| C8 | GEN-010, GEN-011 |
| C4 | GEN-017 |
| C5 | GEN-018 |

---

**Ready for design (sdd-design).**
