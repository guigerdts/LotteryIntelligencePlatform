# Delta for Mis Números Page

## MODIFIED Requirements

### REQ-06: Randomness Disclaimer

(Previously: stated candidates statistically informed, draws random, no prediction improvement promised)

A visible disclaimer SHALL state that candidates are statistically informed over
historical draws, that draws remain random and FAIR, that NO METHOD can raise the
win probability, and that we only optimize payout-if-you-win and coverage. It
SHALL remain visible on load and after generation.

#### Scenario: disclaimer persists across states

- GIVEN idle and post-generation states
- WHEN each renders
- THEN the disclaimer text remains visible and includes the "no method raises win probability" statement
