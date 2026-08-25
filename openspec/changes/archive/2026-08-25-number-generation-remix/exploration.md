# Exploration: number-generation-remix

> SDD change `number-generation-remix` — artifact store: openspec.
> Language: English (SDD contract). Evidence-backed with file:line references.

## Current State

The "Mis Números" feature generates 5-number combinations via
`GenService.generate(lottery_id, count, seed)`
(`backend/src/backend/app/services/gen_service.py:113`). The pipeline:

1. Resolve the active `MetaSelection` and its `MetaSelectionEntry` rows
   (`gen_service.py:135`, `_read_selection_entries` at `:344`).
2. `allocate_count(entries, count)` distributes `count` across entries by score
   (`generators/allocation.py:31`).
3. Load the active F5 probability map from `prob_*` tables
   (`_load_distribution` at `gen_service.py:361`) — built by `probability_service`,
   **independent of meta/ml/dl** (grep for `meta|ml_|dl_` in
   `services/probability_service.py` returns nothing).
4. `sample_combinations(seed, pools, count, ...)` (`generators/sampling.py:49`).
   Per pool: `weights = [pool.probabilities[n] * pool.score for n in numbers]`
   (`sampling.py:88`).

**Verified key finding:** the `entry.score` multiplier is a *constant per pool*,
so it cancels inside `rng.choices` — the sampled number distribution depends
**only on the F5 map**. Across pools the F5 map is identical, so the meta scores
have **zero effect** on which numbers are produced. `entry.score` survives only
as a label (`score = entry_score × mean(P(n))`, `gen_service.py:185`).
Therefore the entire chain `features → ml → dl → bt → rank → select → opt` is dead
weight for generation.

`Draw` model (`models/draw.py:21`) exposes `jackpot` (Numeric, nullable) and
`winners` (Integer, nullable) — sufficient for an **EV lever (A)**. There is **no
sales/popularity column** anywhere → an **unpopularity/split-avoidance lever (B)
is impossible** without importing sales data.

`StatisticsService` (`services/statistics_service.py`) already computes frequency,
positional frequency, gaps, and a single scalar `entropy`
(`statistics_service.py:346`). It does **not** compute χ² goodness-of-fit or a
runs test — those must be added for bias detection (C).

## Affected Areas

- `backend/src/backend/app/services/gen_service.py` — generation orchestration;
  repurpose weighting (drop meta score, add statistical weights).
- `backend/src/backend/app/generators/sampling.py` — `WeightedPool` currently
  multiplies by `entry.score`; replace with transparent statistical weights
  (EV/bias/unpopularity/coverage) or honest uniform.
- `backend/src/backend/app/generators/allocation.py` — allocation by score;
  re-purpose or simplify.
- `backend/src/backend/app/services/probability_service.py` — F5 source; keep,
  enrich with coverage/unpopularity framing.
- `backend/src/backend/app/services/statistics_service.py` — add χ² / runs test
  for bias detection (C).
- `backend/src/backend/app/meta/*` (`scoring.py`, `selection.py`, `meta_service.py`)
  — candidates for **removal** from the gen path (dead for generation).
- `backend/src/backend/app/{feature_engineering,ml,dl,backtesting,optimization}/*`
  — candidates for **removal/retire** if not used elsewhere.
- `backend/src/backend/app/models/draw.py` — EV lever uses `jackpot`/`winners`;
  optional sales column would enable lever B.
- Frontend "Mis Números" UI + API response — add **honesty disclaimer** (no method
  raises win probability).
- `docs/BALOTO_RULES_AND_ENGINE_AUDIT.md` — already written (rules + audit + decision).

## Approaches

1. **Minimal repurpose (keep F5, drop meta wiring)**
   - Remove meta score from `WeightedPool`; sample from F5 (frequency/empirical).
   - Pros: tiny change, honest, keeps working generator. Cons: no new "edge".
   - Effort: Low.

2. **Statistical remix (recommended)**
   - Keep F5 as base; add transparent levers:
     - **A. EV gate**: compute `EV = (jackpot × p_win + lower_tier_expected) − cost`
       from `jackpot`/`winners`; surface "favorable now?" flag.
     - **C. Bias detection**: χ² over 768 draws vs uniform; runs test + entropy.
       If fair → state "no exploitable bias"; if anomalous → report.
     - **B. Unpopularity (conditional)**: avoid 1–31, 7, sequences to reduce split
       risk — only if sales data imported; fallback neutral.
     - **D. Coverage/wheeling**: optional structured minors within budget.
   - Pros: honest, auditable, maximizes payout-if-win + coverage. Cons: more code,
     lever B blocked by data.
   - Effort: Medium.

3. **Full removal of dead engines**
   - Delete `feature_engineering/ml/dl/backtesting/optimization` gen-path usage;
     retire `meta` selection/rank from generation.
   - Pros: less code, clearer architecture. Cons: risk if those engines serve
     other surfaces (backtesting UI, experiments).
   - Effort: Medium-High.

## Recommendation

Adopt **Approach 2 (Statistical remix)** combined with **partial Approach 3**:
repurpose `gen`/`probability`/`statistics` on levers A/C/D (+B if data), and
**decouple/retire the meta prediction chain from the generation path** (keep the
engines only if they power other surfaces). Add the honesty disclaimer. This
matches the user-approved decision and the mathematical boundary (no method
raises win probability).

## Risks

- **Scope creep / data gap:** lever B (unpopularity) needs sales data not present;
  must be explicit as out-of-scope or require a data-import task.
- **Removing meta may break other consumers** (backtesting/experiment UIs) — verify
  references before deletion.
- **Overclaiming:** any UI text implying higher odds violates the honesty
  constraint and user intent.
- **4-digit game:** user mentioned a grandmother's 4-digit notebook; it is **not
  modeled** in the current `Lottery` model — flag as out-of-scope unless decided.

## Ready for Proposal

**Yes** — but the proposal should first resolve a few product questions (proposal
question round): (a) remove dead engines entirely vs. just decouple from gen;
(b) include a sales-data import task to enable lever B, or mark B out-of-scope;
(c) include the 4-digit game in scope or defer; (d) exact disclaimer wording/location.
