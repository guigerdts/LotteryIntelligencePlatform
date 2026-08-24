# Spec — Generator Output (`generator-output`)

**Change**: `winning-numbers-pipeline` · **Store**: `openspec` · **Date**: 2026-08-23
**Artifact**: base spec — promoted from change `winning-numbers-pipeline` (archive).
**Sources**: official rules verified in Engram #1870 (`domain/baloto-revancha-official-rules`): 5 distinct numbers 1–43 + Superbalota 1–16; the 0+SB refund tier makes SB mandatory. Seams: `gen_service.py:167` persists `"super_number": None, "score": None`; `sampling.py:77` passes `None` SB into `validate_combination`; `LotteryConfig` protocol already declares `super_number_min`/`super_number_max`.
**Verify**: pytest (`backend/tests/gen/`).

## Requirements

### REQ-01: Legality Enforced Pre-Persist With Explicit Codes

| Field | Value |
|-------|-------|
| **ID** | R1 |
| **RFC** | MUST |

Every persisted combination SHALL satisfy the official bet shape resolved from `LotteryConfig`: exactly `numbers_to_select` distinct integers within `[min_number, max_number]` (5 distinct in 1–43) plus one Superbalota within `[super_number_min, super_number_max]` (1–16). `validate_combination(numbers, super_number, cfg)` SHALL gate persistence — no combination may be written without passing it WITH a non-null Superbalota. Violations SHALL raise typed errors defined in `services/errors.py`: `GEN_INVALID_NUMBERS` (count, duplicate, range, or ordering violation) and `GEN_INVALID_SUPER_NUMBER` (SB missing or out-of-range); both map to HTTP 422 via the global handler. Existing `GEN_SPACE_EXHAUSTED` semantics (resampling exhaustion, zero combos persisted) are unchanged.

#### Scenario: all generated combos legal

- GIVEN a seeded generate request against config 5 / 1–43 / SB 1–16
- WHEN generation completes
- THEN every persisted row passes `validate_combination(numbers, sb, cfg)` with `sb is not None`

#### Scenario: illegal SB rejected before persist

- GIVEN a candidate Superbalota outside 1–16
- WHEN validation gates the write
- THEN error code `GEN_INVALID_SUPER_NUMBER` raises and zero rows persist

#### Scenario: duplicate number rejected before persist

- GIVEN a candidate `[7, 7, 12, 30, 41]`
- WHEN validation gates the write
- THEN error code `GEN_INVALID_NUMBERS` raises and zero rows persist

### REQ-02: Reproducible SB From Historical Marginals

| Field | Value |
|-------|-------|
| **ID** | R2 |
| **RFC** | MUST |

Sampling SHALL emit `(combination, super_balota)` pairs: the Superbalota is drawn per combination from the historical SB-marginal distribution on the SAME isolated RNG stream as the numbers, so one seed reproduces the entire ticket including SB. Because stream consumption changes, `GENERATOR_VERSION` (`generators/version.py`) SHALL be bumped in the same slice so `generation_seed`/`snapshot_fingerprint` outputs differ from every pre-change value — new snapshots MUST NOT alias legacy fingerprints. Legacy rows (`super_number IS NULL`) stay readable; post-change generations contain zero `NULL` Superbalotas. Marginal fallbacks: sparse/incomplete SB marginals SHALL fall back to uniform over 1–16; zero imported draws SHALL fail with `GEN_NO_HISTORY` and persist nothing.

#### Scenario: SB present, in range, byte-reproducible

- GIVEN seed S generates a snapshot twice from identical history
- WHEN the outputs are compared
- THEN every combination carries an integer SB in 1–16 and both runs are identical including SB

#### Scenario: version bump prevents fingerprint aliasing

- GIVEN `GENERATOR_VERSION` incremented
- WHEN fingerprints are computed for a new generation
- THEN none equals a pre-change snapshot fingerprint, and legacy rows still deserialize

#### Scenario: no history fails explicitly

- GIVEN zero imported draws
- WHEN generation runs
- THEN `GEN_NO_HISTORY` raises and no snapshot persists

### REQ-03: Non-Null Selection-Weighted Score

| Field | Value |
|-------|-------|
| **ID** | R3 |
| **RFC** | MUST |

Every persisted combination SHALL carry a non-null, finite selection-weighted score computed from its entry-selection weight and the probability distribution, replacing the `"score": None` placeholder at `gen_service.py:167`. Generator responses (`/gen/generate`, `/gen/combinations`) SHALL expose `super_number` and `score` for every combination.

#### Scenario: scores always populated and exposed

- GIVEN any successful seeded generation
- WHEN persisted rows and the API payload are inspected
- THEN every row has a non-null finite `score` and responses echo `super_number` and `score`
