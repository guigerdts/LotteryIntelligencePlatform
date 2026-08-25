# Delta for Generator Output

## MODIFIED Requirements

### REQ-03: Non-Null Statistical-Weighted Score

(Previously: score came from entry-selection weight + probability distribution)

Every persisted combination SHALL carry a non-null, finite score derived from the
F5 probability distribution weighted by TRANSPARENT STATISTICAL LEVERS (EV
adjustment, bias-neutral, optional coverage/unpopularity), NOT from any
meta/ML/DL/backtest selection score. The generator SHALL NOT read
`meta_selections` / `meta_selection_entries` for weighting. Generator responses
SHALL expose `super_number` and `score`.

#### Scenario: scores always populated and exposed

- GIVEN any successful seeded generation
- WHEN persisted rows and the API payload are inspected
- THEN every row has a non-null finite `score` and responses echo `super_number` and `score`

#### Scenario: generation independent of meta scores

- GIVEN the meta prediction chain is removed/retired
- WHEN generation runs
- THEN output numbers follow F5 + statistical-lever weighting, with no meta input

## ADDED Requirements

### REQ-04: Statistical Lever Weighting

The generator SHALL compose sampling weights as `F5[n] × statistical_lever_weight[n]`
where `statistical_lever_weight` MAY incorporate EV timing (A), bias-neutralization
(C), and optional coverage/wheeling (D). Unpopularity weighting (B) SHALL be
applied ONLY when sales/popularity data is available; otherwise weights SHALL be
neutral. No lever SHALL claim or produce higher win probability.

#### Scenario: lever B absent without sales data

- GIVEN no sales/popularity data imported
- WHEN weights are composed
- THEN unpopularity weight = 1.0 (neutral) for all numbers

#### Scenario: levers do not change odds

- GIVEN any statistical lever configuration
- WHEN generation runs
- THEN each combination's win probability equals the fair combinatorial probability
