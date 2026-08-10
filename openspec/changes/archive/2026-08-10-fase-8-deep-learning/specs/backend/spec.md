# Delta — Backend: DL Training Surface Parity

**Change**: `fase-8-deep-learning` · **Store**: `openspec` · **Date**: 2026-08-09
**Artifact**: delta spec — MODIFIED REQ-10/11/12 on the existing `backend` capability; all
other backend requirements (REQ-01..09) remain unchanged.

## Purpose

Extends the ML manual surface to the DL engine: write endpoint `POST /dl/train`, read
endpoints `GET /dl/models` + `GET /dl/metrics`, and CLI `lip dl train|models|metrics`.
Behavior follows the `dl-engine` contract (DLE-14) exactly — manual-only, snapshot-only reads,
`INSUFFICIENT_DATA` below the 100-draw floor (DLE-10), `/dl/predict` and any ranking/weights-
download surface remain out of scope. No GET triggers precompute.

**Merge-order note**: the `ml-engine` delta (`fase-7-machine-learning`) also MODIFIES
REQ-10/11/12 and is not yet archived. This block therefore carries the accumulated behavior
(stats + `/ml/*` + `/dl/*`) so merging either order preserves all three surfaces; the archive
phase SHALL warn before merging and reconcile.

## MODIFIED Requirements

### Requirement: REQ-10: Manual Generation Endpoint

`POST /statistics/generate` SHALL trigger snapshot generation/update on demand (C5, D6) and MUST NOT overlap `GET /statistics/...`. The request SHALL identify the lottery (`lottery_id` or code) and an optional bounded scope; the response SHALL be the envelope. An invalid lottery SHALL map to `RESOURCE_NOT_FOUND` (404); generation failure SHALL return `generation_error` (500). The endpoint SHALL never fire during import.

`POST /ml/train` SHALL additionally trigger ML snapshot training on demand (MLE-09), with request fields `lottery_id|code`, `model_set` (`core-5` default), and optional `cut` for the walk-forward window. An invalid lottery SHALL map to `RESOURCE_NOT_FOUND` (404); a training failure SHALL return `training_error` (500); a leakage-invalid split SHALL be rejected. `POST /ml/train` MUST NOT overlap `GET /ml/models` or `GET /ml/metrics` and SHALL never fire during import.

`POST /dl/train` SHALL additionally trigger DL snapshot training on demand (DLE-14), with request fields `lottery_id|code`, `model_set` (`core-3` default), optional `window` (`W`, default 10, bounds 2..20), and optional `cut` for the window-aware split. An invalid lottery SHALL map to `RESOURCE_NOT_FOUND` (404); below the 100-real-draw floor the response SHALL be a clean `INSUFFICIENT_DATA` (DLE-10); a leakage-invalid (straddling/shuffled) split SHALL be rejected (DLE-05); a training failure SHALL return `training_error` (500). `POST /dl/train` MUST NOT overlap the GETs and SHALL never fire during import.
(Previously: manual stats generation endpoint only.)

#### Scenario: generation is manual only

- GIVEN a configured lottery and a running app
- WHEN `POST /statistics/generate` is called
- THEN a `stat_*` snapshot is produced (incremental over an existing valid snapshot, full otherwise per C4) and the response is the 200 envelope.

#### Scenario: unknown lottery maps to 404

- GIVEN a running app
- WHEN `POST /statistics/generate` targets an unknown lottery
- THEN the response is 404 `{code:"RESOURCE_NOT_FOUND"}` and no snapshot is written.

#### Scenario: ml train is manual and scoped

- GIVEN a configured lottery with F4 features and draws ≥ `cut`
- WHEN `POST /ml/train {model_set:"core-5"}` is called
- THEN an `ml_*` snapshot version is produced (idempotent per MLE-08) and the response is the 200 envelope; the run never overlaps reads.

#### Scenario: dl train is manual, scoped, and floored

- GIVEN a configured lottery with ≥100 real draws and F4 features
- WHEN `POST /dl/train {model_set:"core-3", window:10}` is called
- THEN a `dl_*` snapshot version is produced (idempotent per DLE-12) and the response is the 200 envelope; never overlapping reads.

#### Scenario: dl train refuses below the data floor

- GIVEN a lottery with fewer than 100 real draws
- WHEN `POST /dl/train` is called
- THEN the response is a clean `INSUFFICIENT_DATA` and no `dl_*` snapshot or weights are written.

### Requirement: REQ-11: Separate Read Endpoints, No Precompute

`GET /statistics/...` SHALL serve reads only and MUST NOT trigger automatic precompute (C5). Point queries and small windows (LAST N, bounded filters) SHALL be answered on demand (D1) against existing snapshots; a MISSING snapshot SHALL surface a resolution error rather than silently precompute.

`GET /ml/models` SHALL list the model registry (executed + `future-ml` families per MLE-07) for a lottery and `GET /ml/metrics` SHALL return a lottery's active metrics — both read ONLY the stored `ml_*` snapshot and MUST NOT trigger training. A missing `ml_*` snapshot SHALL surface `SNAPSHOT_NOT_FOUND` (404).

`GET /dl/models` SHALL list the DL model registry (executed + `future-dl` families per DLE-11) for a lottery and `GET /dl/metrics` SHALL return a lottery's active DL metrics — both read ONLY the stored `dl_*` snapshot and MUST NOT trigger training. A missing `dl_*` snapshot SHALL surface `SNAPSHOT_NOT_FOUND` (404). No `GET` SHALL expose model weights; `/dl/predict` and ranking/recommendation surfaces SHALL NOT be registered (DLE-14).
(Previously: statistics read endpoints only.)

#### Scenario: read does not precompute

- GIVEN a valid snapshot for a lottery
- WHEN `GET /statistics/{lottery}/frequencies?last=10` runs
- THEN it returns the bounded on-demand result and no generation occurs.

#### Scenario: missing snapshot signals, not computes

- GIVEN a lottery with no snapshot
- WHEN a read targets it
- THEN the response signals the absence (error) and does NOT trigger generation.

#### Scenario: ml reads never train

- GIVEN a lottery without an `ml_*` snapshot
- WHEN `GET /ml/metrics` targets it
- THEN the response is 404 `SNAPSHOT_NOT_FOUND` and `POST /ml/train` is never fired.

#### Scenario: dl reads never train

- GIVEN a lottery without a `dl_*` snapshot
- WHEN `GET /dl/metrics` targets it
- THEN the response is 404 `SNAPSHOT_NOT_FOUND` and `POST /dl/train` is never fired.

#### Scenario: dl routes are limited to train/models/metrics

- GIVEN the API router after F8
- WHEN route discovery runs
- THEN only `POST /dl/train`, `GET /dl/models`, `GET /dl/metrics` are registered; `/dl/predict`, ranking, and weights-download routes do not exist.

### Requirement: REQ-12: CLI Manual Trigger

The CLI (`cli.py`) SHALL expose a manual generation/update command matching the API (D6), accepting lottery scope and optional bounded-window configuration. The run's trigger SHALL be recorded as manual/CLI.

CLI parity SHALL add `lip ml train|models|metrics`: `lip ml train` mirrors `POST /ml/train` (same lottery/`model_set`/`cut` options), `lip ml models` and `lip ml metrics` mirror the reads, printing the same snapshot data.

CLI parity SHALL add `lip dl train|models|metrics`: `lip dl train` mirrors `POST /dl/train` (same lottery/`model_set`/`window`/`cut` options and floor behavior), `lip dl models` and `lip dl metrics` mirror the reads, printing the same snapshot data. No CLI predict/export/weights command SHALL be added.
(Previously: statistics CLI only.)

#### Scenario: CLI generates snapshot

- GIVEN a CLI invocation for a lottery
- WHEN the command runs
- THEN a snapshot is generated (incremental/full per C4), reported, and no import hook fires.

#### Scenario: CLI trains ml snapshot

- GIVEN a CLI invocation with a lottery and `model_set=core-5`
- WHEN `lip ml train` runs
- THEN an `ml_*` snapshot is produced or reported idempotent, and reads (`lip ml metrics`) print stored rows without training.

#### Scenario: CLI trains dl snapshot

- GIVEN a CLI invocation with a lottery and `model_set=core-3`
- WHEN `lip dl train` runs
- THEN a `dl_*` snapshot is produced or reported idempotent (or `INSUFFICIENT_DATA` below the floor), and reads (`lip dl metrics`) print stored rows without training.

**Note**: `/dl/predict` and `/dl/ranking` (API_SPEC §9) remain out of scope in this change;
the store answers only resolved snapshots (DLE-14), matching the read/write separation owned
by the dl-engine spec. API_SPEC §9 SHALL be updated to remove `/dl/predict` from the delivered
surface (docs-drift reconciliation, F7 precedent).