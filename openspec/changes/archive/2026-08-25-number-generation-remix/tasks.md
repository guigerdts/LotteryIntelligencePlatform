# Tasks: Remix Number Generation on Statistical Levers

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | 600–900 (new modules + deletions + UI + tests) |
| 400-line budget risk | High |
| Chained PRs recommended | Yes |
| Suggested split | PR1 investigation → PR2 bias → PR3 EV → PR4 coverage → PR5 generator → PR6 retire → PR7 UI |
| Delivery strategy | ask-on-risk |
| Chain strategy | pending |

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|-----------|----------------------|-----------------|-------------------|
| 1 | Investigate sales source + engine consumers | PR1 | `backend/.venv/bin/pytest tests/ -q` | N/A (research only) | no code shipped |
| 2 | χ²/runs bias detection | PR2 | `backend/.venv/bin/pytest tests/statistics/ -q` | generate stats snapshot via API | revert statistics_service.py |
| 3 | EV service | PR3 | `backend/.venv/bin/pytest tests/ev/ -q` | call EV endpoint on DB | revert ev_service.py |
| 4 | Coverage/unpopularity map | PR4 | `backend/.venv/bin/pytest tests/probability/ -q` | probability generate | revert probability_service.py |
| 5 | Generator remix | PR5 | `backend/.venv/bin/pytest tests/gen/ -q` | POST /gen/generate → 5 combos | revert gen_service/sampling + VERSION |
| 6 | Decouple gen from meta | PR6 | `backend/.venv/bin/pytest tests/gen/ tests/pipeline/ -q` | POST /gen/generate | revert gen_service/sampling |
| 7 | UI disclaimer + EV flag | PR7 | `cd frontend && vitest run` | Mis Números page render | revert component |

## Phase 1: Investigation

- [ ] 1.1 Grep all consumers of `meta/`, `feature_engineering/`, `ml/`, `dl/`, `optimization/` outside generation (backtesting/experiment UIs) — record findings.
- [ ] 1.2 Research viable Baloto sales/popularity data source; document obtainability (gates lever B).

## Phase 2: Statistics — Bias Detection (STE-14)

- [ ] 2.1 RED: add failing tests for `chi_square` and `runs_test` in `tests/statistics/`.
- [ ] 2.2 GREEN: implement `chi_square`, `runs_test` in `app/statistics/engine.py`; expose bias report via `StatisticsService` (NULL-safe over 768 draws).

## Phase 3: EV Service (EV-01..03)

- [ ] 3.1 RED: tests for EV split (`winners>0`), NULL jackpot, `favorable_now`.
- [ ] 3.2 GREEN: create `app/services/ev_service.py` reading `Draw.jackpot`/`winners`; parimutuel split; NULL-safe; return `EVResult`.

## Phase 4: Probability Coverage Map (PM-08)

- [ ] 4.1 RED: test neutral map without sales; coverage nudges under-represented.
- [ ] 4.2 GREEN: add optional `coverage/unpopularity` weight map to `probability_service`; neutral when no sales data.

## Phase 5: Generator Remix (REQ-03, REQ-04)

- [ ] 5.1 RED: test that `gen_service` no longer reads `meta_selections`; output identical to F5+levers.
- [ ] 5.2 Create `app/generators/weighting.py`: `compose_weights(f5, ev, bias, coverage)` → `dict[int,float]`.
- [ ] 5.3 Modify `gen_service.py` + `sampling.py` (`WeightedPool` takes composed weights; drop `entry.score`); bump `GENERATOR_VERSION`.
- [ ] 5.4 GREEN: pass 5.1 RED test; verify 5 combos via API carry non-null score.

## Phase 6: Decouple Generation from Meta (keep engines)

- [ ] 6.1 Remove generation's dependency on `meta_selections`/`meta_selection_entries`: `gen_service` composes weights from F5 + statistical levers, not from a meta selection. (Engines ml/dl/bt/opt/feature are KEPT — they power backtesting/experiment UIs.)
- [ ] 6.2 Make the numbers-orchestrator pipeline skip the `rank` stage for generation (or build a trivial selection) so no meta call is required to produce numbers.
- [ ] 6.3 Keep meta-learning/backtesting/experiment modules and their tests intact; only generation wiring changes.

## Phase 7: UI (REQ-06)

- [ ] 7.1 Strengthen Mis Números disclaimer text ("no method raises win probability").
- [ ] 7.2 Show `favorable_now` / EV flag from generation payload.

## Phase 8: Verify

- [ ] 8.1 `backend/.venv/bin/pytest` green; `ruff check .` clean.
- [ ] 8.2 `cd frontend && vitest run` green.
- [ ] 8.3 Manual: generate 5 combos, confirm disclaimer + EV flag, scores populated.
