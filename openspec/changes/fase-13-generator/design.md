# Design: F13 — Intelligent Generator

## Technical Approach

F13 adds a deterministic combination generation layer consuming F12 active selections and F5 probability distributions. Follows the established snapshot lifecycle (active/retired/failed, monotonic version, SHA-256 fingerprint). Pipeline: resolve F12 selection → validate count → allocate count via GEN-004 integer-micro-unit rule → load F5 distributions per entry → sample with isolated_rng → validate lottery rules with resampling → persist snapshot atomically. F5 `ProbabilityService` is NOT modified; F11/F12 untouched.

## Architecture Decisions

| Decision | Choice | Alternatives | Rationale |
|----------|--------|-------------|-----------|
| **Allocation rule** | Integer micro-units (`SCORE_SCALE=10**6`) + floor + remainder by desc score | Float `score * count // total_score`, `Decimal`, rank-only | Exact integer arithmetic; `Σcᵢ == count` guaranteed; no float drift (GEN-004) |
| **Resampling policy** | MAX_ATTEMPTS=1000, typed error GEN_SPACE_EXHAUSTED | Silent degradation, unlimited retry | Bounded runtime; predictable failure for tiny spaces |
| **Seed derivation** | `derive_seed(fingerprint, lottery_id, count, VERSION)` SHA-256 | Timestamp, user-only | Deterministic; optional override (GEN-009) |
| **Module boundary** | New `generators/` reusing ONLY `derive_seed`/`isolated_rng`/`_canonical_json` | Extend F5 probability engine | Different concerns; F5 untouched (NFR-GEN-05) |
| **Score column** | Nullable Float on `gen_combinations` (N5) | Not nullable, excluded | Future weight hook; NULL = "no evaluation" in MVP |
| **Duplicate rejection** | Set of frozensets of tuples, bounded by count ≤ 100 | DB lookup per attempt | In-memory O(1); max 100 entries fits comfortably |

## Data Flow

    API/CLI ──→ GenService.generate()
                   │
                   ├── 1. Resolve F12 selection (active) → entries[]
                   ├── 2. Validate count [1,100]
                   ├── 3. Allocate: micro-unit integer arithmetic → allocation[entry_id]
                   ├── 4. For each entry with cᵢ > 0:
                   │       ├── Load F5 probability snapshot for lottery
                   │       ├── Build weighted number→probability from entry score
                   │       └── Sample cᵢ combos via isolated_rng
                   ├── 5. Validate each combo (lottery rules) + resample if needed
                   ├── 6. Sort combos, assign position
                   ├── 7. Compute fingerprint
                   ├── 8. Idempotency check → return existing if match
                   ├── 9. Retire old active snapshot (if any)
                   └── 10. Persist snapshot + combinations atomically
                          │
                          └── DB: gen_snapshots + gen_combinations

## Module Structure

```
backend/src/backend/app/generators/
├── __init__.py              # Package seam (docstring only)
├── types.py                 # GenerationConfig, Combination, Allocation
├── allocation.py            # allocate_count() — GEN-004 micro-unit integer rule
├── sampling.py              # sample_combinations() — F5-weighted sampling + resampling
├── validation.py            # validate_combination() — lottery rules check
├── snapshot_store.py        # GenSnapshotStore — gen_* I/O owner (lifecycle pattern)
└── version.py               # GENERATOR_VERSION constant

backend/src/backend/app/models/
├── gen_snapshot.py          # GenSnapshot ORM
└── gen_combination.py       # GenCombination ORM

backend/src/backend/app/services/
└── gen_service.py           # GenService — composition root

backend/src/backend/app/api/v1/
└── gen.py                   # API router (4 endpoints)

backend/src/backend/app/schemas/
└── gen.py                   # Pydantic v2 schemas

backend/alembic/versions/
└── 0015_gen_tables.py       # Migration
```

## Domain Model / ORM

### GenSnapshot
`gen_snapshots`: `id` PK, `lottery_id` FK→lottery RESTRICT, `selection_id` FK→meta_selections RESTRICT, `version` String(32), `status` String(16) CHECK `active|retired|failed`, `fingerprint` String(64), `config_json` Text nullable, `created_at` DateTime(tz). Unique `(lottery_id, selection_id, fingerprint)`. Index `ix_gen_snapshots_lottery_selection` on `(lottery_id, selection_id)`.

### GenCombination
`gen_combinations`: `id` PK, `snapshot_id` FK→gen_snapshots RESTRICT, `position` Integer, `numbers` Text (JSON array), `super_number` Integer nullable, `score` Float nullable, `created_at` DateTime(tz). Index `ix_gen_combinations_snapshot` on `(snapshot_id)`.

### Migration 0015
Additive only. `upgrade()` creates both tables + indexes. `downgrade()` drops indexes + tables in reverse FK order. No existing table modified. Template: `0014_meta_tables.py`.

## Generation Pipeline

1. **Resolve selection**: Query `MetaSelection` WHERE lottery_id=X AND status='active'. None → GEN_NO_SELECTION (404).
2. **Read entries**: Query `MetaSelectionEntry` WHERE selection_id=Y. Empty → GEN_NO_SELECTION.
3. **Validate count**: Integer [1,100], default 10. Invalid → GEN_COUNT_INVALID (422).
4. **Allocate**: Micro-unit integer arithmetic (see GEN-004 section below). Assert `Σcᵢ == count`.
5. **Load distributions**: For each entry with cᵢ > 0, read active `ProbSnapshot` for lottery. None → GEN_NO_DISTRIBUTION (404). Build number→probability map from `prob_values`.
6. **Sample**: For each entry, use `isolated_rng(seed)` with weighted sampling (numbers weighted by F5 distribution × entry score). Generate `cᵢ` combinations per entry.
7. **Validate**: Each combo must have distinct numbers in [min_number, max_number], sorted, super_number in range. Invalid → resample (GEN-006).
8. **Resampling policy**: MAX_ATTEMPTS=1000 per combination. If no valid non-duplicate found → raise `GenServiceError(GEN_SPACE_EXHAUSTED)`. Zero combos persisted. Duplicate detection via `set[frozenset[tuple[int]]]` bounded by count ≤ 100.
9. **Fingerprint**: `SHA-256(_canonical_json({lottery_id, selection_id, count, seed, VERSION}))`.
10. **Idempotency**: Same fingerprint → return existing snapshot, no new rows (GEN-008).
11. **Persist**: Retire old active for (lottery_id, selection_id), create new active with version=next monotonic, insert combinations. Atomic commit.

## GEN-004 Allocation — Exact Integer Micro-Unit Arithmetic

### Procedure

```python
SCORE_SCALE = 10**6  # Fixed scale factor; documented constant

def allocate_count(entries: list[SelectionEntry], count: int) -> list[tuple[int, int]]:
    """Return [(entry_index, allocated_count)] with Σcᵢ == count guaranteed."""
    # Step 1: Scale scores to integer micro-units.
    # This is a REPRESENTATION conversion (float→int), not an allocation rounding.
    # Multiplying by 1e6 and rounding to nearest integer produces a stable integer
    # representation of each score. The rounding error per entry is ≤ 0.5 micro-unit,
    # bounded and deterministic — it does NOT compound or drift the allocation sum.
    total_score = sum(e.score for e in entries)
    if total_score == 0:
        raise GenServiceError("GEN_COUNT_INVALID", "total score is zero")
    score_micros = [int(round(e.score * SCORE_SCALE)) for e in entries]
    total_micros = sum(score_micros)

    # Step 2: Integer floor allocation — NO float arithmetic.
    allocations = []
    remainder = count
    for i, micros in enumerate(score_micros):
        c = micros * count // total_micros  # integer floor division
        allocations.append((i, c))
        remainder -= c

    # Step 3: Distribute remainder by descending micro-unit score (tie: lower rank first).
    ranked = sorted(range(len(entries)), key=lambda i: (-score_micros[i], entries[i].rank))
    for idx in ranked:
        if remainder <= 0:
            break
        allocations[idx] = (allocations[idx][0], allocations[idx][1] + 1)
        remainder -= 1

    return allocations
```

### Why Σcᵢ == count (Proof)

Let `mᵢ = round(sᵢ × SCALE)` and `M = Σmᵢ`. After floor: `fᵢ = mᵢ × count // M`. Then `Σfᵢ ≤ count` because each floor discards a non-negative remainder. The remaining `count - Σfᵢ` units are distributed one-per-entry in descending score order, consuming exactly the deficit. Therefore `Σcᵢ == count` always.

### Precision Regression Test Cases

| Input | Expected | Assertion |
|-------|----------|-----------|
| scores=[0.7], count=90 | [90] | sum == 90 |
| scores=[0.5,0.3,0.2], count=10 | [5,3,2] | sum == 10 |
| scores=[0.34,0.33,0.33], ranks=[1,2,3], count=10 | [4,3,3] | sum == 10, entry with rank=1 gets the +1 |
| scores=[0.999999,0.000001], count=100 | [100,0] | sum == 100 |
| scores=[0.333,0.333,0.334], count=100 | [33,33,34] | sum == 100 |

**CRITICAL**: `score=0.7, count=90` MUST produce 63 for the 0.7 entry (not 62). Micro-unit approach: `round(0.7 * 1e6) = 700000`, `700000 * 90 // 1000000 = 63`. Exact.

## Resampling (GEN-006)

- **Acceptance predicate**: `len(combo) == numbers_to_select`, all in [min,max], all distinct, sorted, super_number in range if required, combo not in `generated_set`.
- **MAX_ATTEMPTS**: 1000. Lottery pool C(n,k) is typically large (C(50,6) ≈ 15M); 1000 is conservative.
- **Space exhaustion**: When MAX_ATTEMPTS reached → `GenServiceError(GEN_SPACE_EXHAUSTED, "combination space exhausted after 1000 attempts")`. No partial count. No warning fallback. Zero combos persisted.
- **Duplicate set**: `set[frozenset[tuple[int, ...]]]` — O(1) membership, memory ≤ 100 entries.

## GenService — Error Taxonomy

| Error Code | HTTP | When |
|------------|------|------|
| GEN_NO_SELECTION | 404 | No active F12 selection for lottery |
| GEN_NO_DISTRIBUTION | 404 | No active F5 probability snapshot for lottery |
| GEN_LOTTERY_NOT_FOUND | 404 | Invalid lottery_id |
| GEN_COUNT_INVALID | 422 | count < 1 or > 100 |
| GEN_SNAPSHOT_NOT_FOUND | 404 | Requested snapshot doesn't exist |
| GEN_DUPLICATE_SNAPSHOT | 409 | Same fingerprint, active snapshot exists |
| GEN_SPACE_EXHAUSTED | 422 | Valid combination space insufficient OR MAX_ATTEMPTS=1000 reached without completing exactly `count`. No partial count. No warning fallback. |

All subclass `ServiceError` per existing `MetaServiceError` pattern. `GenServiceError` defined in `services/errors.py`.

## API Endpoints

| Method | Path | Request | Response | Errors |
|--------|------|---------|----------|--------|
| POST | /gen/generate | `{lottery_id, count?, seed?, selection_id?}` | `GenerationResult` | 404, 422 |
| GET | /gen/combinations | `?lottery_id&snapshot_id?` | `CombinationList` | 404 |
| POST | /gen/snapshot | `{lottery_id, snapshot_id, status}` | `SnapshotResult` | 404, 422 |
| GET | /gen/snapshots | `?lottery_id` | `SnapshotList` | 404 |

Standard envelope `{success, data|error, timestamp}`. Router prefix `/gen`, tags `["generator"]`.

## CLI Commands

| Command | Arguments | Output |
|---------|-----------|--------|
| `lip gen generate` | `--lottery-id`, `[--count]`, `[--seed]`, `[--selection-id]` | JSON generation result |
| `lip gen combinations` | `--lottery-id`, `[--snapshot-id]` | JSON combination list |
| `lip gen snapshot` | `--lottery-id`, `--snapshot-id`, `--status` | JSON snapshot update |
| `lip gen snapshots` | `--lottery-id` | JSON snapshot list |

## Determinism Design

- **GENERATOR_VERSION**: `"1.0.0"` in `generators/version.py`. Bumped on algorithm change only.
- **Seed**: `derive_seed(input_fingerprint, model_params={"lottery_id": L, "count": C}, n_simulations=C)` where `input_fingerprint = SHA-256(_canonical_json({selection_fingerprint, lottery_id, count, GENERATOR_VERSION}))`. Reuses F5 `derive_seed` — no new derivation logic.
- **Canonical serialization**: `_canonical_json` from `probability.fingerprint` reused directly.
- **Reproducibility**: Same (selection_id, lottery_id, count, seed) → identical `isolated_rng` sequence → identical combinations.

## Boundary Enforcement

**F13 DOES**: Read `meta_selections`/`meta_selection_entries`, read `prob_snapshots`/`prob_values`, read `lottery`, persist `gen_snapshots`/`gen_combinations`.

**F13 DOES NOT**: Modify `probability/` module. Modify `meta/` module. Modify `exp_*`/`bt_*`/`ml_*`/`dl_*`/`opt_*` tables. Import `ProbabilityService` at module level (lazy import only). Execute engines. Re-rank or re-score selections.

**Reuse surface**: `derive_seed(input_fingerprint, model_params, n_simulations)`, `isolated_rng(seed)`, `_canonical_json(payload)` — all from `probability.determinism` and `probability.fingerprint`.

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | `allocate_count()` exactness: Σ == count for all cases | Pure function, parametrized |
| Unit | `allocate_count()` precision regression: 0.7×90=63, [0.5,0.3,0.2]→[5,3,2], [0.34,0.33,0.33]→[4,3,3] | Pure function, dedicated test |
| Unit | `validate_combination()` lottery rules | Pure function, parametrized |
| Unit | `sample_combinations()` determinism (same seed → same output) | Mock F5 data, verify output |
| Unit | `sample_combinations()` resampling MAX_ATTEMPTS exhaustion → GEN_SPACE_EXHAUSTED | Mock tiny pool, verify error |
| Unit | `sample_combinations()` duplicate rejection | Mock known-duplicate path |
| Unit | `GenSnapshotStore` lifecycle (create/retire/idempotency) | SQLite test DB |
| Unit | `GenService` error paths (no selection, no distribution, invalid count) | SQLite test DB |
| Unit | `GenService` idempotency (same fingerprint → return existing) | SQLite test DB |
| Integration | API endpoints (POST generate, GET combinations) | FastAPI TestClient |
| Integration | CLI commands (`lip gen generate`) | subprocess + JSON parse |

### Precision Regression Test (MANDATORY)

```python
@pytest.mark.parametrize("scores,count,expected,rank_ties", [
    ([0.7], 90, [90], []),
    ([0.5, 0.3, 0.2], 10, [5, 3, 2], []),
    ([0.34, 0.33, 0.33], 10, [4, 3, 3], [1, 2, 3]),
])
def test_allocate_count_exact(scores, count, expected, rank_ties):
    entries = [SelectionEntry(model_id=f"m{i}", engine_type="bt",
              rank=rank_ties[i] if rank_ties else i, score=s) for i, s in enumerate(scores)]
    result = allocate_count(entries, count)
    allocations = [c for _, c in result]
    assert sum(allocations) == count
    assert sorted(allocations, reverse=True) == sorted(expected, reverse=True)
```

## Migration / Rollout

Migration 0015 is purely additive (2 new tables). `alembic upgrade` creates tables; `alembic downgrade -1` drops them. No data migration. No existing tables modified.

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file classification, or process-integration boundary.

## Risks

| Risk | Level | Mitigation |
|------|-------|------------|
| Float precision in allocation | RESOLVED | Integer micro-unit arithmetic with SCALE=10**6; proof that Σcᵢ == count |
| GEN_SPACE_EXHAUSTED spec alignment | RESOLVED | GEN_SPACE_EXHAUSTED(422) integrated in GEN-013 error taxonomy per authorized spec amendment |
| F5 distribution unavailable | MEDIUM | GEN_NO_DISTRIBUTION (404), no fallback per C6 |
| Resampling infinite loop | LOW | MAX_ATTEMPTS=1000 hard limit |

## Open Questions

- None — all defects resolved. GEN_SPACE_EXHAUSTED authorized. Float precision resolved by integer micro-units.

---

**Ready for tasks (sdd-tasks).**
