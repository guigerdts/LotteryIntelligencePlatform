# Delta — Backend: Manual Statistics Generation Surface

**Change**: `fase-3-statistics` · **Store**: `openspec` · **Date**: 2026-08-07
**Artifact**: delta spec — ADDED surface on the existing `backend` capability; all existing backend requirements (REQ-01..09) remain unchanged.

## Purpose

Adds the manual statistics generation/update surface to the existing Fase 0 backend scaffold (`backend/app/api`, `cli.py`): a dedicated `POST /statistics/generate` strictly separated from `GET /statistics/...` read endpoints, plus an idempotent CLI entry. No GET endpoint triggers automatic precompute (C5); stats generation is never wired into import (D6). All behavior follows the statistics-engine STE-01..13 contract.

## ADDED Requirements

### Requirement: Manual Stats Generation Endpoint

`POST /statistics/generate` SHALL trigger snapshot generation/update on demand (C5, D6) and MUST NOT overlap `GET /statistics/...`. The request SHALL identify the lottery (`lottery_id` or code) and an optional bounded scope; the response SHALL be the Fase 0 envelope. An invalid lottery SHALL map to `RESOURCE_NOT_FOUND` (404); generation failure SHALL return `generation_error` (500). The endpoint SHALL never fire during import.

#### Scenario: generation is manual only

- GIVEN a configured lottery and a running app
- WHEN `POST /statistics/generate` is called
- THEN a `stat_*` snapshot is produced (incremental over an existing valid snapshot, full otherwise per C4) and the response is the 200 envelope.

#### Scenario: unknown lottery maps to 404

- GIVEN a running app
- WHEN `POST /statistics/generate` targets an unknown lottery
- THEN the response is 404 `{code:"RESOURCE_NOT_FOUND"}` and no snapshot is written.

### Requirement: Separate Read Endpoints, No Precompute

`GET /statistics/...` SHALL serve reads only and MUST NOT trigger automatic precompute (C5). Point queries and small windows (LAST N, bounded filters) SHALL be answered on demand (D1) against existing snapshots; a MISSING snapshot SHALL surface a resolution error rather than silently precompute.

#### Scenario: read does not precompute

- GIVEN a valid snapshot for a lottery
- WHEN `GET /statistics/{lottery}/frequencies?last=10` runs
- THEN it returns the bounded on-demand result and no generation occurs.

#### Scenario: missing snapshot signals, not computes

- GIVEN a lottery with no snapshot
- WHEN a read targets it
- THEN the response signals the absence (error) and does NOT trigger generation.

### Requirement: CLI Manual Trigger

The CLI (`cli.py`) SHALL expose a manual generation/update command matching the API (D6), accepting lottery scope and optional bounded-window configuration. The run's trigger SHALL be recorded as manual/CLI.

#### Scenario: CLI generates snapshot

- GIVEN a CLI invocation for a lottery
- WHEN the command runs
- THEN a snapshot is generated (incremental/full per C4), reported, and no import hook fires.

**Note**: Read/write separation (C5), read-only re core tables (C3), and out-of-scope rules are owned by statistics-engine (STE-02/05/10/13); backend re-exposes them through these API/CLI seams.

---

**Next**: `sdd-design` (request/response schemas, CLI flags, snapshot resolution).