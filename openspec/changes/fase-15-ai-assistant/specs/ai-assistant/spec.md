# Spec — AI Assistant (`ai-assistant`)

**Change**: `fase-15-ai-assistant` · **Store**: `openspec` · **Date**: 2026-08-16
**Artifact**: spec (this change) — NEW capability `ai-assistant`: deterministic rule-based text generation over persisted snapshots for the five roadmap functions (explain/interpret/report/summarize/assist). No LLM, no new runtime dependencies.

## Purpose

Deterministic, rule-based text generation consuming existing persisted snapshots through the service layer — no LLM SDKs, no new runtime dependencies (F6 gate stays green, no `pyproject.toml` change). A `TextGenerator` seam (Provider Protocol) isolates generation so a future LLM provider can plug in at the composition root without touching the domain contract or the five functions. All output is envelope-wrapped, stateless (D5), synchronous, manual-only (BTE-12), and byte-identical per engine version.

**Output language**: generated text SHALL be **Spanish (es)** — matching the roadmap function names ("Explicar resultados", "Interpretar gráficos") and the product's Spanish UI labels. Spec/code artifacts remain English per the SDD contract.

Requirements A-01..A-12. D7 (scalars read) included as A-11.

## Requirements Overview

| ID | Requirement | RFC |
|----|-------------|-----|
| A-01 | Deterministic rule-based engine + `TextGenerator` seam | MUST |
| A-02 | Versioned algorithm identity + fingerprint | MUST |
| A-03 | Decimal-safe text formatting (no float artifacts) | MUST |
| A-04 | Byte-identical determinism + golden-test testability | MUST |
| A-05 | Latency: in-process, no network I/O | SHOULD |
| A-06 | explain — `GET /assistant/explain` | MUST |
| A-07 | interpret — `GET /assistant/interpret` | MUST |
| A-08 | report — `GET /assistant/report` | MUST |
| A-09 | summarize — `POST /assistant/summarize` | MUST |
| A-10 | assist — `POST /assistant/assist`, intent routing | MUST |
| A-11 | Scalars read — `GET /statistics/{code}/scalars` (D7) | MUST |
| A-12 | Envelope + error handling | MUST |

## Requirements

### A-01: Deterministic Rule-Based Engine + TextGenerator Seam

The engine SHALL generate text via deterministic rule-based generators (stdlib + string templates) over persisted snapshot data. It MUST NOT call any LLM SDK, external provider, or new runtime dependency. Prompts/templates SHALL live as code constants in the engine package (D1). Generation SHALL be isolated behind a `TextGenerator` seam so a future LLM provider can be registered without modifying the five functions' contracts.

#### Scenario: rule-based output without new deps

- GIVEN persisted statistics for a lottery
- WHEN explain is invoked
- THEN Spanish text is produced by deterministic templates using stdlib only
- AND the dependency ban-gate tests stay green

#### Scenario: LLM provider can plug in later

- GIVEN the `TextGenerator` seam
- WHEN a new provider is registered at the composition root
- THEN the five functions' contracts and the domain are unchanged

### A-02: Versioned Algorithm Identity + Fingerprint

The engine SHALL expose `AI_GENERATOR_VERSION` (pinned in `ai/version.py`, independent of other engines) and a canonical fingerprint — SHA-256 over `sort_keys=True` JSON of `{engine_version, function, inputs}`. Output SHALL change only when the version or inputs change.

#### Scenario: version participates in fingerprint

- GIVEN two invocations differing only in `AI_GENERATOR_VERSION`
- WHEN fingerprints are computed
- THEN they differ

#### Scenario: stable fingerprint

- GIVEN the same version and inputs
- WHEN the fingerprint is computed twice
- THEN the hex digest is identical

### A-03: Decimal-Safe Text Formatting

The engine MUST format numeric values as exact `Decimal` strings — never via `float()` — so generated text has no floating-point artifacts. Persisted `Numeric` values (e.g. `avg_gap`, entropy, probability `value`) SHALL be formatted from their Decimal representation at fixed documented precision.

#### Scenario: no float artifacts

- GIVEN a persisted average of `0.12345678` (Decimal)
- WHEN a report renders it
- THEN the text contains exactly `0.12345678` with no float-rounding residue

#### Scenario: NULL-aware values

- GIVEN a NULL average/jackpot value
- WHEN text generation formats it
- THEN a documented "no data" placeholder renders, never an error

### A-04: Determinism + Testability

Same engine version + same inputs SHALL produce byte-identical output text, locked by golden tests per function.

#### Scenario: byte-identical repetition

- GIVEN identical inputs and engine version
- WHEN the same function runs twice
- THEN both outputs are byte-identical

#### Scenario: golden test lock

- GIVEN a committed golden fixture
- WHEN the generator runs against it
- THEN output matches the fixture exactly

### A-05: Latency (SHOULD)

Generation SHALL be synchronous and in-process with no network I/O; a single call SHOULD complete well under 1s for a bounded snapshot.

#### Scenario: fast synchronous call

- GIVEN an active snapshot
- WHEN any generator is invoked
- THEN the response returns synchronously with no external calls

### A-06: explain

`GET /assistant/explain?lottery_code={code}&subject={subject?}&context={context?}` SHALL return Spanish natural-language explanation of the lottery's results from the active statistics snapshot: frequencies, gaps, averages, and entropy (via scalars, A-11). Unknown lottery → `RESOURCE_NOT_FOUND` (404). Missing snapshot or missing scalars → empty-data Spanish text in a success envelope (no failure).

#### Scenario: explanation with entropy

- GIVEN an active statistics snapshot including an entropy scalar
- WHEN explain is called for the lottery
- THEN Spanish text cites frequency/gap/average highlights and entropy

#### Scenario: missing scalars

- GIVEN a snapshot with no entropy scalar
- WHEN explain is called
- THEN the text explains without entropy and does not fail

### A-07: interpret

`GET /assistant/interpret?lottery_code={code}` SHALL interpret the data behind the client-side charts (D6: frequencies/gaps/averages/probability rows — not images) as Spanish text. Unknown lottery → `RESOURCE_NOT_FOUND` (404); empty data → empty-data Spanish text (success).

#### Scenario: interprets chart data

- GIVEN frequency/gap/average/probability rows for a lottery
- WHEN interpret is called
- THEN Spanish text interprets the chart data (no image input)

### A-08: report

`GET /assistant/report?lottery_code={code}&scope={scope?}` SHALL return a structured markdown-ish plain-text report. `scope` ∈ {frequency, gap, average, probability, experiment}; default covers all available scopes. Unsupported scope → 422 validation error.

#### Scenario: scoped report

- GIVEN an active snapshot
- WHEN report with `scope=frequency` is called
- THEN a structured plain-text report of frequencies renders

#### Scenario: invalid scope rejected

- GIVEN a report request
- WHEN `scope` is unsupported
- THEN 422 validation error lists the allowed values

### A-09: summarize

`POST /assistant/summarize` with body `{experiment_id, run_ids?}` SHALL return Spanish text summarizing the experiment comparison (`exp.compare()` data), mirroring the `POST /experiment/{id}/compare` body contract. Unknown experiment → `RESOURCE_NOT_FOUND` (404).

#### Scenario: experiment summary

- GIVEN a completed comparison with metric rows
- WHEN summarize is called
- THEN Spanish text highlights the best run per metric and the deltas

### A-10: assist

`POST /assistant/assist` with body `{question, lottery_code}` SHALL classify the free-text question by deterministic keyword-based intent over the taxonomy {explain, interpret, report, summarize} and delegate to the matching generator. Unknown intent SHALL return a helpful Spanish response listing the four capabilities (success envelope, not an error). Classification SHALL be pure rule-based (no ML).

#### Scenario: intent routed

- GIVEN a question mentioning "por qué" and "frecuencia"
- WHEN assist is called
- THEN intent=explain is selected and explain's output returns

#### Scenario: unknown intent fallback

- GIVEN an off-topic question
- WHEN assist is called
- THEN a capabilities-listing response returns in a success envelope

### A-11: Scalars Read (D7)

`GET /statistics/{code}/scalars` SHALL expose persisted `stat_scalars` (e.g. entropy) from the active snapshot as `{name, value}` rows with Decimal-string values, enabling explain (A-06). Read-only, never precomputes (STE-10); missing snapshot → `SNAPSHOT_NOT_FOUND` (404); unknown lottery → `RESOURCE_NOT_FOUND` (404). (Modifies `api/v1/statistics.py` per proposal D7.)

#### Scenario: entropy exposed

- GIVEN an active snapshot with an entropy scalar
- WHEN scalars is called
- THEN the response contains `{name: "entropy", value: <Decimal string>}`

#### Scenario: read never precomputes

- GIVEN a lottery with no active snapshot
- WHEN scalars is called
- THEN 404 `SNAPSHOT_NOT_FOUND` and no generation is triggered

### A-12: Envelope + Error Handling

Every assistant endpoint SHALL return the standard envelope: success `{success, data, timestamp}`; failure `{success, error: {code, message}, timestamp}`. Error mapping: unknown lottery → `RESOURCE_NOT_FOUND` (404); invalid body/scope → 422; generation failure → `assistant_error` (500). Missing/empty data for an existing lottery SHALL produce an empty-data Spanish text response in a success envelope — NOT an error.

#### Scenario: envelope success

- GIVEN a valid request
- WHEN any assistant endpoint responds
- THEN the body is `{success: true, data: {text, engine_version, fingerprint}, timestamp}`

#### Scenario: empty-data text, not failure

- GIVEN a lottery with a snapshot but no frequency rows
- WHEN explain is called
- THEN a success envelope with empty-data Spanish text returns, no error