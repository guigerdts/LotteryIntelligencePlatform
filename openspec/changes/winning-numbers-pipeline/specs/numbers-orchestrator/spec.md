# Delta — Numbers Orchestrator (`numbers-orchestrator`)

**Change**: `winning-numbers-pipeline` · **Store**: `openspec` · **Date**: 2026-08-23
**Artifact**: delta spec — NEW capability (proposal S2). The proposal Capabilities list names this domain `pipeline-orchestrator`; the owner-instructed name `numbers-orchestrator` governs this spec set. No main spec exists, so ADDED requirements become the full capability spec at archive.
**Binding owner decisions**: orchestrator MAY auto-train ml/dl when missing (minutes-scale latency acceptable); delivery is sync-with-stages — one call returns the full per-stage report; no job/polling infra in this change.
**Seam**: rank depends on a hardcoded backtesting context hash (`meta_service.py:242`) — brittle coupling that blocks chaining; the orchestrator owns correct context derivation.
**Verify**: pytest against the service layer (`backend/tests/pipeline/`).

## ADDED Requirements

### Requirement: R1: R-full-chain — Canonical Ordered Execution In One Call

| Field | Value |
|-------|-------|
| **ID** | R1 |
| **RFC** | MUST |

A single orchestrator entry point SHALL execute the canonical chain `stats → features → ml → dl → bt → rank → select → gen` in that ORDER, enforcing `bt` strictly BEFORE `rank` (rank consumes backtest context). When ml/dl models are missing, the orchestrator SHALL train them automatically. Rank's backtesting context SHALL be derived from the identity of the backtest actually executed in this run (fingerprint/checksum) — never a hardcoded value, retiring the `meta_service.py:242` coupling. Any stage failure SHALL raise `PIPE_STAGE_FAILED` (carrying the failed stage id), defined in `services/errors.py`; remaining stages SHALL NOT run, completed stages' artifacts SHALL persist intact, and NO generator output SHALL be produced for that run.

#### Scenario: cold chain succeeds

- GIVEN imported draws and no chain artifacts
- WHEN the orchestrator runs once
- THEN all eight stages complete in canonical order and final combinations are returned

#### Scenario: bt-before-rank enforced with real context

- GIVEN instrumented stages
- WHEN the chain executes
- THEN `bt` finishes before `rank` starts and `rank` receives that bt run's fingerprint-derived context (no hardcoded hash)

#### Scenario: stage failure aborts cleanly

- GIVEN `rank` will raise
- WHEN the chain reaches `rank`
- THEN `PIPE_STAGE_FAILED` names `rank`, `gen` never runs, and earlier artifacts persist

### Requirement: R2: R-healing — Detect Missing Prerequisites And Repair

| Field | Value |
|-------|-------|
| **ID** | R2 |
| **RFC** | MUST |

Before executing each stage, the orchestrator SHALL inspect its prerequisites (active snapshots, model artifacts, input fingerprints): missing or stale items are repaired by running exactly the deficient stages; current-and-valid stages are skipped. New draw coverage that invalidates a stage's fingerprint SHALL invalidate every downstream stage that consumes it.

#### Scenario: partial chain heals forward

- GIVEN stats/features snapshots exist and everything downstream is missing
- WHEN the orchestrator runs
- THEN stats/features report skipped and the five remaining stages run to completion

#### Scenario: fresh draw invalidates downstream only

- GIVEN a completed chain and one newly imported draw
- WHEN the orchestrator runs again
- THEN stages whose fingerprints depend on draw coverage re-run and unaffected upstream stages skip

### Requirement: R3: R-stage-progress — Per-Stage Status Report

| Field | Value |
|-------|-------|
| **ID** | R3 |
| **RFC** | MUST |

Every orchestrator response SHALL include an ordered per-stage report: canonical stage id, status ∈ {`skipped`, `completed`, `failed`}, and artifact references (snapshot id / fingerprint) where produced; a `failed` entry carries its error code.

#### Scenario: report matches canonical shape

- GIVEN any finished run
- WHEN the response is inspected
- THEN eight stage entries appear in canonical order with allowed statuses and references

### Requirement: R4: R-idempotent — Fingerprint Reuse, Zero Side Effects

| Field | Value |
|-------|-------|
| **ID** | R4 |
| **RFC** | MUST |

Re-running with unchanged inputs SHALL reuse stored fingerprints end-to-end and return an identical result while performing zero side-effect writes: no store in the chain gains a new snapshot version.

#### Scenario: double run writes nothing

- GIVEN two consecutive runs with identical inputs
- WHEN both complete
- THEN payloads are identical and no stage store gained a new version
