# Delta for Numbers Orchestrator

**Change**: `numbers-pipeline-gen-only` · **Date**: 2026-08-25

## MODIFIED Requirements

### REQ-01: Canonical Ordered Execution In One Call

| Field | Value |
|-------|-------|
| **ID** | R1 |
| **RFC** | MUST |

(Previously: 8-stage chain `stats → features → ml → dl → bt → rank → select → gen`)

A single orchestrator entry point SHALL execute the canonical chain `stats → features → gen` in that ORDER. Stages `ml`, `dl`, `bt`, `rank`, and `select` are removed from the numbers path; backtesting retains its own independent pipeline. The `features` stage SHALL produce the active probability snapshot consumed by `gen`. Any stage failure SHALL raise `PIPE_STAGE_FAILED` (carrying the failed stage id); remaining stages SHALL NOT run, completed stages' artifacts SHALL persist intact, and NO generator output SHALL be produced for that run.

#### Scenario: cold chain succeeds

- GIVEN imported draws and no chain artifacts
- WHEN the orchestrator runs once
- THEN all three stages (`stats`, `features`, `gen`) complete in canonical order and final combinations are returned

#### Scenario: gen succeeds without active MetaSelection

- GIVEN `features` produced a valid probability snapshot but no active `MetaSelection` exists
- WHEN the orchestrator reaches `gen`
- THEN `gen` succeeds using a deterministic seed derived from the probability snapshot fingerprint and lottery_id
- AND no `GEN_NO_SELECTION` error is raised
- AND the run report shows `gen` with status `completed`

#### Scenario: stage failure aborts cleanly

- GIVEN `features` will raise
- WHEN the chain reaches `features`
- THEN `PIPE_STAGE_FAILED` names `features`, `gen` never runs, and `stats` artifacts persist

### REQ-02: Detect Missing Prerequisites And Repair

| Field | Value |
|-------|-------|
| **ID** | R2 |
| **RFC** | MUST |

(Previously: prerequisite detection considered all 8 stages; stale/missing detection covered `ml/dl/bt/rank/select`)

Before executing each stage, the orchestrator SHALL inspect its prerequisites (active snapshots, input fingerprints): missing or stale items are repaired by running exactly the deficient stages; current-and-valid stages are skipped. Stages `ml`, `dl`, `bt`, `rank`, and `select` are no longer part of the numbers orchestrator and SHALL NOT be inspected or healed. New draw coverage that invalidates `stats` or `features` fingerprints SHALL invalidate `gen` as the downstream consumer.

#### Scenario: partial chain heals forward

- GIVEN a `stats` snapshot exists but `features` is missing
- WHEN the orchestrator runs
- THEN `stats` reports `skipped` and `features` + `gen` run to completion

#### Scenario: fresh draw invalidates downstream only

- GIVEN a completed chain and one newly imported draw
- WHEN the orchestrator runs again
- THEN `stats` re-runs (draw coverage changed), `features` re-runs (stats fingerprint changed), and `gen` re-runs

### REQ-03: Per-Stage Status Report

| Field | Value |
|-------|-------|
| **ID** | R3 |
| **RFC** | MUST |

(Previously: report returned eight stage entries in canonical order)

Every orchestrator response SHALL include an ordered per-stage report with exactly three entries: `stats`, `features`, `gen`. Each entry SHALL carry a canonical stage id, status ∈ {`skipped`, `completed`, `failed`}, and artifact references (snapshot id / fingerprint) where produced; a `failed` entry carries its error code. No `ml`, `dl`, `bt`, `rank`, or `select` entries SHALL appear.

#### Scenario: report matches canonical shape

- GIVEN any finished run
- WHEN the response is inspected
- THEN exactly three stage entries appear (`stats`, `features`, `gen`) with allowed statuses and references
