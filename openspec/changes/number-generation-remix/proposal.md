# Proposal: Remix Number Generation on Statistical Levers

## Intent

The prediction chain `features → ml → dl → bt → rank → select → opt` has **zero
effect** on generated numbers: in `generators/sampling.py:88` weights are
`F5[n] × entry.score`, but `score` is a constant per pool so it cancels in
`rng.choices`, and the F5 map (`probability_service`) is meta-independent. We
rebuild the 5-number generation on transparent, legitimate statistical levers
(EV / bias / coverage) and retire the dead engines. Honesty constraint: no
method raises win probability.

## Scope

### In Scope
- Decouple generator from the meta prediction chain; weight by F5 × transparent statistical weights.
- **A. EV gate** from `Draw.jackpot` / `Draw.winners` (768 draws available).
- **C. Bias detection**: χ² goodness-of-fit + runs test + entropy over 768 draws.
- **D. Coverage / wheeling** (optional, within user budget).
- Honesty disclaimer in the *Mis Números* UI.
- Retire prediction engines if no other consumer (verified first).
- **Investigate** Baloto sales/popularity source; **if practical**, add import + unpopularity lever (**B**).

### Out of Scope
- 4-digit game (deferred per user).
- Unpopularity lever (**B**) if no sales source is found.
- Altering lottery fairness or odds (mathematically impossible).

## Capabilities

### New Capabilities
- `ev-assessment`: EV computation + "favorable-now?" flag from jackpot/winners.

### Modified Capabilities
- `generator-output`: repurpose weighting, drop meta score.
- `mis-numeros-page`: add honesty disclaimer.
- `statistics-engine`: add χ² / runs test.
- `probability-engine`: coverage / unpopularity weight framing.
- `meta-learning`: decouple from gen; retire if orphaned.

## Approach

Keep F5 as the base distribution. `gen_service` composes weights from
F5 × transparent lever weights (EV-adjusted, bias-neutral, coverage). Remove
`entry.score` from `WeightedPool`. `statistics_service` adds χ²/runs. Retire
`feature-engine`/`dl-engine`/`opt-engine`/meta-from-gen only after confirming no
other consumer (backtesting/experiment UIs). Bias result drives a neutral-or-flag
output, never a "prediction".

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `generators/sampling.py` | Modified | drop `entry.score` multiplier |
| `services/gen_service.py` | Modified | statistical weights, no meta |
| `services/statistics_service.py` | Modified | χ² / runs test |
| `services/probability_service.py` | Modified | coverage weights |
| `meta/`, `feature_engineering/`, `ml/`, `dl/`, `optimization/` | Removed (if orphan) | retire dead engines |
| `mis-numeros-page` (frontend) | Modified | disclaimer |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Removing engines breaks other UIs | Med | grep consumers before delete |
| No sales source for lever B | Med | mark B out-of-scope, keep A/C/D |
| UI implies higher odds | Low | enforced disclaimer wording |

## Rollback Plan

Engines kept behind imports until verified orphaned; git revert of any removed
module. Generator weighting is a single composable function — revertable.

## Dependencies

- Baloto sales/popularity data source (conditional for lever B).

## Success Criteria

- [ ] Gen output independent of meta scores (tests prove).
- [ ] χ² / runs present over 768 draws; report neutral-or-flag.
- [ ] EV "favorable-now?" flag from jackpot/winners.
- [ ] Honesty disclaimer visible in Mis Números UI.
- [ ] pytest + ruff green; dead engines retired only if orphaned.
