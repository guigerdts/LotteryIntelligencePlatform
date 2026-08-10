# Delta — Backend: Optimization Surface Parity

**Change**: `fase-9-optimization-engine` · **Store**: `openspec` · **Date**: 2026-08-10
**Artifact**: delta spec — MODIFIED REQ-10/11/12 on the existing `backend` capability; all other backend requirements (REQ-01..09) remain unchanged.

## Purpose

Extends the ML/DL manual surface to the Optimization Engine: write endpoint `POST /opt/train`, read endpoints `GET /opt/models`, `GET /opt/metrics`, `GET /opt/params`, and CLI `lip opt train|models|metrics|params`. Behavior follows the `opt-engine` contract (OE-12) exactly — manual-only, snapshot-only reads, `INSUFFICIENT_DATA` below the 100-draw floor (OE-08), `/opt/predict` and any ranking surface remain out of scope. No GET triggers precompute.

**Merge-order note**: this delta carries the accumulated behavior (stats + `/ml/*` + `/dl/*` + `/opt/*`) so merging preserves all four surfaces.

## MODIFIED Requirements

### Requirement: REQ-10: Manual Generation Endpoint

`POST /statistics/generate` SHALL trigger snapshot generation/update on demand (C5, D6) and MUST NOT overlap `GET /statistics/...`.

`POST /ml/train` SHALL trigger ML snapshot training on demand (MLE-09).

`POST /dl/train` SHALL trigger DL snapshot training on demand (DLE-14).

`POST /opt/train` SHALL additionally trigger optimization on demand (OE-12), with request fields `lottery_id|code`, `optimizer` (`core-4` default: `ga`), `model_set` (`core-5` or `core-3`), `objective_metric` (default `f1`), `objective_direction` (default `maximize`), optional `search_space` (JSON), and optional termination params (`max_generations`, `max_evaluations`, `patience`, `min_delta`). An invalid lottery SHALL map to `RESOURCE_NOT_FOUND` (404); below the 100-real-draw floor the response SHALL be a clean `INSUFFICIENT_DATA` (OE-08); a training failure SHALL return `training_error` (500). `POST /opt/train` MUST NOT overlap the GETs and SHALL never fire during import.

#### Scenario: opt train is manual, scoped, and floored

- GIVEN a configured lottery with ≥100 real draws and F4 features
- WHEN `POST /opt/train {optimizer:"ga", model_set:"core-5", objective_metric:"f1"}` is called
- THEN an `opt_*` snapshot version is produced (idempotent per OE-10) and the response is the 200 envelope; never overlapping reads.

#### Scenario: opt train refuses below the data floor

- GIVEN a lottery with fewer than 100 real draws
- WHEN `POST /opt/train` is called
- THEN the response is a clean `INSUFFICIENT_DATA` and no `opt_*` rows are written.

### Requirement: REQ-11: Separate Read Endpoints, No Precompute

`GET /statistics/...` SHALL serve reads only and MUST NOT trigger automatic precompute (C5).

`GET /ml/models` and `GET /ml/metrics` read ONLY `ml_*` snapshots.

`GET /dl/models` and `GET /dl/metrics` read ONLY `dl_*` snapshots.

`GET /opt/models` SHALL list the optimizer registry (core-4 families per OE-09) for a lottery and `GET /opt/metrics` SHALL return a lottery's active optimization metrics — both read ONLY the stored `opt_*` snapshot and MUST NOT trigger optimization. A missing `opt_*` snapshot SHALL surface `SNAPSHOT_NOT_FOUND` (404). `GET /opt/params` SHALL return the best found parameters for a specific model from the active optimization snapshot. No `GET` SHALL expose raw convergence history in the list endpoint; `/opt/predict` and ranking/recommendation surfaces SHALL NOT be registered (OE-12).

#### Scenario: opt reads never optimize

- GIVEN a lottery without an `opt_*` snapshot
- WHEN `GET /opt/metrics` targets it
- THEN the response is 404 `SNAPSHOT_NOT_FOUND` and `POST /opt/train` is never fired.

#### Scenario: opt routes are limited to train/models/metrics/params

- GIVEN the API router after F9
- WHEN route discovery runs
- THEN only `POST /opt/train`, `GET /opt/models`, `GET /opt/metrics`, `GET /opt/params` are registered; `/opt/predict`, ranking, and export routes do not exist.

### Requirement: REQ-12: CLI Manual Trigger

The CLI (`cli.py`) SHALL expose a manual generation/update command matching the API (D6).

CLI parity SHALL add `lip ml train|models|metrics`.

CLI parity SHALL add `lip dl train|models|metrics`.

CLI parity SHALL add `lip opt train|models|metrics|params`: `lip opt train` mirrors `POST /opt/train` (same lottery/`optimizer`/`model_set`/`objective`/termination options and floor behavior), `lip opt models`, `lip opt metrics`, and `lip opt params` mirror the reads, printing the same snapshot data. No CLI predict/export command SHALL be added.

#### Scenario: CLI trains opt snapshot

- GIVEN a CLI invocation with a lottery and `optimizer=ga`
- WHEN `lip opt train` runs
- THEN an `opt_*` snapshot is produced or reported idempotent (or `INSUFFICIENT_DATA` below the floor), and reads (`lip opt metrics`) print stored rows without training.

**Note**: `/opt/predict` and ranking (API_SPEC §10) remain out of scope in this change; the store answers only resolved snapshots (OE-12), matching the read/write separation owned by the opt-engine spec. API_SPEC §10 SHALL NOT include `/opt/predict` in the delivered surface.
