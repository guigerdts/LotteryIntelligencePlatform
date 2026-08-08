# Spec — Probability Engine

**Change**: fase-5-probability-engine · **Store**: openspec · **Date**: 2026-08-08
**Artifact**: spec (this change) — new capability `probability-engine` (delta for archive merge).

## Purpose

An independent, deterministic, result-only engine computing event probabilities from lottery rules and stored data: exact combinatorial values (hypergeometric, binomial, Poisson), empirical rates from `stat_*` frequencies, univariate windowed conditional probability, fixed-seed Monte Carlo simulation, and empirical-Bayes posteriors with declared priors. It mirrors the F3/F4 snapshot contract — dedicated `prob_*` schema, canonical SHA-256 fingerprint, `draw_number` axis, `active|retired|failed` lifecycle, `PROB_GENERATOR_VERSION`, manual-only generation, multi-lottery. The engine depends ONLY on its own provider Protocols (never Core/Statistics/Feature internals) and writes ONLY to `prob_*`. Monte Carlo sits inside the byte-identical determinism gate via an isolated seeded PRNG. Prediction, ML/DL, number generation, betting, pairwise/joint conditionals, feature-sourcing, and `analytics/` composition are out of scope (F6/F7+).

Engine-level requirements are `PES-01..`; the 7 canonical methods are `PM-01..PM-07`.

## Requirements

### PES-01: Independent `prob_*` Schema (D1/D4)

The engine SHALL persist to a dedicated `prob_snapshots` (header) + `prob_values` (normalized payload: `model_id, model_version, subject, draw_number|NULL, value, params`) schema, mirroring `stat_*`/`feature_*`. It MUST NOT reuse `datasets` or the draft `montecarlo_runs` shape (C6; F4 D5 precedent). MC persists aggregates + quantiles only — NEVER raw simulation histories.

#### Scenario: writes confined to prob_*
- GIVEN a generation run over existing draws
- WHEN it completes
- THEN only `prob_*` rows are written; no Core, `stat_*`, `feature_*`, `datasets`, or `dataset_draws` change.

#### Scenario: MC never persists raw runs
- GIVEN a completed Monte Carlo simulation
- WHEN the snapshot is inspected
- THEN only aggregates/quantiles and per-subject values exist; no per-simulation history rows.

### PES-02: Strict Read-Only vs Core/Statistics/Feature

The engine MUST NOT modify `lottery`, `draw`, `draw_numbers`, `super_number`, `dataset*`, `stat_*`, or `feature_*`; writes target `prob_*` only. Reads are passive and never trigger generation.

#### Scenario: all non-prob rows unchanged
- GIVEN a generation run and an on-demand read
- WHEN both execute
- THEN all Core, `stat_*`, and `feature_*` rows are byte-identical before and after.

### PES-03: `draw_number` Axis, No FK to Draw

`draw_number` SHALL be the official series axis; `draw_date` is metadata. `prob_values.draw_number` is a logical identifier — the schema MUST NOT add a physical FK to `draw` (FES-03 parity); joins use `draw_number` only.

#### Scenario: non-monotonic dates
- GIVEN draws with non-monotonic `draw_date`
- WHEN any probability series is produced
- THEN order and values follow `draw_number`, never `draw_date`.

### PES-04: `prob_generator_version` & No In-Place Recompute

Every `prob_snapshots` snapshot SHALL carry `prob_generator_version` (independent of `STATS_`/`FEATURE_` versions) plus per-model `model_version`. Snapshots MUST NEVER be recomputed in place; a change creates a new version. `n_simulations` is a versioned parameter — it participates in fingerprint and seed (D2).

#### Scenario: locked snapshot survives bump
- GIVEN an immutable active snapshot at v3
- WHEN a changed model version or `n_simulations` runs
- THEN a new version is written and v3 stays untouched.

### PES-05: Bit-Identical Determinism (incl. MC Seed Policy)

Same {draws range + stat links, model versions/params, `n_simulations`} + same `prob_generator_version` MUST yield byte-identical results. Every read SHALL be `ORDER BY draw_number, id`; accumulators are INTEGER/`Decimal`-exact; `float` NEVER enters a checksum or persisted value; canonical JSON `sort_keys=True`; fingerprint = canonical SHA-256. Monte Carlo SHALL use an isolated `random.Random(seed)` — never global `random`; seed = `int.from_bytes(sha256(canonical_json({input_fingerprint, model_params, n_simulations, PROB_GENERATOR_VERSION})).digest()[:16], "big")`.

#### Scenario: identical rerun matches
- GIVEN the same draws, models, params, `n_simulations`, and version across two runs
- WHEN both complete
- THEN outputs, checksums, and `input_fingerprint` are byte-identical.

#### Scenario: MC param change yields new deterministic run
- GIVEN a locked MC snapshot
- WHEN a run with a different `n_simulations` or version executes
- THEN its seed differs, its result differs deterministically, and the old snapshot keeps its seed/values.

### PES-06: Provider Protocols Only

The engine defines `DrawReader`, `StatSnapshotReader`, `FeatureSnapshotReader` as `Protocol`s at the composition root. It MUST import ONLY these interfaces and MUST NEVER import concrete `statistics`/`feature_engineering`/models/repository internals. Adapters SHALL wrap `statistics_service.read_*` / `feature_engine_service.read_*` (FES-06 parity). Missing data ⇒ skipped/absent, never guessed (STE-09).

#### Scenario: decoupled from F3/F4 internals
- GIVEN statistics or feature internals change behind their services
- WHEN Probability reads through the providers
- THEN it needs no code change and imports no concrete module.

### PES-07: Snapshot Lifecycle `active|retired|failed`

`prob_snapshots` SHALL implement exactly one active per `(lottery_id, model_set)`; replace retires the old row in the same transaction; a failed run persists a `failed` dead header — never `active` or `partial`. `is_locked` is set on commit.

#### Scenario: replace retires, failure marks failed
- GIVEN an active snapshot
- WHEN a new generation succeeds
- THEN the old row is retired atomically; on failure, only a `failed` header is written.

### PES-08: No Scheduler — Manual Only

Generation/rebuild SHALL be manual (CLI `lip probability generate|rebuild` / API `POST /probability/generate`), never during import or on read. Reads SHALL answer from stored `prob_*` and MUST NOT precompute or trigger generation; a missing snapshot SHALL surface `SNAPSHOT_NOT_FOUND` (404).

#### Scenario: read never generates
- GIVEN a lottery with no snapshot
- WHEN a read targets it
- THEN the response is 404 `SNAPSHOT_NOT_FOUND` and no generation fires.

### PES-09: Migration & Rollback

New migration `0007_prob_tables` (`down_revision = "0006_feature_tables"`) SHALL add `prob_snapshots` and `prob_values`; downgrade drops ONLY `prob_*`. New indexes (3) `ix_psnap_lottery_model_status`, `ix_pval_snapshot_id`, `ix_pval_subject` SHALL be justified by access paths in the design.

#### Scenario: rollback is non-destructive
- GIVEN a DB with Core + statistics + feature tables
- WHEN migration 0007 is downgraded
- THEN `prob_*` is dropped and Core/`stat_*`/`feature_*` remain intact.

### PES-10: Multi-Lottery

Every snapshot SHALL be scoped by `lottery_id`; lotteries MUST be independent.

#### Scenario: per-lottery isolation
- GIVEN two lotteries
- WHEN each is generated
- THEN snapshots are per-`lottery_id`; rules (`min_number`/`max_number`/`numbers_to_select`) come from each lottery's own row.

### PES-11: Empty / 0-Draw Handling (acceptance constraint)

An empty live DB is an acceptance constraint, not an implementation blocker: behavior SHALL be specified and tested via fixtures; a 0-draw / no-snapshot state SHALL be handled gracefully (e.g. `draws_from=0, draws_to=0` header or a `validation_error`), never a crash.

#### Scenario: fixture-driven verification
- GIVEN an empty DB and a fixture CSV
- WHEN the pipeline imports and generates
- THEN the snapshot validates against hand-computed fixture expectations.

### PM-01: Hypergeometric Distribution

The engine SHALL compute `P(X=k) = C(r,k)·C(N−r, n−k) / C(N,n)` — `N` from lottery rules (`max−min+1`), `n = numbers_to_select`, `r` = success-population param — using exact combinatorial integers and Decimal (never float). Inputs: lottery rules via `StatSnapshotReader`/draws. Output: `model_id="hypergeometric"`, rows per match count k.

#### Scenario: single-number match odds
- GIVEN lottery min=1, max=45, numbers_to_select=5, r=1 (one specific number)
- WHEN hypergeometric is computed
- THEN `P(k=1) = C(1,1)·C(44,4)/C(45,5)` exact — e.g. 1/9 for that pool.

### PM-02: Binomial Distribution

The engine SHALL compute `P(X=k) = C(n,k) · p^k · (1−p)^(n−k)` with declared `p` and `n` (default `n = numbers_to_select`), exact Decimal. Output rows per `k` in `0..n`.

#### Scenario: exact binomial
- GIVEN n=5, p=0.5 (declared)
- WHEN PM-02 runs
- THEN values match hand-computed `C(5,k)/32` exactly, and no float is persisted.

### PM-03: Poisson Distribution

The engine SHALL compute `P(X=k) = λ^k e^−λ / k!` in Decimal (exact `k!`, λ declared or derived from stored `stat_*` means), float rejected. Output rows per `k`.

#### Scenario: exact Poisson
- GIVEN declared λ = 2 and k in 0..3
- WHEN PM-03 runs
- THEN the values, computed with a fixed Decimal precision context, match the reference to that precision.

### PM-04: Empirical Probability

The engine SHALL compute the empirical probability `P(subject) = observed_count(subject) / total_draws` from the active `stat_*` frequency/`stat` snapshot (via `StatSnapshotReader`), per subject number. Same snapshot ⇒ identical values.

#### Scenario: frequency-derived rate
- GIVEN a stat snapshot with count 12 occurrences of number 7 over 60 draws
- WHEN PM-04 runs
- THEN the value for number 7 is 12/60 = 0.2 (Decimal).

### PM-05: Monte Carlo Simulation

The engine SHALL simulate per-lottery draws under declared inputs with an isolated `random.Random(seed)` (PES-05 seed policy) and compute per-subject empirical probabilities + quantiles. Same seed, params, `n_simulations`, version ⇒ byte-identical run and persisted aggregates. Output: per-subject probabilities + `p50/p90/p99` quantiles in `prob_values`.

#### Scenario: seeded rerun is identical
- GIVEN two MC runs with identical seed-producing inputs (fingerprint, params, `n_simulations`, version)
- WHEN both execute
- THEN both produce identical persisted aggregates and checksum.

### PM-06: Bayesian Posterior

The engine SHALL compute an empirical-Bayes posterior by pure fold: `posterior ∝ prior × likelihood` over declared prior params and frozen input count data; same priors + inputs ⇒ same posterior. Priors declared as model parameters; posterior values in `prob_values`.

#### Scenario: same priors give same posterior
- GIVEN declared priors and a frozen frequency snapshot
- WHEN PM-06 runs twice
- THEN both produce byte-identical posterior values and checksum.

### PM-07: Conditional Probability

The engine SHALL compute the univariate conditional probability of a subject event within a declared `draw_number`-ordered window — e.g. `count_in_window / window_size` from raw draws or `stat_*`. It SHALL NOT estimate pairwise or joint conditionals; those remain declared-but-not-computed until F6 (Graph).

#### Scenario: windowed univariate conditional
- GIVEN a last-20 window where number 9 appears in 8 draws
- WHEN PM-07 runs with that window
- THEN the conditional is 8/20 (0.4) — never a joint/co-occurrence value.

---

**Note**: New capability created at archive from change delta `fase-5-probability-engine`. Added `prob_*` snapshot model and 7 canonical methods (PM-01..PM-07) on the F3/F4 contract. Lands in a domain subfolder at merge-archive.