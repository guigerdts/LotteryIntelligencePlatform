# Spec — Performance (`performance`)

**Change**: `fase-16-performance` · **Store**: `openspec` · **Date**: 2026-08-18
**Artifact**: spec (this change) — NEW capability `performance`: transversal requirements binding every Fase-16 optimization slice to the exploration baselines, the proposal §5 baseline→target table, and the GF-1 byte-identical determinism hard gate.

## Purpose

Transversal, capability-spanning performance contracts for Fase 16: GF-1 determinism is a HARD GATE (a serial-vs-parallel byte difference blocks the slice), every optimization must be evidenced by a baseline→result measurement with the exact proposal §5 commands, slices stay ≤400 authored lines with no size exception, CPU-bound parallel engines use bounded process pools (max_workers=2, never threads), the snapshot read cache is an in-process bounded LRU keyed on `(snapshot_id, endpoint)` (D3, no external store), and cold start `import backend.app.main` must drop from 25.3 s to ≤8 s (S6). S1 (S1a/S1b) is correctness — it carries no performance target.

## Requirements Overview

| ID | Requirement | RFC |
|----|-------------|-----|
| PFM-01 | GF-1 byte-identical determinism hard gate | MUST |
| PFM-02 | Baseline→target measurement evidence (proposal §5 commands) | MUST |
| PFM-03 | ≤400 authored lines per slice; no size exception | MUST |
| PFM-04 | Bounded process-pool parallelism; pure workers | MUST |
| PFM-05 | In-process LRU snapshot read cache (D3) | MUST |
| PFM-06 | Cold-start target — `import backend.app.main` ≤8 s (S6) | MUST |

## Requirements

### PFM-01: GF-1 Byte-Identical Determinism Hard Gate

Every parallelization or caching slice (S3, S4, S5) SHALL preserve GF-1 byte-identical determinism. Any serial-vs-parallel byte difference in output, checksum, or fingerprint **blocks the slice** — GF-1 is a gate, not a warning. Parallel results SHALL be assembled in frozen deterministic order (backtest `window_index`; ML sorted number). Existing determinism suite (`tests/test_determinism.py`, statistics g9, ML/DL/bt determinism e2e) MUST remain green after every slice.

#### Scenario: parallel output is byte-identical to serial

- GIVEN a completed serial run of a parallelizable engine
- WHEN the same run executes through the parallel path
- THEN the outputs, fingerprints, and checksums are byte-identical
- AND a single byte difference fails the slice and reverts the change

#### Scenario: frozen deterministic order

- GIVEN an engine with parallel independent work units
- WHEN results are collected
- THEN they are ordered by the frozen key (`window_index` / sorted number), never by completion time

### PFM-02: Baseline→Target Measurement Evidence

Each perf slice (S2–S7) SHALL record a baseline and a result measurement using the EXACT command and threshold from the proposal §5 baseline→target table before it is accepted. No optimization MAY be merged without both measurements. Correctness slices (S1a/S1b) are exempt — their acceptance is test pass/fail.

#### Scenario: measurement-before/after recorded

- GIVEN a perf slice with a target in the §5 table
- WHEN the slice is submitted for review
- THEN the change includes the §5 baseline value, the result value, and the exact §5 command used for both

#### Scenario: target not met blocks acceptance

- GIVEN a perf slice whose measured result misses the §5 target
- WHEN the slice is evaluated
- THEN it is not accepted; the optimization is reverted or re-scoped

### PFM-03: ≤400 Authored Lines Per Slice

Every slice SHALL stay within 400 authored lines (additions + deletions, per the proposal §8 partition review). No `size:exception` is permitted for Fase 16. A slice exceeding 400 lines SHALL be split into autonomous chained PRs before review.

#### Scenario: oversized slice rejected

- GIVEN a slice whose authored diff exceeds 400 lines
- WHEN it is prepared for review
- THEN it is split or reduced; it is not submitted whole

### PFM-04: Bounded Process-Pool Parallelism; Pure Workers

CPU-bound parallel engines (S3 backtest windows, S4 ML per-number fits) SHALL use processes — `concurrent.futures.ProcessPoolExecutor` with `max_workers=2` — never threads (GIL). Worker tasks SHALL be module-level, picklable, and pure: NO DB session or engine object MAY be created inside a worker. Work-unit functions SHALL take plain data inputs and return plain data outputs.

#### Scenario: bounded worker pool

- GIVEN a 3-core, memory-limited box
- WHEN a parallel engine runs
- THEN the process pool never exceeds `max_workers=2`

#### Scenario: no DB sessions in workers

- GIVEN a parallel run of backtest windows or ML fits
- WHEN a worker executes a work unit
- THEN it performs no database access and holds no session/engine object

### PFM-05: In-Process LRU Snapshot Read Cache (D3)

The snapshot read cache SHALL be an in-process LRU keyed on `(snapshot_id, endpoint)` serving immutable snapshot payloads. It MUST NOT use Redis or any external store. Invalidation SHALL derive from snapshot immutability: a new snapshot version is a new `snapshot_id` → a new key; no write-through is required. Cache size SHALL be bounded to respect the ~2.4 GB-available memory box. A cached read MUST return a payload byte-identical to a fresh DB-built read (golden check).

#### Scenario: cache hit returns identical payload

- GIVEN an immutable snapshot payload previously read
- WHEN the same `(snapshot_id, endpoint)` is read again
- THEN the payload is served from the in-process LRU and is byte-identical to a fresh read

#### Scenario: version bump invalidates by key

- GIVEN a cached snapshot at `snapshot_id=X`
- WHEN a new snapshot version `X+1` is generated and read
- THEN the read targets the new key and never returns the stale `X` payload

#### Scenario: no external store

- GIVEN the cache contract (D3)
- WHEN any read path uses the cache
- THEN it is in-process only; no Redis/external dependency is introduced

### PFM-06: Cold-Start Target (S6)

Deferring heavy imports (torch in `dl/*`, sklearn in `ml/engine.py`) SHALL make `import backend.app.main` complete in ≤8 s, measured with `time python -c "import backend.app.main"` (baseline 25.3 s, proposal §5). Behavior SHALL be identical before/after deferral: the deferred dependency MUST still be importable and functional at first use.

#### Scenario: cold-start target met

- GIVEN the command `time python -c "import backend.app.main"`
- WHEN measured after S6
- THEN the wall time is ≤8 s

#### Scenario: deferred import still works on first use

- GIVEN an app with deferred heavy imports
- WHEN a DL/ML entry function first executes
- THEN torch/sklearn import successfully at first use and behavior is unchanged