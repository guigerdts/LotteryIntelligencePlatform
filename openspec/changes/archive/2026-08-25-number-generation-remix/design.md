# Design: Remix Number Generation on Statistical Levers

## Technical Approach

Keep the F5 probability map (`probability_service`) as the base distribution.
Replace the dead meta-selection score with a **transparent statistical weight
composer** that combines F5 × EV (A) × bias-neutral (C) × optional coverage (D),
and applies unpopularity (B) only when sales data exists. Add EV and bias
detection as pure, testable computations over existing `Draw` history. Retire the
prediction engines from the generation path after confirming no other consumer.

## Architecture Decisions

| Decision | Choice | Tradeoff | Rationale |
|----------|--------|----------|-----------|
| Weight source | New `statistical_weight` composer, not meta | Slight rewrite of `gen_service` | Meta score cancels in sampling (sampling.py:88); it added nothing |
| EV computation | New `EVService` reading `Draw.jackpot`/`winners` | Needs NULL handling | Only lever A data we already have (768 draws) |
| Bias detection | Add pure fns to `statistics/engine` (STE-14) | Adds χ²/runs code | Confirms fairness; never alters frequencies |
| Engine retirement | Grep consumers first; delete only orphans | Risk if backtest/experiment UIs use them | User chose "eliminar y retirar" but safely |
| Sales data (B) | Investigation task; neutral fallback | May be unobtainable | User: include "if viable/practical" |

## Data Flow

    Draw history (DB)
       │
       ├─→ StatisticsService ──→ bias report (χ² / runs / entropy)   [C]
       ├─→ EVService ──────────→ favorable_now flag + EV              [A]
       └─→ ProbabilityService ─→ F5 map + optional coverage map       [D / B?]
                                                                      │
                                            StatisticalWeightComposer │
                                                      F5 × levers     │
                                                              ↓
                                                   GenService.generate
                                                              ↓
                                                  sampled combinations
                                                              ↓
                                         Mis Números UI (disclaimer + EV flag)

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `app/generators/weighting.py` | Create | `compose_weights(f5, ev, bias, coverage)` → `dict[int,float]` |
| `app/services/gen_service.py` | Modify | Drop `entry.score`; call composer; bump `GENERATOR_VERSION` |
| `app/generators/sampling.py` | Modify | `WeightedPool` takes composed weights (no meta multiplier) |
| `app/services/ev_service.py` | Create | EV from `Draw.jackpot`/`winners`; NULL-safe |
| `app/statistics/engine.py` | Modify | `chi_square`, `runs_test` pure functions |
| `app/services/statistics_service.py` | Modify | Expose bias report (STE-14) |
| `app/services/probability_service.py` | Modify | Optional coverage/unpopularity map (PM-08) |
| `app/services/gen_service.py` (meta wiring) | Modify | Remove meta-selection dependency from generation; KEEP ml/dl/bt/opt/feature engines (they power backtesting/experiment UIs) |
| `frontend/.../MisNumeros.tsx` | Modify | Strengthen disclaimer (REQ-06) + show EV flag |

## Interfaces / Contracts

```python
@dataclass
class StatisticalLeverWeights:
    f5: dict[int, float]
    ev_factor: float = 1.0           # A
    coverage_factor: dict[int, float] = field(default_factory=dict)  # D
    unpopularity_factor: dict[int, float] = field(default_factory=dict)  # B (neutral if no data)

@dataclass
class EVResult:
    ev: float
    favorable_now: bool
    source_draws: int

@dataclass
class BiasReport:
    status: Literal["fair", "anomalous"]
    chi_square: float
    p_value: float
    runs_z: float
    outliers: list[int]
```

## Testing Strategy

| Layer | What | Approach |
|-------|------|----------|
| Unit | composer neutral without sales | weights == F5 when no lever data |
| Unit | EV split + NULL | fixtures with winners=0/5, NULL jackpot |
| Unit | bias fair vs anomalous | synthetic 768-draw fixtures |
| Unit | gen independence from meta | removing meta selection yields identical output |
| Integration | full generate via API | 5 combos + disclaimer + EV flag in payload |
| RED | meta-decoupling | test that `gen_service` no longer imports meta selection |

## Threat Matrix

N/A — no routing, shell, subprocess, VCS/PR automation, executable-file
classification, or process-integration boundary is changed.

## Migration / Rollout

- Bump `GENERATOR_VERSION` so new snapshots never alias legacy fingerprints
  (generator-output REQ-02); legacy rows stay readable.
- No DB migration required for A/C/D. Sales import (B) would add a `sales`
  table only if the investigation finds a viable source.
- Engines deleted only after `grep -r` confirms zero consumers outside gen.

## Open Questions

- [ ] Is a practical Baloto sales/popularity data source obtainable? (gates lever B)
- [ ] Do backtesting/experiment UIs consume the meta/ml/dl engines? (gates deletion)
