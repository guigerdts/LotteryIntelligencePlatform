# Proposal: Winning Numbers Pipeline (Baloto/Revancha)

## Intent

Owner need: "combinaciones ganadoras posibles" — playable tickets, end to end. Today the generator emits incomplete bets: `GenService.generate()` persists `"super_number": None, "score": None` (`gen_service.py:167`) and `sample_combinations()` never samples the Superbalota (`sampling.py:77` passes `None`). Official rules demand 5 distinct numbers 1–43 + SB 1–16; SB alone already pays (0+SB refund tier). Reaching output also requires manual CLI chaining with brittle couplings (rank→backtesting context hash; `meta_service.py:242` hardcoded). **Honest framing**: statistically informed candidates over historical draws; draws stay random; no prediction improvement is promised.

## Scope

### In Scope

**S1 — Legal generator output (backend)**: sample SB per combo from the history SB-marginal distribution (same isolated RNG stream; seeded/reproducible); real per-combination selection-weighted score replacing `null`; legality validation (5 distinct 1–43, SB 1–16) enforced pre-persist with explicit `GEN_*` error codes.

**S2 — Chain orchestrator (backend)**: POST endpoint that runs/repairs stats→features→ml/dl→bt→rank→select→gen; per-stage progress; fingerprint-idempotent; skips completed stages (heals missing).

**S3 — "Mis Números" (frontend)**: replace raw Generator form; one CTA; stage progress; combos presented as "un boleto, dos sorteos (Baloto+Revancha)"; prize-tier reference table; honest randomness disclaimer.

### Out of Scope

- No draw data-model changes (DB verified correct: numbers 1–43, `super_number.value` 1–16).
- No prediction-improvement claims or model tuning.
- No purchase/payment integration.
- No data-layer unification of Baloto(id 1)/Revancha(id 3) — presentation-only now; deferred.

## Capabilities

### New Capabilities
- `generator-output`: complete legal tickets (numbers+SB+score), deterministic, validated.
- `pipeline-orchestrator`: heal-and-run chain API, stage reporting, fingerprint idempotency.
- `my-numbers-page`: owner-facing results page (one CTA, both draws, tiers, disclaimer).

### Modified Capabilities
None — `openspec/specs/` has no generator capability today (GEN-* lives in code/tests only).

## Approach

- **S1**: extend `sampling.py::sample_combinations` to draw SB from an SB-marginal map on the same rng, return `(combo, sb)`, compute selection-weighted score; `gen_service.generate()` persists both (replacing L167 nulls); enforce `validation.py::validate_combination(combo, sb, cfg)` (already accepts `sb`); bump `GENERATOR_VERSION`; add codes to `services/errors.py`.
- **S2**: recommend **sync-with-stages** over job+polling: repo has no worker/job infra and local runtimes are minutes-scale; single POST returns per-stage results; each stage checks fingerprints/tables first (heal). Job+polling deferred until runtime evidence demands it.
- **S3**: new page + client/type extensions, MSW tests following Models.tsx patterns; route in `App.tsx`.

## Affected Areas

| Area | Impact |
|------|--------|
| `backend/src/backend/app/generators/sampling.py` | Modified — SB sampling, `(combo, sb)` return |
| `backend/src/backend/app/generators/validation.py` | Modified — enforce SB legality |
| `backend/src/backend/app/services/gen_service.py` | Modified — persist SB+score (L167), SB-marginal read |
| `backend/src/backend/app/services/errors.py` | Modified — new `GEN_*` codes |
| `backend/src/backend/app/api/v1/gen.py` | Modified — expose SB/score |
| `backend/src/backend/app/services/pipeline_service.py`, `api/v1/pipeline.py` | New — S2 orchestrator |
| `backend/tests/gen/*`, `backend/tests/pipeline/*` | Mod/New — determinism, legality, heal |
| `frontend/src/pages/MyNumbers.tsx` (from `Generator.tsx`) | New — S3 page |
| `frontend/src/services/gen.ts`, `types/gen.ts`, `App.tsx` | Modified — client, types, route |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| SB in RNG stream breaks seed reproducibility | Med | bump `GENERATOR_VERSION`; golden determinism tests |
| Sparse history → weak SB marginals | Low | uniform 1–16 fallback; explicit error if no draws |
| rank→bt context-hash coupling blocks orchestration | High | verify/repair in S2; escalate to design if structural |
| Cold-chain sync POST exceeds HTTP timeout | Med | staged progress; job infra deferred |

## Rollback Plan

Per slice, independent: revert that slice's PR. `super_number` stays nullable — legacy snapshot rows remain readable; orchestrator endpoint is additive; frontend route swap reverts by restoring Generator. No migrations.

## Dependencies

- Active selection + probability snapshot per lottery (S2 heals these first).
- Imported draw history for SB marginals.

## Delivery Forecast (400-line budget)

- S1 ≈350–450 LOC (code+tests): budget risk Medium → standalone chained PR.
- S2 ≈250–350 LOC: Low/Medium → standalone chained PR.
- S3 ≈300–400 LOC: Medium → standalone chained PR.

Decision needed before apply: Yes · Chained PRs recommended: Yes · 400-line budget risk: Medium

## Success Criteria

- [ ] Generated combos always carry valid SB 1–16; zero `super_number IS NULL` rows post-change.
- [ ] Same seed reproduces identical combos including SB.
- [ ] Illegal combinations rejected pre-persist with clear error codes.
- [ ] Orchestrator heals missing dependencies: empty chain → one POST yields final combinations with per-stage statuses.
- [ ] UI shows both draws per ticket, prize-tier table, and randomness disclaimer.
