# Archive Report — number-generation-remix

## Goal

Discard the dead meta prediction chain from number generation and rebuild the
5-combination "Mis Números" output on legitimate statistical levers (F5 frequency
× cold-coverage boost), with an honest UI that states odds are unchanged.

## Outcome

Implemented and merged via the stacked PRs **#71 / #72 / #73** into
`fix/rank-stale-healing`, then fast-forwarded into `main`.

## What shipped

| Area | Change |
|------|--------|
| statistics | `chi_square_gof`, `runs_test` (per-draw **sum** series), `bias_report` (STE-14) |
| EV (lever A) | `ev_service`: `combinations_count`, `combination_ev`, `estimate_ticket_ev`, `is_high_ev_window` (EV-15) |
| coverage (lever C/D) | `probability_service.coverage_map` + `cold_boost_weights` (PM-08) |
| generation | `generators/weighting.build_weights`; `sampling.WeightedPool` on precomputed weights; `gen_service` decoupled from `meta` `entry.score`; `GENERATOR_VERSION` 2.0.0 → 3.0.0 (GEN-009/14/15) |
| frontend | `MisNumeros`: honest disclaimer + Transparencia panel; `Score` → `Peso` (PM-09/EV-16) |

## Verification

- Backend suites green: `gen` 174, `statistics` 25, `probability` 92.
- Frontend `MisNumeros` 10/10, `tsc -b` clean, `eslint` clean.
- Full backend suite not run to completion in this environment (command timeout / OOM); not a code failure.

## Honesty

The UI states no method raises win probability. The combination `score` is a
transparent coverage weight (mean of F5 × cold-boost), not a win prediction.
Engines `ml`/`dl`/`bt`/`opt`/`feature` were retained (consumed by the
backtesting/experiment UIs); only `gen` was decoupled from the meta chain.

## Next

- Lever B (unpopularity / split-avoidance weights) requires importing
  sales/popularity data — out of scope until that exists.
