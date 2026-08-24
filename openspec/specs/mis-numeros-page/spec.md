# Spec — Mis Números Page (`mis-numeros-page`)

**Change**: `winning-numbers-pipeline` · **Store**: `openspec` · **Date**: 2026-08-23
**Artifact**: base spec — promoted from change `winning-numbers-pipeline` (archive).
**Binding product decisions**: Revancha is ALWAYS bundled — one ticket valid for BOTH draws (Baloto+Revancha), no toggle. Default combination count: 5.
**Prize-tier source**: Engram #1870 — eight official tiers.
**Verify**: vitest + MSW (Models/DL page patterns).

## Requirements

### REQ-01: Single End-To-End Action

| Field | Value |
|-------|-------|
| **ID** | R1 |
| **RFC** | MUST |

The page SHALL offer exactly ONE primary CTA that invokes the numbers-orchestrator end-to-end — no per-stage manual buttons. Because the sync call may run minutes-scale, the busy state SHALL hold for the whole request: CTA disabled with `aria-busy` and progress wording. A failed request SHALL render `ErrorState` whose retry re-issues the orchestrator call (DL page precedent).

#### Scenario: one CTA drives the whole chain

- GIVEN an MSW handler for the orchestrator POST
- WHEN the CTA is clicked
- THEN exactly one orchestrator request fires and no other stage endpoints are called

#### Scenario: busy held through slow call, retry on failure

- GIVEN the POST handler delays then returns 500
- WHEN the request resolves
- THEN during flight the CTA is disabled with `aria-busy`, and afterwards ErrorState offers Retry that re-posts

### REQ-02: Chain Progress Rendering

| Field | Value |
|-------|-------|
| **ID** | R2 |
| **RFC** | MUST |

The page SHALL render the response's per-stage report: all eight canonical stages in order with status labels; a `failed` stage SHALL show its error visibly. While the request is in flight the page SHALL show an indeterminate busy indicator — sync-with-stages delivers statuses only at completion.

#### Scenario: statuses render after the response

- GIVEN a 200 response carrying eight stage entries
- WHEN it lands
- THEN all eight render in canonical order with their statuses

#### Scenario: failed stage surfaces without crashing

- GIVEN a response whose `rank` stage failed
- WHEN it lands
- THEN `rank` shows its failed status and combinations are absent, and the page stays interactive

### REQ-03: Revancha Always Bundled

| Field | Value |
|-------|-------|
| **ID** | R3 |
| **RFC** | MUST |

Every presented ticket SHALL be labeled as valid for BOTH draws using the owner-approved phrase “un boleto, dos sorteos (Baloto+Revancha)”. The page SHALL NOT offer a Baloto/Revancha toggle or any separate Revancha generation control. This is presentation-only: data-layer unification of Baloto(id 1)/Revancha(id 3) remains out of scope.

#### Scenario: dual-draw presentation, no toggle

- GIVEN generated combinations render
- WHEN the ticket area is inspected
- THEN the both-draws phrase labels the tickets and no toggle control exists in the DOM

### REQ-04: Default Combination Count

| Field | Value |
|-------|-------|
| **ID** | R4 |
| **RFC** | MUST |

The page SHALL request five combinations by default; the user MAY adjust the count before running.

#### Scenario: default payload carries five

- GIVEN the user does not modify the count control
- WHEN the CTA fires
- THEN the orchestrator request body contains count 5

### REQ-05: Eight Official Tiers Table

| Field | Value |
|-------|-------|
| **ID** | R5 |
| **RFC** | MUST |

The page SHALL display a static prize-tier reference listing ALL EIGHT official tiers: 5+SB (jackpot), 5, 4+SB, 4, 3+SB, 3, 2+SB (paramutual), and 0+SB (bet refund) — presented as official-rules reference, never as outcome promises.

#### Scenario: tiers table complete

- WHEN the page renders
- THEN exactly the eight official tiers appear with their match descriptions

### REQ-06: Randomness Disclaimer

| Field | Value |
|-------|-------|
| **ID** | R6 |
| **RFC** | MUST |

A visible disclaimer SHALL state that candidates are statistically informed over historical draws, that draws remain random, and that no prediction improvement is promised. It SHALL remain visible on load and after generation.

#### Scenario: disclaimer persists across states

- GIVEN idle and post-generation states
- WHEN each renders
- THEN the disclaimer text remains visible
