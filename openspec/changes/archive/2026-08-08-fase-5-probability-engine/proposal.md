# Proposal: Fase 5 — Probability Engine

**Change**: fase-5-probability-engine · **Store**: openspec · **Date**: 2026-08-08
**Artifact**: proposal · **Predecessor**: exploration

## 1. Intent

Fase 5 delivers the Probability Engine: an independent, deterministic, result-only engine that computes exact combinatorial probabilities (hypergeometric, binomial, Poisson), empirical probabilities from `stat_*` frequencies, deterministic Monte Carlo simulation, and empirical-Bayes posteriors with declared priors — persisted as immutable, versioned, fingerprinted `prob_*` snapshots following the proven F3/F4 contract (STE-01..13, FES-01..10). It establishes the platform's first genuinely new architectural element — a fixed-seed PRNG that keeps Monte Carlo inside the byte-identical determinism gate — and produces reproducible, reviewable odds baseline artifacts that later fases (F6 Graph null-models, F7 features/priors, F10 backtesting baselines, F13 Generator constraints) consume.

## 2. Scope

### In scope
- `backend/app/probability/` package: pure model functions (6 canonical methods), provider Protocols, deterministic engine, fingerprint/checksum, `PROB_GENERATOR_VERSION`.
- Migration `0007_prob_tables`: `prob_snapshots` (header) + normalized `prob_values` payload; rollback drops ONLY `prob_*`.
- `ProbabilityService`: idempotent generate (incremental/full), atomic persist with `active|retired|failed`, retire-on-replace, failed-mark on error (mirror of `statistics_service.py` / `feature_engine_service.py`).
- Manual CLI `lip probability generate|rebuild` + `POST /probability/generate` + snapshot-read GETs; envelope/error taxonomy reuse; multi-lottery; `SNAPSHOT_NOT_FOUND` 404 when no active snapshot.
- Fixture-driven tests via the import pipeline (`EMPTY live DB`); graceful 0-draw / 0-snapshot states (F4 `draws_from=0, draws_to=0` precedent).

### Out of scope
- Prediction, ML/DL, number generation, betting recommendations, optimization (F7/F8/F9/F13) — LIP is not a predicting tool; F5 computes event probabilities and baselines only.
- Pairwise/co-occurrence conditionals (F6 Graph joint counts exist nowhere; F3 correlations pending, F4 `draw_correlation` future) — declared, never computed.
- Confidence intervals as a standalone schema method — they are MC-derived outputs only.
- Feature-sourcing: registering probability scores as `feature_*` inputs is later F4/F7 activity (C7).
- `analytics/` composition slice (REQ-01 seam stays empty this change); non-canonical API-doc GET wrappers; histogram blobs.
- Any new numeric dependency (no numpy/scipy per `pyproject.toml`).

### Capabilities — CONTRACT for sdd-spec
- **New capability** `probability-engine` → `openspec/specs/probability-engine/spec.md` (engine requirements PES-01.. + per-method requirements PM-01..06, one coherent `core` bundle like F3/F4).
- **Modified**: None — F3/F4/backend specs unchanged; reads of `stat_*` go through existing service seams.

## 3. Decisions (D1–D6)

### D1: Persistence — snapshot pattern, mirror F3/F4
`prob_snapshots` header + normalized `prob_values` payload (`model_id, model_version, subject, draw_number|NULL, value, params` — INTEGER/Decimal only). Justification: identical to `stat_*`/`feature_*` (version identity, checksum, input fingerprint, immutable lifecycle, atomic write, read-from-snapshot). The `DATABASE_SCHEMA.md` `montecarlo_runs` name is a field-less draft (C6); F4 already rejected a naive `feature_value(draw_id, value)` shape for missing snapshot/version/checksum (archived F4 D5) — same rejection applies here.

### D2 — Monte Carlo determinism
- PRNG: **`random.Random(seed)` isolated instance** — never global `random`, no OS entropy, no new dependency.
- **Seed derivation**: `int.from_bytes(sha256(canonical_json({input_fingerprint, model_params, n_simulations, PROB_GENERATOR_VERSION})).digest()[:16], "big")` — canonical SHA-256 over exactly the same canonical inputs.
- **`n_simulations` is a versioned parameter** — part of the fingerprint + seed.
- Floats never enter a checksum or persisted value (FES-05); counters are int, results Decimal-quantized once.
- Params or version change ⇒ new seed ⇒ different (but deterministic) run — correct; old immutable snapshot keeps its seed/values.

### D3 — Definition of "probability"
| In (owned) | Out (not owned) |
|---|---|
| Exact combinatorial from rules (hypergeometric C(n,k), binomial, Poisson) | Prediction of outcomes (F7) |
| Empirical rates from `stat_*` frequencies | ML/DL scoring/training (F7/F8) |
| Univariate conditional on historical window (draws/stat_*) | Number/combination generation (F13) |
| MC-rule simulation + CI percentiles | Betting/game recommendations |
| Empirical-Bayes with declared priors | Any unspecified predictive inference |

Precedence: Roadmap lines 176–181 + LOTTERY_THEORY LT-017..022 (same 6) are the canonical list (C1).

### D4 — Persistence vs on-demand
Snapshot (generation writes prob_*): run-level results — MC aggregates + quantiles, model probability grids, Bayes posterior sets. On-demand (reads never precompute, REQ-11): bounded single-subject reads served from stored active `prob_*` or stored `stat_*` rows; missing snapshot → `SNAPSHOT_NOT_FOUND` 404. Generation never triggers during import; reads never trigger generation (STE-12/FES-09 parity).

### D5 — F3/F4 consumption via own Protocols
`probability/providers.py` defines its own `DrawReader` (Core draws worldview: `ORDER BY draw_number, id` keyset), `StatSnapshotReader` (active stat identity + `read_frequencies/gaps/positions/scalars`), `FeatureSnapshotReader` (optional). Adapt at the composition root over `statistics_service.read_*` / `feature_engine_service.read_*` — NEVER F3/F4/marc internals; mirrored FES-06 (F4's `StatisticsProvider` exposes only scalars — no freq read; extending an archived spec is rejected). Missing data → skipped/absence, never guessed (STE-09).

### D6 — Slice 1 scope: roadmap 6 in ONE `core` bundle
All six — Hipergeométrica, Binomial, Poisson, Empírica, Monte Carlo, Bayes — together, matching how F3 shipped `CORE_METRICS` and F4 shipped FE-01..10 as one declared surface, one migration, one engine version. Conditional = univariate historical-window only; pairwise joint conditionals declared-but-not-computed (F6-bound). Deferred: CI as standalone, histograms, feature-sourcing, `analytics/` composition.

## 4. Documentary Contradictions

| # | Contradiction | Type | Precedence | Resolution |
|---|---|---|---|---|
| C1 | Method lists: Roadmap6 vs ENGINE_SPECS5 vs README7 vs API4 | contractual | Roadmap+LOTTERY_THEORY | Adopt roadmap 6; deviations noted, API doc not preserved verbatim |
| C2 | API_SPEC probability GETs vs snapshot contract | contractual | F3/F4 implemented OpenSpec + live API | Superseded: POST `/probability/generate` + GET reads (same as F3/F4 override) |
| C3 | Roadmap lists entropy "pending" | cosmetic | live code (`CORE_METRICS` incl. entropy) | already shipped in F3 core; no design impact |
| C4 | F4 spec endnote "Probability (Fase 6)" | cosmetic | Roadmap | Probability IS Fase 5; endnote mislabel |
| C5 | PROJECT_STATUS/README stale | cosmetic | HEAD af69abb (archived F4) | refresh as doc choresynchronized during change/archive |
| C6 | `probability_snapshot`/`montecarlo_runs` draft names | contractual | live migrations 0005/0006 precedent + F4 D5 | follow `prob_*` pattern; draft names NOT a contract |
| C7 | FEATURE_ENGINEERING §12 probability features vs README engine features | contractual | both | F5 owns probability values; feature-sourcing belongs to F4/F7 (future-statistics-type) |

Precedence hierarchy: Roadmap + LOTTERY_THEORY (method semantics) > implemented OpenSpec specs + live code/schema (contracts) > API_SPEC/DATABASE_SCHEMA/FEATURE_ENGINEERING (aspirational docs).

## 5. Architecture Proposal

| Component | Role (mirrors F3/F4) |
|---|---|
| `probability/generator.py` | `PROB_GENERATOR_VERSION`, model registry (6 models, params, versions), scopes |
| `probability/models/` | Pure functions: exact comb (fractions), empirical rates, univariate conditional, Bayes-fold, MC sampler (`random.Random`) |
| `probability/engine.py` | Deterministic orchestration + input fingerprint (canonical SHA-256) — no DB, no concrete imports |
| `probability/providers.py` | Protocols + composition-root adapters over service seams |
| `services/probability_service.py` | idempotent generate, atomic persist/retire/failed mark |
| `prob_snapshots` migration | plus payload `prob_values` alone-DB rollback |
| CLI + API | `lip probability generate|rebuild`, `POST /probability/generate`, GETs from snapshot |

## 6. Dependencies

| Dep | State | Consumed for |
|---|---|---|
| F1 Core draws/rules | ✅ | exact/conditional empiric; determinism precedent |
| F3 `stat_*` core bundle | ✅ | empirical rates; check by-active snapshot; `entropy` scalar |
| F3 second tier | ❌ absent | not required — declared subset only (no distributions/trends/corr) |
| F4 `feature_*` | ✅ (optional) | feature-provider identity; no requirement-core |
| Live DB | ⚠️ EMPTY | fixture-only validation; no real data in code |
| New numeric deps | ❌ none | stdlib `random`/`Decimal`; no numpy/scipy |

## 7. Contracts with F3/F4

- Statistics (reads only): active `stat_snapshot` (`checksum`, `generator_version`, `draws_from/to`) + `read_frequencies/read_gaps/read_averages` via `StatSnapshotReader` adapter over `statistics_service` — never repositories internals.
- Feature (optional): active `feature_snapshot` identity + `read_features` when present; absent → skip.
- Core draws: own `ProbSource` wrapping the deterministic keyset iterator (F4 `_SessionDrawProvider` pattern).
- Assurance: probability package never imports `backend.app.statistics.*`/`backend.app.feature_engineering.*` concrete modules (FES-02/06 parity).

## 8. Determinism Strategy

| Method | Determinism guarantee |
|---|---|
| Exact (hypergeom/binom/Poisson) | deterministic by definition; int/frac/Decimal arithmetic, canonical JSON |
| Empirical | same `stat_*` snapshot ⇒ identical values (reads ordered by key) |
| Monte Carlo | fixed-seed `random.Random(seed)`; seed = canonical SHA-256 {fingerprint, params, n_simulations, version}; rerun ⇒ byte-identical run + checksum; floats never persisted |
| Bayes | same declared priors + frozen inputs ⇒ same posterior (pure fold) |

## 9. Persistence Strategy

`prob_snapshots(lottery_id, model_set="core", version, prob_generator_version, checksum, input_fingerprint, status, is_locked, draw_count, draws_from, draws_to, params_json)` + `prob_values(snapshot_id, model_id, model_version, subject, draw_number|NULL, value)`. Idempotent generate via `find_by_fingerprint`; `full` always bump; atomic commit same-tx retire; `failed` dead header on error (never active/partial). MC persists aggregates + empirical quantiles only — not per-simulation histories. Migration `0007` down drops only `prob_*` (rollback plan: re-run `alembic upgrade head` regenerates; no migration destructive of Core/stat/feature).

## 10. Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| MC determinism regression (novel seed logic) | High | golden fixtures per seed; rerun-checksum test; seed policy unit tests |
| Empty live DB blocks verification | High | import-pipeline fixture CSVs; 0-draw case handled; no code data dependency |
| Empirical surface depends on F3 second tier (absent) | Med | restricted to active core statistics — declared then skipped |
| Large-n combinatorics without scipy | Med | python `int` exactness + Decimal; streamed; MC huge only via parameter |
| Float leakage into checksums | Med | no float latest in fingerprints; pure Decimal/int units |
| Conditional joint data absent | Med | windowed univariate only; pairwise deferred to F6 |

## 11. Success Criteria

- [ ] Migration `0007` upgrade/downgrade non-destructive; only `prob_*` dropped.
- [ ] Fixture import → generate → snapshot contains all 6 models; rerun produces byte-identical checksum + fingerprint (determinism gate).
- [ ] MC: same params/version ⇒ identical bytes; n or version change ⇒ different seed/result; float never persisted.
- [ ] Empirical/Conditional/Bayes values match hand-computed fixture expectations (known lottery sizes).
- [ ] Reads serve from stored snapshots; missing snapshot → 404 `SNAPSHOT_NOT_FOUND`; generation never fires on read.
- [ ] Strict read-only: Core/`stat_*`/`feature_*` byte-identical before/after a probability run (no writes outside `prob_*`).
- [ ] CLI/API parity; `backend/.venv/bin/pytest` + `ruff` green; 0-draw fixture handled gracefully.

## 12. Governance Boundaries

F5 computes probabilities only of MCMC events — never "prediction" (F7), never ML/DL (F7/F8), never combination generation (F9/F13), never betting/threshold advice. It does not modify Core, Statistics, or Feature Engine; writes confined to `prob_*`. No scheduler, no import hooks, no broker/trading logic, no new dependencies.

## 13. Traceability

- `IMPLEMENTATION_ROADMAP.md` Fase 5 (lines 176–181) — canonical 6 methods
- `LOTTERY_THEORY.md` LT-017..022 — same 6 theories
- `ENGINE_SPECIFICATIONS.md` §6 — engine responsibility ("Calcular modelos probabilísticos")
- `openspec/specs/statistics-engine/spec.md` STE-01..13, `feature-engine/spec.md` FES-01..10, `backend/spec.md` REQ-01, 10–12
- `openspec/changes/archive/2026-08-07-fase-3-statistics/{design,verify-report}.md`, `2026-08-07-fase-4-feature-engine/{exploration,proposal,design}.md` — F3/F4 contract precedents incl. rejected D5
- Live code: `statistics/{generator,engine,checksum}.py`, `services/{statistics_service,feature_engine_service}.py`, `feature_engineering/{engine,providers,fingerprint,registry.py}`, `app/probability/__init__.py`, `app/analytics/__init__.py`