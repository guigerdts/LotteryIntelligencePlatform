# EV Assessment Specification

## Purpose

Compute expected value for a Baloto/Revancha play from official draw history and
surface a "favorable-now?" signal. This is an economic timing lever (A) only — it
does NOT change win probability.

## Requirements

### EV-01: Expected Value Computation

The system SHALL compute EV per play as
`EV = P_win × jackpot_share_estimate + Σ(tier_prize × P_tier) − ticket_cost`,
using `Draw.jackpot` and `Draw.winners` from stored history. When `winners > 0`,
the jackpot contribution SHALL account for the parimutuel split
(`jackpot / winners`). Ticket cost SHALL come from configured Baloto/Revancha prices.

#### Scenario: positive-EV rollover

- GIVEN a draw with jackpot COP 30bn and 0 winners, ticket COP 6000
- WHEN EV is computed
- THEN EV reflects the full jackpot over jackpot odds minus cost, and is positive

#### Scenario: split reduces EV

- GIVEN a draw with jackpot COP 10bn and 5 winners
- WHEN EV is computed
- THEN the jackpot contribution uses COP 2bn (10bn / 5)

### EV-02: Favorable-Now Flag

The system SHALL expose a boolean `favorable_now` (EV > ticket_cost) and the
computed EV value to the generation/UI layer. It SHALL NOT alter the sampled numbers.

#### Scenario: flag true when EV exceeds cost

- GIVEN EV > cost
- WHEN the flag is evaluated
- THEN `favorable_now` is true

#### Scenario: flag false on normal draw

- GIVEN a typical draw with EV < cost
- WHEN the flag is evaluated
- THEN `favorable_now` is false

### EV-03: Graceful Missing Data

The system SHALL handle missing `jackpot`/`winners` (NULL) by omitting that draw
from the EV estimate; if no usable draws exist, it SHALL return
`favorable_now = false` and a neutral EV, never a crash.

#### Scenario: NULL jackpot ignored

- GIVEN history with some NULL jackpot rows
- WHEN EV is computed
- THEN NULL rows are excluded and no value is imputed
