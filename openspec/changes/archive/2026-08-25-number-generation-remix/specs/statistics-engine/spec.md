# Delta for Statistics Engine

## ADDED Requirements

### STE-14: Bias / Fairness Detection

The engine SHALL compute, over the active draw history, a chi-square
goodness-of-fit test of observed vs uniform number frequencies, a runs test for
sequential independence, and report the existing entropy scalar. Results SHALL be
exposed as a bias report (fair / anomalous) with statistics; they SHALL NOT be
used to alter stored frequencies.

#### Scenario: fair game reports fair

- GIVEN 768 draws with frequencies consistent with uniform
- WHEN STE-14 runs
- THEN the bias report flags "fair" with the χ² statistic and p-value

#### Scenario: anomalous frequency flagged

- GIVEN a number with observed frequency far beyond uniform expectation
- WHEN STE-14 runs
- THEN the bias report flags "anomalous" and lists the outlier
