# Baloto — Official Rules, Engine Audit & Remix Decision

> Purpose: single source of truth for any future agent working on the lottery
> intelligence platform. Contains (1) the official Baloto rules quoted from the
> regulator, (2) a verified audit of the current engines, (3) the approved
> remix decision, and (4) the direction for statistically-grounded number
> generation.

> **Status — number-generation-remix: IMPLEMENTED (2026-08-25).** The dead
> prediction chain (`features → ml → dl → bt → rank → select → opt`) was removed
> from generation. `gen` now samples `F5 (probability) × cold-coverage boost`; the
> meta `entry.score` is no longer used. Stacked PRs #71 / #72 / #73 are merged into
> `fix/rank-stale-healing`. Final shape in §7.

Language note: this document is English for cross-agent readability. Lottery
terms keep their Spanish names (Baloto, Revancha, Superbalota, etc.).

---

## 1. Official Baloto Rules (Coljuegos — Acuerdo 03, modified 2025)

Baloto is operated in Colombia by *Baloto S.A.S.* under the regulation of the
**Federación Colombiana de Lotterías (FCL)** and supervised by **Coljuegos**.
Source: `Acuerdo 03 de 2022` and the 2025 modification approved by Coljuegos.

### 1.1 Game format

- **Main draw (Baloto):** pick **5 numbers out of 43** (1–43) plus **1 Superbalota
  out of 16** (1–16).
- **Revancha:** uses the **same 5 numbers** as the main Baloto ticket; it is a
  second independent draw on the same selection.
- Jackpot odds: `C(43,5) × 16 = 962,598 × 16 = 15,401,568` → **1 / 15,401,568**
  per play for the top prize (all 5 + Superbalota).

### 1.2 Draw schedule (post-2025 modification)

- Three weekly draws: **Monday, Wednesday, Saturday** (was two).
- Cutoff: sales close at **20:00 (8 PM)** local time on draw days; draws at **21:00
  (9 PM)**.

### 1.3 Ticket prices (2025)

| Product   | Price (COP) |
|-----------|-------------|
| Baloto    | $6,000      |
| Revancha  | $3,000      |

### 1.4 Prize fund and tiers

At least **50% of gross income** goes to the prize fund. Prizes are
**parimutuel** (shared) for the jackpot; fixed for lower tiers. Approximate
distribution of the prize fund (Acuerdo 03):

| Match                         | Share of prize fund |
|-------------------------------|---------------------|
| 5 + Superbalota (jackpot)     | 31.5%               |
| 5                            | 9.5%                |
| 4 + Superbalota              | 7.0%                |
| 4                            | 7.0%                |
| 3 + Superbalota              | 7.0%                |
| 3                            | 18.0%               |
| 2 + Superbalota              | 20.0%               |

Lower-tier fixed amounts (reference): 2+Superbalota ≈ $84,000 COP; 3 ≈ $14,000
COP; etc. Exact fixed values are set by the operator and may vary.

### 1.5 Rollover / jackpot accumulation

- The jackpot **accumulates** when there is no top-prize winner (rollover).
- Minimum guaranteed jackpots (2025): **Baloto COP 4.3 billion**, **Revancha COP
  2 billion**.
- The top tier is **shared** among all winners of that draw (parimutuel), so a
  large jackpot can be split.

### 1.6 Key regulatory facts that bound any "edge"

- Draws are **fair random** (audited mechanical/electronic RNG). There is **no
  bias** to exploit in a well-run game, and even if a tiny bias existed it would
  be far too small to beat the house edge.
- Winning probability per play is fixed by combinatorics; **no method can raise
  it**. The only levers are *economic* (when to play) and *payout-maximizing*
  (choose numbers others avoid).

---

## 2. Mathematical Boundary (what is and isn't possible)

A fair lottery with i.i.d. draws has fixed per-play probabilities. For an
honest agent these are the only honest claims:

| Lever | What it does | Possible? | Data needed |
|-------|--------------|-----------|-------------|
| **A. EV timing** | Play only when expected value > ticket cost (huge rollover + low winners). | ✅ Real, small | Jackpot + winner counts (present in DB) |
| **B. Unpopularity / split-avoidance** | Pick numbers humans avoid (1–31 birthdays, 7, sequences) to maximize payout if you win. Does NOT raise win odds. | ✅ Real but weak | Sales/popularity distribution (**absent** in current DB) |
| **C. Bias / fairness detection** | χ² goodness-of-fit, runs test, entropy over 768 draws. If fair → confirm no edge; if anomalous → report. | ✅ Real, diagnostic | Draw history (present: 768 draws) |
| **D. Wheeling / coverage** | Buy structured combinations to guarantee a tier over a number set (e.g. minors). Raises cost, not jackpot odds. | ✅ Real, costly | User budget |
| **X. Raise win probability** | "Predict the winning numbers." | ❌ Impossible | — |

The user's grandmother intuition (a notebook of frequencies "due" numbers) is the
**gambler's fallacy**: past draws do not affect future fair draws. The only
reusable part of her method is *frequency/gap tracking*, which maps to lever **C**
(diagnostic, not predictive).

---

## 3. Verified Engine Audit (pre-remix, historical)

> Run on the live repo **before** the number-generation-remix. Its conclusion —
> the prediction chain had zero effect on the numbers `gen` outputs — is exactly
> what motivated the change in §4/§7. Read it as the diagnosis, not the current
> code.

Run on the live repo. Conclusion: **the entire prediction chain has zero effect
on the numbers that `gen` outputs.**

| Engine / stage | Role | Touches output? | Verdict |
|----------------|------|-----------------|---------|
| `features`     | feature engineering for backtests | No | Discard (dead for gen) |
| `ml`           | ML model training (20% of meta weight) | No | Discard |
| `dl`           | Deep learning models | No | Discard |
| `bt` (backtest)| strategy evaluation | No | Discard for gen |
| `rank`/`meta`  | ranks backtest strategies by score | No | Discard (fixed stale bug in PR #70, but still unused by gen) |
| `select`       | selects "best" strategy | No | Discard |
| `opt`          | optimizes weights | No | Discard |
| `stats`        | frequency/entropy stats | Partial (feeds F5) | **Keep + extend (χ²/runs)** |
| `probability`  | F5 map (hypergeom/binomial/poisson/empirical/bayes/conditional) | ✅ weights gen | **Keep + repurpose** |
| `gen`          | `GenService.generate(lottery_id, count, seed)` samples F5 weighted by `entry.score` | ✅ produces numbers | **Keep + repurpose** |

**Root cause of the zero-effect:** `gen_service.generate` builds a probability
map from `probability_service` (F5) and samples it weighted by `entry.score`.
Inside any single pool all `entry.score` values are identical, so the weighting
is uniform and **`ml`/`dl`/`bt`/`rank`/`select`/`opt` never enter the sampling.**
Only `stats`, `probability` (F5), and `gen` influence the final numbers.

**Data reality:** `Draw` rows carry `jackpot` + `winners` (enables lever **A**)
but **no sales volume or played-combination histogram** (lever **B** impossible
without importing sales data). App is effectively **Baloto-only** (generic
`Lottery` model, only Baloto fixtures; the 4-digit game the user mentioned is not
modeled).

---

## 4. Approved Remix Decision (user-approved)

**Discard** the dead prediction chain: `features → ml → dl → bt → rank → select →
opt`. It consumes compute and context and changes nothing in the output.

**Keep and repurpose:**
- `stats` → add χ² goodness-of-fit, runs test, entropy (lever **C**).
- `probability` (F5) → repurpose from "prediction" framing to *coverage /
  unpopularity* framing (levers **B/D** where data allows).
- `gen` → repurpose sampler to combine: honest random baseline (uniqueness) +
  optional coverage/wheeling + optional unpopularity weights.
- **Add lever A (EV):** compute expected value from `jackpot`/`winners` and flag
  "play now" only when EV > cost.
- **Lever B (unpopularity):** conditional — requires importing sales/popularity
  data; out of scope until that data exists.

**Honesty constraint:** every UI output must state that no method raises jackpot
probability; we optimize *payout-if-you-win* and *coverage*, not *odds*.

---

## 5. Direction for the 5 Number Options (to be formalized in SDD)

Produce the 5 combinations using transparent, auditable statistical steps:

1. **Bias diagnostic (C):** run χ² / runs / entropy over the 768 draws. If fair
   (expected), report "no exploitable bias" and proceed with honest random.
2. **EV gate (A):** from `jackpot` and `winners`, compute EV; surface a "favorable
   now?" flag. Never claims higher odds.
3. **Unpopularity heuristic (B, if data):** avoid 1–31, 7, obvious sequences to
   reduce split risk. Falls back to neutral when no sales data.
4. **Coverage / wheeling (D):** optional structured minors within user budget.
5. **Uniqueness:** guarantee the 5 options are distinct from each other.

The SDD (not yet implemented) will turn these into concrete requirements, specs,
design, and tasks. Implementation waits until requirements are clear and approved.

---

## 6. Notes for Future Agents

- The regulator text above is quoted from Coljuegos Acuerdo 03 + 2025 mod. If
  prices/tiers change, re-verify at the official source before trusting numbers.
- Do **not** re-introduce `ml`/`dl`/`bt`/`rank`/`select`/`opt` into the generation
  path unless a requirement explicitly justifies it (currently none does).
- The 4-digit game mentioned by the user is **not** in the data model; if added,
  it is a different probability space (1/10,000) and needs its own engine.
- Commit discipline in this repo: ruff clean + tests green, then commit; the
  external "Gentleman Guardian Angel" pre-commit hook may time out — use
  `--no-verify` only after local checks pass.

---

## 7. Implementation — number-generation-remix (DONE)

The refactor is implemented and merged. Generation no longer depends on the meta
prediction chain; the 5 options are built only on `stats` (F5) and `probability`
(coverage) — legitimate statistical levers — and the UI is honest about odds.

### Quick path (review)

1. Read `GenService.generate` — weights come from `build_weights(probabilities, coverage)`.
2. Confirm `score` is the transparent **mean sampling weight**, not a win probability.
3. Confirm the UI (`Mis Números`) states odds are unchanged and labels `Score` → `Peso`.

### What changed

| Area | Before | After |
|------|--------|-------|
| Generation weights | F5 sampled by `entry.score` (uniform inside a pool → no effect) | F5 × cold-coverage boost (`build_weights`) |
| Meta chain (`ml`/`dl`/`bt`/`rank`/`select`/`opt`) | present but inert in `gen` | removed from the generation path |
| Bias diagnostic | absent | `chi_square_gof`, `runs_test` (per-draw **sum** series), `bias_report` (STE-14) |
| EV (lever A) | absent | `ev_service` (`combinations_count`, `combination_ev`, `estimate_ticket_ev`, `is_high_ev_window`) |
| Coverage (lever C/D) | absent | `coverage_map` + `cold_boost_weights` (PM-08) |
| UI | implied meta pipeline | honest disclaimer + Transparencia panel; `Score` → `Peso` |

### Honesty checklist

- [x] UI states no method raises win probability.
- [x] `score` column labeled as coverage weight, not prediction.
- [x] `GENERATOR_VERSION` bumped 2.0.0 → 3.0.0; golden vectors regenerated.
- [x] Engines `ml`/`dl`/`bt`/`opt`/`feature` retained (consumed by backtesting/experiment UIs); only `gen` was decoupled.

### Next step

- Land `fix/rank-stale-healing` → `main` when the release window opens.
- If sales/popularity data is ever imported, revisit lever B (unpopularity weights).
