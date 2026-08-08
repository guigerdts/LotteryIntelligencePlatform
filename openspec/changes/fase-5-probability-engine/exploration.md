# Exploration: Fase 5 — Probability Engine

**Change**: `fase-5-probability-engine` · **Store**: `openspec` · **Date**: 2026-08-08
**Artifact**: exploration · **Predecessor**: (none — initial exploration)

## 1. What We're Investigating

Does Fase 5 — Probability Engine have a clean, evidence-backed path, and what are the
open decisions sdd-propose must resolve? Specifically:

1. The **official name and responsibility** of Fase 5 in the approved design.
2. The **real state** of its dependencies (F1 Core, F2 Data, F3 Statistics, F4 Feature).
3. Which **Feature Engine contracts** (schema, versioning, fingerprint, determinism, lifecycle, API/CLI) Probability can reuse and which it must re-derive.
4. Which **data and features** Probability can actually consume today (given an EMPTY live DB).
5. The **documented vs. actual surface**: method lists, API shape, schema naming.
6. **Contradictions** between master docs and the implemented reality.
7. **Gaps** that block or constrain implementation.
8. **Scope boundaries** against Fase 6+ (and against "prediction").
9. The **set of decisions (D1–D6)** sdd-propose must resolve.

Method: read the 5 master docs, the archived SDD phase archives, the 3 main OpenSpec
specs, and verified every claim against the actual code (modules, models, migrations,
services, API routers, CLI) and the live SQLite DB.

---

## 2. Evidence Used

| Source | Path | What it establishes |
|---|---|---|
| Roadmap | `IMPLEMENTATION_ROADMAP.md` (Fase 5; Fase 3 state lines 131–149; dependency chain) | Canonical 6 methods; F3 pending list; chain Feature → Probability → Graph → ML… |
| Engine specs | `ENGINE_SPECIFICATIONS.md` §6 | Responsibility: "Calcular modelos probabilísticos"; 5 implementations |
| System arch | `SYSTEM_ARCHITECTURE.md` §6 + §4 + §9 | Probability engine responsibility; config includes "semillas aleatorias" (random seeds) |
| Feature eng | `FEATURE_ENGINEERING.md` §1, §12, §13 | Models consume only features; probability feature family; simulation stores confidence intervals |
| README | `README.md` Probability section + Fase 3 section | 7 probability items; implemented F3 contract (stat snapshot pattern) |
| Lottery theory | `LOTTERY_THEORY.md` LT-017..022 | 6 probability theories (matches roadmap) |
| API spec | `API_SPECIFICATION.md` §6, §2, §5 | 4 probability GET endpoints (no Poisson, no conditional); envelope; stale stats surface |
| DB schema | `DATABASE_SCHEMA.md` §3–4 | `probability_snapshot`, `montecarlo_runs` table names (draft, no fields) |
| OpenSpec spec | `openspec/specs/feature-engine/spec.md` (FES-01..10, FE-01..10) | F4 contract; Probability out-of-scope endnote; future-statistics |
| OpenSpec spec | `openspec/specs/statistics-engine/spec.md` (STE-01..13) | F3 contract; STE-13 excludes probability/scoring/analytics/ML/prediction |
| OpenSpec spec | `openspec/specs/backend/spec.md` (REQ-01..12) | `probability/` seam; `analytics/` composition; REQ-10..12 API/CLI pattern |
| Archived F4 | `openspec/changes/archive/2026-08-07-fase-4-feature-engine/{exploration,proposal,design}.md` | F4 decision history (incl. rejected D5); provider-contract sketch |
| Archived F3 | `openspec/changes/archive/2026-08-07-fase-3-statistics/design.md` + `verify-report.md` | `stat_*` pattern, lifecycle, determinism gate G9, read-only gate G10 |
| Code | `backend/src/backend/app/probability/__init__.py` | Empty seam, responsibility docstring |
| Code | `backend/src/backend/app/analytics/__init__.py` | Composition seam over statistics + probability |
| Code | `backend/src/backend/app/feature_engineering/{engine,registry,providers,fingerprint}.py` + `features/` + `services/feature_engine_service.py` | Registry, Kahn topo order, deterministic engine, input fingerprint, provider Protocols |
| Code | `backend/src/backend/app/statistics/{engine,generator,checksum}.py` + `services/statistics_service.py` | Pure Decimal metrics, `STATS_GENERATOR_VERSION`, deterministic reads, payload tables |
| Code | `backend/src/backend/app/models/{feature_snapshot,feature_value}.py` | `feature_*` schema (snapshot header + normalized values) |
| Code | `backend/src/backend/app/api/v1/{router,feature_engine,statistics}.py`, `cli.py`, `schemas/` | API/CLI parity + response envelope + error taxonomy |
| Runtime | `database/lip.db` (SQLite) | **EMPTY** — 0 lotteries, 0 draws, 0 stat/feature snapshots; alembic head 0006 |
| Repo | `backend/pyproject.toml`, `backend/uv.lock` | No numpy/scipy/pandas — pure Python + Decimal stack |

---

## 3. Dependency State

| Dependency | Status | Claim vs. Reality (verified in code) |
|---|---|---|
| Fase 0 — Foundation | ✅ complete | Seam package `backend/app/probability/__init__.py` exists with docstring "Probability engine: probabilistic models (Monte Carlo, Bayesian, ...)". `analytics/` asserts composition over `statistics/` + `probability/`. |
| Fase 1 — Core Domain | ✅ complete | lottery/draw/draw_numbers/super_number/dataset/dataset_draws; migrations 0001–0002; deterministic keyset read `ORDER BY draw_number, id` (used by F4 provider). |
| Fase 2 — Data Engine | ✅ complete | Import engine + immutable checksummed datasets; migrations 0003–0004; no import hooks fire from other engines (FES-09). |
| Fase 3 — Statistics | ✅ complete (core bundle) | `stat_snapshots` + 5 payload tables; `STATS_GENERATOR_VERSION="1.0.0"`; `CORE_METRICS = {frequency, positions, gaps, averages, entropy}` (generator.py:21); migration 0005. Delivered: frequencies, positions, gaps, averages, entropy. |
| Fase 3 (second tier) | ⚠️ missing | Distributions, trends, correlations — roadmap F3 "pendiente" (lines 141–147); absent from `CORE_METRICS`; no tables. |
| Fase 4 — Feature Engine | ✅ complete | `feature_snapshots`+`feature_values`; `FEATURE_GENERATOR_VERSION="1.0.0"`; FE-01..FE-10 registered (8 scalar values persisted; mapping features FE-07/FE-10 computed but not persisted); `input_fingerprint`; migration 0006; provider Protocols; `future-statistics` `draw_correlation` declared, never computed (FES-08). Archived at af69abb. |
| Live data | ⚠️ **empty** | `database/lip.db` at alembic head (0006) with 0 lotteries, 0 draws, 0 stat/feature snapshots. Only datasets are `backend/tests/fixtures/*.csv`. |

**Verdict**: F1–F4 deliver everything their archives claim, verified in code. The real
gaps are (a) no data has ever been imported into the live DB (the engine stack is
exercised against fixture files), and (b) F3's second-tier metrics (distributions /
trends / correlations) genuinely do not exist yet.

---

## 4. Existing Architecture Relevant

Both engines F3/F4 hard-won contracts (verified live):

1. **Snapshot schema pattern** — header (`snapshots`) + normalized payload values; immutable; `active|retired|failed`; `is_locked`; `UNIQUE(lottery_id, scope, version)`; exactly one `active` per (lottery, scope); atomic write; `failed` header persisted on batch/engine failure (never `active`/`partial`).
2. **Version identity** — engine-own generator version (`STATS_GENERATOR_VERSION`, `FEATURE_GENERATOR_VERSION`), bumped only on algorithmic/meaning change; never tied to app deploy or import.
3. **Determinism (G9-style)** — same {draws checksum + generator version + optional stats identity} ⇒ byte-identical outputs; `ORDER BY draw_number, id` on every read; INTEGER/Decimal-exact accumulators; **float never enters a checksum or persisted value**; canonical JSON (`sort_keys=True`, compact separators).
4. **Input fingerprint** — canonical SHA-256 over *inputs* (draws range+checksum, per-feature `{id, version, params}`, optional stats identity); used as the invalidation key for idempotency/recompute.
5. **Provider Protocols** — engines depend only on `Protocol` interfaces at the composition root (`DrawProvider`, `StatisticsProvider`, `DatasetProvider`); missing data → skipped/absent, never guessed.
6. **Lifecycle / manual only** — generation on-demand (CLI `lip … generate|rebuild` + `POST /generate`), no scheduler, no import hooks (STE-12/FES-09); API GET reads from stored snapshots, never precompute; missing snapshot surfaces `SNAPSHOT_NOT_FOUND` (404).
7. **Multi-lottery** — every snapshot scoped by `lottery_id`; rules from the lottery row (`min_number`, `max_number`, `numbers_to_select`).
8. **Migration ownership** — Alembic only; `down_revision` chain 0001→0006; rollback drops only the phase's tables (F4 rollback drops only `feature_*`).
9. **Service error taxonomy** — envelope codes `RESOURCE_NOT_FOUND` (404), `SNAPSHOT_NOT_FOUND` (404), `generation_error` (500), `definition_error` (500), `validation_error` (422).

---

## 5. Available Contracts

### Feature Engine (F4) — what Probability can consume today
- `feature_snapshots` header (lottery_id, feature_set=`core`, version, feature_engine_version, checksum, input_fingerprint, status, is_locked, draw_count, draws_from, draws_to) + `feature_values` `Numeric(20,8)` per (feature_id, feature_version, draw_number).
- Registered FE-01..FE-10: draw_sum, draw_mean, draw_range, odd_even_ratio, low_high_ratio, consecutive_count, decade_distribution, repeated_from_previous, max_current_gap, current_frequency. **Only scalar values are persisted**; the mapping features (FE-07 decade_distribution, FE-10 current_frequency) are computed and fingerprinted but have no stored cell.
- `StatisticsProvider` in the **actual** F4 code exposes only `active_snapshot()` + `scalars()` — no frequencies/gaps/positions read methods (those live behind `statistics_service.read_*` + the payload repository).
- `future-statistics` `draw_correlation` registered/versioned but never computed (FES-08).

### Statistics (F3) — currently readable surfaces
- `stat_frequency` (number, count), `stat_frequency_positions` (number, position, count), `stat_gaps` (count, min/max/avg per number), `stat_averages` (series_key, mean, non_null_count), `stat_scalars` (e.g. entropy) — deterministic ordered reads through the service (`read_frequencies(last)`, `read_gaps(last)`, `read_averages`), available only when an active `core` snapshot exists.

### Core Domain — raw, always readable
- `draw` (draw_number, draw_date as metadata, jackpot, winners, is_deleted), `draw_numbers` (position, number), `lottery` rules (min_number, max_number, numbers_to_select, super-number range).
- Deterministic keyset read `ORDER BY draw.draw_number, draw_numbers.id` (the F4 provider pattern).

### What is NOT available today
- F3 second-tier metrics (distributions, trends, correlations).
- Co-occurrence / joint counts — deferred to Fase 6 (Graph Engine; "Correlaciones" pending in F3 roadmap; `draw_correlation` future in F4).
- Live data: the DB is empty — Probability must handle the 0-draw / 0-snapshot case (like F4: `draws_from=0, draws_to=0`, empty result or validation error), and tests must run against fixtures.
- `draw_correlation` feature values (declared, never computed).

---

## 6. Documentary Contradictions

| # | Contradiction | Evidence | Impact |
|---|---|---|---|
| C1 | **Probability method lists differ across 5 docs** | Roadmap: MC, Bayes, Hypergeometric, Binomial, Poisson, conditional (6) · ENGINE_SPECIFICATIONS §6: MC, Bayes, Poisson, Binomial, Hypergeom (5 — omits conditional) · README: Binomial, Hypergeometric, Poisson, Bayes, Conditional, **Confidence intervals**, MC (7) · SYSTEM_ARCHITECTURE §6: MC, Bayes, Distribuciones, Simulación, conditional (generic) · API_SPEC §6: only 4 GET endpoints (no Poisson, no conditional) | The **ROADMAP + LOTTERY_THEORY (LT-017..022 — same 6)** are the authoritative list; confidence intervals appear only in README (treat as sub-output of MC, not a standalone method). The proposal MUST pick the canonical set (the roadmap 6) and note the deviation of ENGINE_SPECS/API_SPEC. |
| C2 | **API_SPECIFICATION's probability endpoints are GET `/probability/{method}`** | §6 lists GET-only endpoints (no request body); F3/F4 both overrode similar spec surfaces with POST `/generate` + GET reads + snapshot pattern (the §5 statistics GETs were not implemented verbatim either). | Probability API will likely diverge from the API doc the same way: snapshot-driven generation + reads. Decide in proposal whether the documented GET endpoints survive as thin on-demand wrappers or are superseded by the snapshot pattern (recommended). |
| C3 | Roadmap lists "Entropía" under F3 **pending**, but entropy shipped in F3 core | `statistics/engine.py` `entropy_base2` + `CORE_METRICS` includes entropy (found in F4 exploration) | Stale roadmap item; entropy is available today. No impact on F5 beyond noting the roadmap's pending list is stale on this point. |
| C4 | F4 spec endnote marks Probability as out of scope labeled "(Fase 6)" | `openspec/specs/feature-engine/spec.md` purpose: "Graphs, co-occurrences, ML, Probability, Prediction are out of scope (Fase 6)"; roadmap puts Probability = **Fase 5** | Cosmetic mislabel; Probability IS Fase 5. No user impact — note in proposal. |
| C5 | **PROJECT_STATUS.md + README header are stale** — STATUS says F4 "Pendiente" and last tag fase-3, while HEAD af69abb archived F4; README says "Estado: Fase 0" | files verified | Hygiene task, not a blocker; refresh during the F5 change (as a chore). |
| C6 | **DATABASE_SCHEMA.md table names do not match the live schema** — `statistics_snapshot` (live: `stat_snapshots`); `feature_definition`/`feature_value` (rejected in F4 D5); `probability_snapshot`, `montecarlo_runs` are draft names only (no fields) | DB schema doc vs. migrations 0005/0006 | For F5: the draft names are not a contract. Follow the `stat_*`/`feature_*` precedent — F4 explicitly rejected the old `feature_value(draw_id, value)` shape for lack of snapshot/version/checksum; F5 must likewise reject a naive `montecarlo_runs` design unless the design builds the snapshot+determinism layer on top. |
| C7 | **Feature-sourcing overlap** — FEATURE_ENGINEERING §1 says "All models consume exclusively features", and §12 lists probability features (empirical, accumulated, conditional, Score Bayesiano, Score Monte Carlo) that README lists as Probability *engine* capabilities | FEATURE_ENGINEERING vs README | Reconciliation: F5 computes probability **values**; exposing them as `feature_*` inputs / "scores" is F4/F7 territory (a future-statistics-type feature). The proposal must state who owns what. |

---

## 7. Gaps and Risks

| Severity | Gap / Risk | Evidence | Mitigation |
|---|---|---|---|
| **HIGH** | **The determinism contract cannot be trivially extended to Monte Carlo** — the whole platform demands byte-identical outputs for identical inputs (STE-05 / FES-05), but a naive MC is a random draw. The project has **no** `numpy`/`scipy`/`random` import anywhere; everything is pure-Python + Decimal. | `pyproject.toml` (no numeric deps), `statistics/engine.py` + `feature_engineering/` (Decimal-only) | Design a fixed-seed PRNG: `random.Random(seed)` where seed = canonical hash of {input fingerprint, model params, generator version}; then MC is as reproducible as the rest. Alternatively, decide to introduce a deterministic PRNG/numeric dependency (a buy — decision in D2). |
| **HIGH** | **No live data** — zero lotteries/draws/snapshots in the DB | direct inspection of `database/lip.db` | Tests must run against fixture CSVs via the import pipeline (as F4 did); proposal must state "no live data" in the verification/acceptance section. |
| **MED** | **F4's `StatisticsProvider` exposes only `scalars()`** — frequencies/gaps (raw material for empirical probability) are reachable only through `statistics_service.read_*`, not through the F4 seam | `feature_engineering/providers.py` | Either F5 defines its own provider seam reading `stat_*` via the statistics *service* (not its internals), or F4's protocol grows a frequency read. Decision D5. |
| **MED** | **Conditional probability P(A|B) needs joint counts** — co-occurrence data belongs to the Graph Engine (F6) and is computed nowhere today (F3 "correlaciones" pending; F4 `draw_correlation` future). Naive per-request joint counting is O(draws × subset) and unbounded | `registry.py` (draw_correlation future), roadmap | In slice 1, define conditional as a historical-window **univariate conditional** (e.g. P(number given last-N window / moving filter) from Core draws), keep pairwise conditionals as declared-but-not-computed (F6-bound). Decision D6. |
| **MED** | **Distribution formulas at large n without numeric libraries** (factorials, C(n,k), P mass) | no scipy in deps | Python `int` handles arbitrarily large integers exactly; use combinatorics + Decimal to avoid float (`math` not needed; if `math` is added, avoid `math.lgamma` — floats leak). Scipy is an optional dependency decision (D2). |
| **MED** | **Schema choice for `prob_*`** — MC runs produce per-run aggregates + empirical distributions; exact models produce per-number / per-draw probabilities; Bayes produces posterior scalars. One normalized payload may be awkward; `DATABASE_SCHEMA.md` hints at a `montecarlo_runs` table | DB schema doc vs F3/F4 pattern | Retain a `prob_snapshots` header and choose the payload shape in D1/D4: normalized `prob_values (snapshot_id, model_id, subject, draw_number|NULL, value)` vs per-run blob (MC histograms). |
| **LOW** | Stale docs (PROJECT_STATUS, README status header) | — | Chore during the change/archive. |

---

## 8. Scope Boundaries

### In Fase 5 (per roadmap canonical list)
- Probability Engine package `backend/app/probability/` implementing the **6 canonical methods**: Monte Carlo, Bayes, Hipergeométrica, Binomial, Poisson, Probabilidad condicional — under strict determinism (fixed-seed MC), exact Decimal math, mirroring the `stat_*`→`prob_*` contract.
- Provider protocols (Draw / Statistics / Feature) — consuming `draw_*`, `stat_*`, and `feature_*` through interfaces only.
- Snapshot persistence + migration 0007 (`prob_*`); manual generate/rebuild CLI (`lip probability generate|rebuild`); API (`POST /probability/generate`, GET reads); envelope + error taxonomy reuse; multi-lottery; `active|retired|failed`.

### Explicitly OUT OF SCOPE for Fase 5
- **Graph Engine (F6)** — co-occurrence matrices, networks, centrality, communities, pairs graphs.
- **Machine Learning (F7)** — model training/inference/ranking, and any "prediction of outcomes".
- **Deep Learning (F8)** — neural nets.
- **Optimization (F9)** — search over combinations that maximize a score (that is Generator F13 + Optimization F9); F5 *reports* probabilities, F5 does not *generate* candidate combinations.
- **Backtesting (F10)** — walk-forward comparison; F10 will later consume the random-expectation baseline from F5 (documented deferral).
- **Experiments (F11), Meta-learning (F12), Generator (F13), Dashboard (F14), AI Assistant (F15)**.
- **"Prediction"** — the project philosophy is explicit: LIP is *not* a lottery predicting tool. F5 computes probabilities of events from rules + data (a number appearing in the k-th position, a sum-range probability, hypergeometric match counts) and provides baselines; selecting/predicting the "next winning" combination belongs to F7/F13. State this boundary in the proposal so the user can correct it if they actually want a predictor.
- **Feature-sourcing** — registering probability scores as Feature Engine features (FEATURE_ENGINEERING §12/§14: empirical score/Score/MC score) is a later F4/F7 activity, not part of F5.

### Dependency edges from F5 → later
- **F6 Graph**: expected frequencies / null-model baselines that co-occurrence metrics will be compared against.
- **F7 ML**: empirical probabilities and Bayesian posteriors become candidate features/priors.
- **F10 Backtesting**: hypergeometric null-model baselines for hit-rate evaluation.
- **F13 Generator**: per-number / per-position probability constraints feeding combination scoring.
- **`analytics/` composition**: after F5, the `analytics/` seam (composition over statistics + probability, REQ-01) becomes implementable — decide in D6 whether a thin composition slice lands in F5 or a later change (recommend later).

---

## 9. Open Decisions (D1–D6)

| ID | Decision | Context | Options |
|----|----------|---------|---------|
| **D1** | **Schema design: `prob_*` snapshot pattern vs other** | Must mirror `stat_*`/`feature_*` to preserve the checksum/determinism/lifecycle contract; `DATABASE_SCHEMA.md` `montecarlo_runs` is a draft name with no fields | A) `prob_snapshots` header + `prob_values` normalized payload (row per (subject, draw_number \| NULL, value, params)) — mirror F3/F4 (recommended). B) `prob_snapshots` + `prob_montecarlo_runs` blob per DATABASE_SCHEMA names — needs design justification for determinism/checksum. C) Hybrid: normalized core values + optional per-run distribution blob for large MC histograms. |
| **D2** | **Determinism contract for probabilistic computations** | MC is inherently random; the project contract (STE-05/FES-05) requires byte-identical reruns for identical inputs. No `numpy/scipy/random` exists in the stack yet | A) **Fixed-seed PRNG** — `random.Random(seed)` with seed = canonical hash of {input fingerprint + params + generator version}; integer-combinatorics + Decimal math; floats never persisted (recommended: keeps the determinism gate applicable to MC). B) Add a pinned dependency (e.g. `scipy.stats`, `numpy.random`) — new dependency decision. C) Non-deterministic MC — breaks the project contract (not recommended). Also decide what MC persists: aggregates only vs simulated histograms (volume). |
| **D3** | **Semantics of "probability"** | Docs are ambiguous: exact by-number distributions (hypergeometric, binomial, Poisson), empirical rates, conditional, Bayes, and possibly predictive inference. API doc implies compute-per-request. Roadmap vs API_SPEC differ | Define explicitly in the proposal: F5 computes **exact combinatorial values from rules** (hypergeometric, binomial, Poisson), **empirical values from `stat_*` frequencies** (empirical/conditional probability), **MC-derived empirical distributions** from simulation, and **empirical-Bayes posteriors** with declared priors — and is explicitly **NOT predictive** (prediction → F7). The proposal's scope section must be the single source of truth. |
| **D4** | **Persist snapshots vs compute on demand** | F3/F4 precedent: repeatedly-read results are versioned snapshots; point/small-window reads answer on demand without precompute (STE-10). MC runs can be expensive; per-request recompute violates the read contract | A) Snapshot everything into `prob_*`; reads serve from the active snapshot (recommended). B) Compute-only API (GET computes with params — matches API doc §6 but loses determinism/checksum/persistence and the "read never precomputes" rule). C) Hybrid per STE-10: snapshot expensive run-level results; small windows/percentiles recomputed on demand from stored bases. |
| **D5** | **How F5 consumes F4/F3 outputs** | F4's `StatisticsProvider` exposes only `active_snapshot()` + `scalars()`; empirical probability needs frequency/gap data. Extending F4's protocol touches an archived spec | A) F5 defines its own provider Protocols (`DrawProvider`/`StatSnapshotRead`/`FeatureSnapshotRead`) with adapters over the existing read *services* (not F4/F3 internals) — mirrors FES-06 (recommended). B) Extend F4's `StatisticsProvider` (only if F5 output must be F4-style features). C) F5 reads Core draws only and re-rolls empirical counts (duplicates Statistics; rejected). |
| **D6** | **Slice scope: which methods in slice 1 + API shape** | Six methods is a large surface; exact formulas are cheap, MC needs the PRNG design (D2), Bayes/conditional need count/joint semantics (D3), confidence intervals are README-only extras. F3/F4 precedent = one coherent `core` bundle per slice | A) **Slice 1 = the roadmap's canonical 6 in one bundle** (recommended): hypergeometric+binomial+Poisson exact, empirical/conditional from `stat_*`/draws, MC with seed architecture, Bayes with declared priors; defer CI, histograms, and API-doc-divergent endpoints. B) Slice 1 = exact distributions only; MC+Bayes+conditional later. C) Slice 1 = descriptive probability + empirical rates only (no MC no Bayes). Rationale: A mirrors how F3 (`core` bundle) and F4 (FE-01..10 slice) shipped one complete declared surface each. |

---

## 10. Recommendation

**Fase 5 is READY for sdd-propose**, provided the proposal (1) resolves D1–D6 as
explicit decision blocks, (2) states the documented contradictions (C1 method list,
C2 API shape, C6 schema names, C7 probability-vs-feature ownership), and (3) declares
the empty-live-DB reality as an acceptance constraint (tests run against fixtures).

Recommended default positions to propose:
- **Mirror F3/F4**: `prob_snapshots` + `prob_values`, engine version constant, checksum
  + input fingerprint, immutable lifecycle, manual-only CLI/API, read-from-snapshot
  GETs, multi-lottery, migration 0007 with non-destructive rollback.
- **Determinism (D2) = fixed-seed PRNG** seeded from the canonical input fingerprint +
  params + generator version; integer/Decimal-exact arithmetic; floats never persist.
  This preserves the platform's "byte-identical reruns" gate for this phase, and the
  seed policy is the single genuinely new architectural element F5 introduces.
- **Canonical method set = roadmap 6** (MC, Bayes, Hipergeométrica, Binomial, Poisson,
  condicional), corroborated by LOTTERY_THEORY LT-017..022. Confidence intervals are
  treated as MC-derived outputs, not a schema method. API doc GETs do not need to be
  preserved verbatim; snapshot reads are the rule.
- **Consume via F5-owned provider protocols (D5)** — Feature/Statistics snapshot reads
  through service seams, never F3/F4 internals, writes confined to `prob_*`.
- **Stay strictly out of Graph/ML/DL/Backtesting/Generator scope and of "prediction"** —
  F5 computes distributions and expectations, not "winning numbers".

**What must happen before/at proposal**:
1. Resolve D1–D6 (each is a decision block in the proposal).
2. Refresh PROJECT_STATUS.md/README status (stale docs; cheap chore).
3. Decide whether the `analytics/` composition slice and confidence-interval/percentile
   outputs are deferred to later slices — recommendation: defer ALL non-canonical extras.

### Ready for Proposal: Yes

Advise the user: exploration analyzed the 5 master docs, the archived Fase 0–4
artifacts, and verified every contract against the running code and the live DB. Fase 3
and Fase 4 are confirmed complete; dependencies for F5 are present (except live data,
testable via fixtures). The six open decisions are now framed for the proposal. The one
non-trivial architectural novelty — deterministic Monte Carlo — is previewed here with
a recommended fixed-seed policy. Ready to draft the proposal on confirmation of D1–D6.