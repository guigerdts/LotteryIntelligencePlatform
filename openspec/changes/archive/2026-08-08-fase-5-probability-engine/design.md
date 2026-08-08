# Design: Fase 5 — Probability Engine

## Technical Approach

Independent, deterministic, result-only engine (PES-1..11, PM-1..7) mirroring the F3/F4 snapshot contract: `prob_snapshots` header + `prob_values` payload, `PROB_GENERATOR_VERSION`, canonical SHA-256 input fingerprint, immutable `active|retired|failed` lifecycle, manual-only generation, multi-lottery. Pure int/Decimal math; float never enters a checksum or persisted value (PES-5). Reads Core/`stat_*`/`feature_*` ONLY via own Provider Protocols (PES-6); writes ONLY `prob_*` (PES-1/2). Novelty: deterministic Monte Carlo via isolated `random.Random(seed)` inside the rerun gate (D2/PES-5).

## Decisions

| ID | Choice | Rejected |
|---|---|---|
| D-A1 | `probability/` package + service + repos + API, parallel to F4 | — |
| D-A2 | dict-dispatch `registry.py` (methods independent) | Kahn DAG (F4-style) |
| D-A3 | `snapshot_store.py` consolidates F4's two repos (single `prob_*` I/O owner) | — |
| D-A4 | surrogate `id` PK; `draw_number NULL` grid rows | composite PK (impossible with NULL axis, PES-3) |
| D-A5 | empty DB → header `draws_from=0..draws_to=0`; fixture tests | — (PES-11) |
| D-A6 | MC persists aggregates + p50/p90/p99 only | raw simulation history (PES-1) |
| D-A7 | stdlib only (`math.comb`, `Decimal`, `random`) | scipy/numpy (constraint 10) |

Also rejected: extending F4's `StatisticsProvider` (PES-6), reusing `datasets` (F4 D5 precedent), global `random`/OS entropy (PES-5).

## Module Layout (`backend/src/backend/app/probability/`)

| File | Responsibility | Traces |
|---|---|---|
| `__init__.py` | Keep F0 seam docstring | — |
| `engine.py` | Pure math: 7 model functions; no DB, no concrete imports | PES-5/6, PM-1..7 |
| `providers.py` | `DrawReader`, `StatSnapshotReader`, `FeatureSnapshotReader` Protocols + carries (`DrawRow`, `LotteryRules`) | PES-6 |
| `registry.py` | `MethodDefinition` (id/version/params) + dict dispatch | PM-1..7 |
| `fingerprint.py` | Canonical JSON (`sort_keys,separators=(",",":")`) → SHA-256 input fingerprint | PES-5 |
| `determinism.py` | Seed derivation; isolated PRNG policy | PES-5, D2 |
| `schemas.py` | Pydantic v2, mirror `schemas/statistics.py` | PES-8 |
| `snapshot_store.py` | `prob_*` read/write: active, find-by-fingerprint, next-version, ordered bulk insert, retire/failed | PES-7 |

## Data Model (`models/prob_snapshot.py`, `prob_value.py`)

`prob_snapshots`: `id PK · lottery_id FK RESTRICT · model_set String(16)="core" · version · prob_generator_version · checksum String(64) · input_fingerprint String(64) · status CHECK IN (active,retired,failed) · is_locked · draw_count · draws_from · draws_to · created_at · updated_at · Unique(lottery_id, model_set, version)`.

`prob_values`: `id PK · snapshot_id FK RESTRICT · model_id String(64) · model_version String(32) · subject String(64) · draw_number int NULL (no FK to draw, PES-3) · value Numeric(20,8) · params_json (frozen params incl. MC quantile labels) · Unique(snapshot_id, model_id, model_version, subject, draw_number)`.

## Migration

`alembic/versions/0007_probability_tables.py`, `down_revision="0006_feature_tables"`; downgrade drops ONLY `prob_*` (PES-9). Indexes (PES-09 names): `ix_psnap_lottery_model_status (lottery_id, model_set, status)` — active-header resolution; `ix_pval_snapshot_id (snapshot_id)` — payload reads; `ix_pval_subject (subject)` — per-subject/quantile rows.

## Seed / Determinism (`determinism.py`, PES-5/D2)

```python
seed = int(sha256(canonical_json({
  "input_fingerprint": f, "model_params": p, "n_simulations": n,
  "PROB_GENERATOR_VERSION": VER}).encode()).hexdigest()[:16], 16)
rng = random.Random(seed)   # isolated — never global random; no OS entropy
```
`n_simulations` is a versioned parameter inside fingerprint+seed: change ⇒ new deterministic run; old snapshot untouched (PES-4). MC accumulates integer counts only; values = `Decimal(count)/n` quantized once; quantiles from sorted integer aggregates; floats never persisted (PES-5).

## Providers (`providers.py`, PES-6)

```python
class DrawReader(Protocol):
    def iter_draws(self, lottery_id, after_draw_number=None) -> Iterator[DrawRow]: ...
    def lottery_rules(self, lottery_id) -> LotteryRules: ...
class StatSnapshotReader(Protocol):
    def active(self, lottery_id, metric_set="core") -> StatsRef | None: ...
    def frequencies(self, snapshot_id) -> Mapping[int, int]: ...
class FeatureSnapshotReader(Protocol):
    def active(self, lottery_id, feature_set="core") -> FeatureRef | None: ...
```
All reads `ORDER BY draw_number, id` (PES-3/5). Adapters at the service seam wrap `statistics_service.read_*`/`feature_engine_service.read_*` — never repo internals. Missing data → skipped/absent, never guessed (STE-09 parity).

## Engine API (`engine.py`)

| Method | Signature → output | Trace |
|---|---|---|
| hypergeometric | `hypergeometric(N, n, r) → [(k, Decimal)]`, N=max−min+1 | PM-1 |
| binomial | `binomial(n, p) → [(k, Decimal)]` | PM-2 |
| poisson | `poisson(λ, kmax) → [(k, Decimal)]` | PM-3 |
| empirical | `empirical(freq, total) → {num: Decimal}` | PM-4 |
| monte_carlo | `monte_carlo(rng, rules, params) → counts → quantiles p50/p90/p99` | PM-5 |
| bayes | `bayes(prior, like) → normalized prior×likelihood fold` | PM-6 |
| conditional | `conditional(window_counts, window_size) → count/window, univariate only` | PM-7 |

All Integer/Decimal; exact combinatorics via `math.comb`.

## Snapshot Store & Service

`services/probability_service.py` orchestrates: `generate(lottery_id, model_set, scope)` → adapters → engine.execute → fingerprint → store.persist(header+values, same-tx retire old) (PES-7); on error → `mark_failed` dead header, never active/partial. `read(model, subject)` → active snapshot → rows; none → 404 `SNAPSHOT_NOT_FOUND`; never precomputes (PES-8). Idempotent: identical fingerprint+version returns existing active (incremental); `full` always bumps (PES-4). Empty draws → `draws_from=0,draws_to=0` (PES-11).

## API Routes (`api/v1/probability.py`)

| Route | In | Out |
|---|---|---|
| `POST /probability/generate` | `{lottery_code, model_set="core", scope}` | 200/201 `GenerateSnapshot` |
| `GET /probability/{code}/probabilities` | `model`, `subject`, `last` | `ProbabilityList` |
| `GET /probability/{code}/probabilities/{model}` | — | model grid |

Missing snapshot → 404 `SNAPSHOT_NOT_FOUND`; reads never precompute (PES-8); envelope + error taxonomy reused.

## CLI (`cli.py`)

`lip probability generate --code X [--scope]` / `lip probability rebuild --code X` — mirror `lip statistics|feature-engine …`.

## Traceability Matrix

| Req | Seam |
|---|---|
| PES-1 | models + migration 0007; MC aggregates only |
| PES-2 | Providers only; writes confined to `prob_*` |
| PES-3 | `ProbValue.draw_number` logical, no FK; ordered joins |
| PES-4 | `PROB_GENERATOR_VERSION`+`model_version`; new version, never in-place |
| PES-5 | fingerprint + determinism + Decimal/int; `ORDER BY` everywhere |
| PES-6 | providers.py Protocols; service-seam adapters |
| PES-7 | snapshot_store active/retired/failed; is_locked; same-tx retire |
| PES-8 | CLI/API manual; GET reads stored; 404 |
| PES-9 | migration 0007 downgrade → only `prob_*` |
| PES-10 | per-lottery FK + own rules via DrawReader |
| PES-11 | draws_0 header; fixtures; no crash |
| PM-1..7 | engine.py functions |

## Testing Strategy

| Layer | Covers |
|---|---|
| Unit | each PM vs hand-computed fixtures; exact int combinatorics; MC seed rerun equality |
| Unit (determinism) | seed formula; fingerprint+checksum byte-identical twice; `n_simulations` change → new seed, still deterministic |
| Integration | migration 0007 up/down; lifecycle active→retired, failure→failed; read-only gate (Core/stat/feature byte-identical) |
| E2E | fixture CSV → import → generate → GET reads; API/CLI parity; 404; empty-DB acceptance |

## Threat Matrix

N/A — all additions are existing argparse/FastAPI surfaces; no subprocess, shell, VCS, PR-automation, executable-classification, or process-integration boundary introduced.

## Migration / Rollout

0007 upgrade additive; downgrade drops only `prob_*`. No scheduler, no hooks, no feature flags (PES-8), no new deps (constraint 10). Chore C5: refresh `README.md` / `PROJECT_STATUS.md` for Fase 5.

## Open Questions

None — every element traces to PES-01..11 / PM-01..07 or closed D1–D6.

## File Changes

| Action | Path |
|---|---|
| Create | `probability/{__init__,engine,providers,registry,fingerprint,determinism,schemas,snapshot_store}.py` |
| Create | `models/prob_snapshot.py`, `models/prob_value.py`; register in `models/__init__.py` |
| Create | `services/probability_service.py` |
| Create | `api/v1/probability.py`; mount in `api/v1/router.py` |
| Create | `alembic/versions/0007_probability_tables.py` |
| Modify | `cli.py`; `README.md`; `PROJECT_STATUS.md` |
| None | `pyproject.toml` (no new deps) |