# Delta — Backend: ML Training Surface Parity

**Change**: `fase-7-machine-learning` · **Store**: `openspec` · **Date**: 2026-08-09
**Artifact**: delta spec — MODIFIED REQ-10/11/12 on the existing `backend` capability; all
other backend requirements (REQ-01..09) remain unchanged.

## Purpose

Extends the F3 manual surface to the ML engine: write endpoint `POST /ml/train`, read
endpoints `GET /ml/models` + `GET /ml/metrics`, and CLI `lip ml train|models|metrics`.
Behavior follows the `ml-engine` contract (MLE-09) exactly — manual-only, snapshot-only
reads, `/ml/predict` and `/ml/ranking` remain out of scope. No GET triggers precompute.

## MODIFIED Requirements

### Requirement: REQ-10: Manual Generation Endpoint

`POST /statistics/generate` SHALL trigger snapshot generation/update on demand (C5, D6) and MUST NOT overlap `GET /statistics/...`. The request SHALL identify the lottery (`lottery_id` or code) and an optional bounded scope; the response SHALL be the envelope. An invalid lottery SHALL map to `RESOURCE_NOT_FOUND` (404); generation failure SHALL return `generation_error` (500). The endpoint SHALL never fire during import.

`POST /ml/train` SHALL additionally trigger ML snapshot training on demand (MLE-09), with request fields `lottery_id|code`, `model_set` (`core-5` default), and optional `cut` for the walk-forward window. An invalid lottery SHALL map to `RESOURCE_NOT_FOUND` (404); a training failure SHALL return `training_error` (500); a leakage-invalid split SHALL be rejected. `POST /ml/train` MUST NOT overlap `GET /ml/models` or `GET /ml/metrics` and SHALL never fire during import.
(Previously: manual stats generation endpoint only.)

#### Scenario: generation is manual only

- GIVEN a configured lottery and a running app
- WHEN `POST /statistics/generate` is called
- THEN a `stat_*` snapshot is produced (incremental over an existing valid snapshot, full otherwise per C4) and the response is the 200 envelope.

#### Scenario: unknown lottery maps to 404

- GIVEN a running app
- WHEN `POST /statistics/generate` targets an unknown lottery
- THEN the response is 404 `{code:"RESOURCE_NOT_FOUND"}` and no snapshot is written.

#### Scenario: ml train is manual and scoped (new)

- GIVEN a configured lottery with F4 features and draws ≥ `cut`
- WHEN `POST /ml/train {model_set:"core-5"}` is called
- THEN an `ml_*` snapshot version is produced (idempotent per MLE-08) and the response is the 200 envelope; the run never overlaps reads.

### Requirement: REQ-11: Separate Read Endpoints, No Precompute

`GET /statistics/...` SHALL serve reads only and MUST NOT trigger automatic precompute (C5). Point queries and small windows (LAST N, bounded filters) SHALL be answered on demand (D1) against existing snapshots; a MISSING snapshot SHALL surface a resolution error rather than silently precompute.

`GET /ml/models` SHALL list the model registry (executed + `future-ml` families per MLE-07) for a lottery and `GET /ml/metrics` SHALL return a lottery's active metrics — both read ONLY the stored `ml_*` snapshot and MUST NOT trigger training. A missing `ml_*` snapshot SHALL surface `SNAPSHOT_NOT_FOUND` (404).
(Previously: statistics read endpoints only.)

#### Scenario: read does not precompute

- GIVEN a valid snapshot for a lottery
- WHEN `GET /statistics/{lottery}/frequencies?last=10` runs
- THEN it returns the bounded on-demand result and no generation occurs.

#### Scenario: missing snapshot signals, not computes

- GIVEN a lottery with no snapshot
- WHEN a read targets it
- THEN the response signals the absence (error) and does NOT trigger generation.

#### Scenario: ml reads never train (new)

- GIVEN a lottery without an `ml_*` snapshot
- WHEN `GET /ml/metrics` targets it
- THEN the response is 404 `SNAPSHOT_NOT_FOUND` and `POST /ml/train` is never fired.

### Requirement: REQ-12: CLI Manual Trigger

The CLI (`cli.py`) SHALL expose a manual generation/update command matching the API (D6), accepting lottery scope and optional bounded-window configuration. The run's trigger SHALL be recorded as manual/CLI.

CLI parity SHALL add `lip ml train|models|metrics`: `lip ml train` mirrors `POST /ml/train` (same lottery/`model_set`/`cut` options), `lip ml models` and `lip ml metrics` mirror the reads, printing the same snapshot data.
(Previously: statistics CLI only.)

#### Scenario: CLI generates snapshot

- GIVEN a CLI invocation for a lottery
- WHEN the command runs
- THEN a snapshot is generated (incremental/full per C4), reported, and no import hook fires.

#### Scenario: CLI trains ml snapshot (new)

- GIVEN a CLI invocation with a lottery and `model_set=core-5`
- WHEN `lip ml train` runs
- THEN an `ml_*` snapshot is produced or reported idempotent, and reads (`lip ml metrics`) print stored rows without training.

**Note**: `/ml/predict` and `/ml/ranking` (API_SPEC §8) remain out of scope in this change; the store answers only resolved snapshots (MLE-09), matching the read/write separation owned by the ml-engine spec.