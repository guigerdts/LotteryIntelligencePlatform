# Delta for Probability Engine

## ADDED Requirements

### PM-08: Coverage / Unpopularity Weight Map (Optional)

The engine MAY produce an optional weight map `w[n]` for generation use, encoding
coverage (favor under-represented numbers within a budget) and, ONLY when
sales/popularity data is available, unpopularity (avoid birthday/sequential
numbers to reduce split risk). When no sales data exists, the map SHALL be neutral
(`w[n] = 1`). This map influences sampling weights only; it SHALL NOT change
computed event probabilities.

#### Scenario: neutral without sales data

- GIVEN no sales/popularity import
- WHEN PM-08 runs
- THEN `w[n] = 1` for all n

#### Scenario: coverage nudges under-represented

- GIVEN coverage mode enabled
- WHEN PM-08 runs
- THEN under-represented numbers receive weight > 1 within configured bounds
