# Design: Feature Engine (Fase 4) — Core-Domain First Slice

**Change**: `fase-4-feature-engine` · **Store**: `openspec` · **Date**: 2026-08-07
**Artifact**: design · **Predecessors**: exploration, proposal.

## 1. Technical Approach

An independent, deterministic, provider-driven feature engine. It mirrors the Fase 3 contract: immutable `feature_snapshots` header + normalized `feature_values` payload, canonical SHA-256 fingerprint, `active/retired/failed` lifecycle, `draw_number` axis (STE-03), manual generation only. The engine depends **only** on provider protocols (`DrawProvider`, `StatisticsProvider`, `DatasetProvider`) and writes **only** to `feature_*`. First slice computes ~8–10 Core-Domain base features (draw identity, per-draw distribution, tens buckets, current-frequency/gap); `future-statistics` and stats-sourced features are **declared but never computed**.

```
FeatureRegistry ──topo order──▶ engine.execute() ──▶ pure features ──▶ feature_values
      ▲                                │                ▲
      │ (cycle detect)                 ▼                │ providers (Protocol only)
 FeatureDefinitions            fingerprint.checksum     DrawProvider / StatisticsProvider
```

## 2. Data Model — `feature_snapshots` + `feature_values`

Mirrors `stat_*` (design §2): portable DDL only; PK, FK RESTRICT, UNIQUE, CHECK; timestamps `DateTime(timezone=True)`. Immutability enforced by the service (`is_locked`, no dialect triggers).

### `feature_snapshots` (header)

| Column | Type/Null | Reason |
|--------|-----------|--------|
| `id` | int PK | surrogate |
| `lottery_id` | int NOT NULL FK→`lottery.id` RESTRICT | per-lottery scoping (STE-11 parity) |
| `feature_set` | str(32) NOT NULL | feature bundle id, e.g. `core` |
| `version` | str(32) NOT NULL | human monotonic version per (lottery, feature_set) |
| `feature_engine_version` | str(32) NOT NULL | this engine's algorithm identity (independent of `STATS_GENERATOR_VERSION`) |
| `checksum` | str(64) NOT NULL | canonical SHA-256 of the full feature-set output content |
| `input_fingerprint` | str(64) NOT NULL | canonical SHA-256 of the *inputs* (draws + feature defs + optional stats identity); the invalidation key |
| `status` | str(16) NOT NULL | `active|retired|failed`, CHECK |
| `is_locked` | bool NOT NULL | immutable after commit |
| `draw_count`,`draws_from`,`draws_to` | int NOT NULL | folded range (FC-03 axis); `draws_from<=draws_to` CHECK |
| `created_at`,`updated_at` | DateTime(tz) | audit |

UNIQUE `(lottery_id, feature_set, version)`; exactly one `active` per `(lottery, feature_set)` enforced by service.

### `feature_values` (normalized payload)

| Column | Type/Null | Reason |
|--------|-----------|--------|
| `snapshot_id` | int NOT NULL FK RESTRICT → `feature_snapshots.id` | branch of this snapshot's features |
| `feature_id` | str(64) NOT NULL | stable feature slug (registry key), e.g. `sum_of_numbers` |
| `feature_version` | str(32) NOT NULL | this feature's own version (see §6 Q1) |
| `draw_number` | int NULL | axis of the value; NULL for per-lottery scalars (PK allows), FK-ish by value (matches Statistics: no hard FK to `draw`) |
| `value` | Numeric(20,8) NOT NULL | exact Decimal; deterministic accumulation |
| PK | `(snapshot_id, feature_id, draw_number)` | normalized, indexed lookups; one feature per draw |

Decision: **normalized tabular over JSON blob** — same rationale as `stat_*` (SQL-searchable/indexable, byte-stable checksum, portable). D5 (DATABASE_SCHEMA's `feature_value(draw_id, value)` old model) is **rejected**: it lacks snapshot/versioning/checksum and has no `draw_number` axis — the snapshot layering Statistics proved is required for determinism and incremental rebuild.

## 3. Indexes — each justified

| Index | On | Access path served |
|-------|----|--------------------|
| `ix_fsnap_lottery_set_status` (NEW) | `feature_snapshots(lottery_id, feature_set, status)` | active-resolution on generate + every read (mirrors `stat_snapshots`) |
| `ix_fval_snapshot_id` (NEW) | `feature_values(snapshot_id)` | join active snapshot → values in reads / rebuild validation |
| `ix_fval_feature_draw` (NEW) | `feature_values(feature_id, draw_number)` | per-feature series read on the `draw_number` axis (ML consumers pull one feature's whole series) |
| existing `draw`/`draw_numbers` | Core | reused for the deterministic keyset provider read — **no new core column** (Option A, Statistics §4). |

Why-new rationale: every feature read joins by active snapshot then filters by feature_id/series; none of these paths are served by existing indexes. A potential `(lottery_id, number)` denormalization on `draw_numbers` is REJECTED now and documented as a future candidate only if EXPLAIN proves degradation.

## 4. Provider Contracts (only data seam; no statistics import)

```python
class DrawProvider(Protocol):
    def iter_draws(self, lottery_id, *, after_draw_number=None) -> Iterator[DrawRow]: ...
    def lottery_rules(self, lottery_id) -> LotteryRules: ...
class StatisticsProvider(Protocol):
    def active_snapshot(self, lottery_id, metric_set="core") -> StatsSnapshot | None: ...
    def scalars(self, snapshot_id) -> Mapping[str, Decimal]: ...   # entropy etc., read-only
class DatasetProvider(Protocol):   # future seam; declared, not exercised in slice 1
    def active_dataset(self, lottery_id) -> DatasetHeader | None: ...
```
Adapters live at the composition root, wrapping `StatPayloadRepository`/`draw_repository` services. The engine imports only these protocols — **never** `statistics/`, `models/`, or repositories (no circular dependency; satisfied by inversion, mirrors Statistics' `api→service→repository+statistics→models` DAG).

## 5. Determinism Contract

- Mandatory `ORDER BY draw.draw_number, draw_numbers.id` on every read/pass. Never physical scan order.
- INTEGER/`Decimal`-exact accumulators; **float never enters a checksum or persisted value**.
- Canonical serialization `json.dumps(sort_keys=True, separators=(",", ":"))` (reuse `stat_checksum` pattern).
- Input fingerprint `fingerprint.py`:
```python
fingerprint = sha256(canonical_json({
    "draws": {"lottery": id, "from": a, "to": b, "checksum": draw_set_checksum},
    "features": [(f.id, f.feature_version, f.params) ...sorted...],
    "stats": {"checksum": ..., "generator_version": ..., "from": .., "to": ..} | None,
}))
```
`checksum` (outputs) and `input_fingerprint` (inputs) are distinct; equality of the latter is how a snapshot is invalidated when a dependency changes (Q2).

## 6. Registry — versions & cycles

`FeatureDefinition` frozen dataclass: `{id, name, category, description, source("core|statistics|future-statistics|meta"), inputs, algorithm, params, dependencies: tuple, complexity, version, status, history}`. Per-feature module under `features/<id>.py` exposing pure `compute(ctx)`. On load:
- build directed graph `feature → dependencies`;
- run **Kahn topological sort**: if not all nodes emitted, a cycle exists in the remaining set → registration **fails-fast**, offending features reported, none registered.
- enabled features run in topo order; a feature whose dependency is `future`/`disabled`/`failed` → `skipped` (never guessed).
- `source=="future-statistics"` → registered, versioned, documented, **never scheduled**.

## Approval — 8 required answers (traceability)

1. **Individual feature versioning** — `feature_values.feature_version`, bumped only when that feature's algorithm/params/meaning change; never on Statistics bump. (Def in §2/FeatureDefinition.version.)
2. **Snapshot invalidation on dependency change** — recompute when `input_fingerprint` differs from the stored one, compared on (draws checksum, feature versions/params, stats snapshot identity). A stats-content bump changes inputs → a NEW version, old→`retired`; feature versions themselves do NOT bump.
3. **Fingerprint contents** — full enumeration above in §Fingerprint: draws `{lottery, from, to, checksum}` + sorted `[(feature_id, feature_version, params)]` + optional stats `{checksum, generator_version, from, to}`; canonical compact JSON, SHA-256. Drawn as draw-set includes the same fidelity proof.
4. **DAG cycle detection** — Kahn topo sort at registry load; presence of an unresolved strongly-connected residual ↦ fail-fast with reported set (§Registry). DFS alternative rejected (Kahn gives both order and residual set in one pass).
5. **Provider contract** — §Provider Contracts above: `DrawProvider` (keyset read-only), `StatisticsProvider` (passive active-snapshot reads), `DatasetProvider` (declared); no engine→Statistics import, no precompute (STE-10).
6. **Full vs incremental** — full rebuild: recompute all features for all draws into a NEW version (never mutate locked). Incremental: `delta = draws > snapshot.draws_to`; fold delta into a new snapshot (windowed current/tail features recompute only over their bounded window); mirror STE-06. Both always new `version`, old→`retired`.

> **Slice 1 implementation limitation (maintainer-approved, 2026-08-07)**: the current `incremental` implementation recomputes over the complete draw set (windowed/tail features need the full series for a deterministic checksum). This is an **implementation limitation of Fase 4 Slice 1**, NOT a redefinition of the contract: the delta/fold semantics above remain the design's definition of incremental. The seam stays prepared for a later true fold; do not let the slice-1 shortcut become the definitive Feature Engine contract. `full` → new version ✓; `incremental` → may recompute the needed set ✓; declaring this equals a true incremental fold is ✗.
7. **Migration 0006 rollback** — downgrade drops `feature_values`, `feature_snapshots`, and the three `ix_*` indexes; never touches Core/`stat_*`. Additive, clean, non-destructive.
8. **New indexes & why** — §Indexes: active resolution + FK joins + per-feature `draw_number` series reads; justified by the concrete queries they serve; no core denormalization.

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `backend/src/backend/app/feature_engineering/{registry,providers,engine,fingerprint}.py` | Create | pure seams; no DB |
| `backend/src/backend/app/feature_engineering/features/*.py` | Create | ~8–10 Core-Domain feature modules |
| `backend/src/backend/app/models/feature_snapshot.py`, `feature_value.py` | Create | ORM models |
| `backend/src/backend/app/repositories/feature_snapshot_repository.py`, `feature_value_repository.py` | Create | header + batched payload persistence |
| `backend/src/backend/app/services/feature_engine_service.py` | Create | orchestration, single atomic tx |
| `backend/alembic/versions/0006_feature_tables.py` | Create | migration |
| `backend/src/backend/app/feature_engineering/__init__.py` | Modify | keep seam docstring |
| `backend/src/backend/app/services/errors.py`, `app/api/errors.py` | Modify | feature domain error taxonomy |
| `app/cli.py` | Modify | `lip feature-engine generate` subcommand (mirrors `statistics`) |

## Migration / Rollout

Additive `0006_feature_tables.py` only (`down_revision = "0005_stat_tables"`). New `feature_*` tables + three indexes. Empty until manual generate; no scheduler. Onboard strategy risk-free (writes confined to `feature_*`, core untouched). No feature flag required.

## Testing Strategy

| Unit | registry cycle-detection + topo order; per-feature pure compute deterministic; fingerprint canonical |
| Integration | generate→snapshot→read on tmp migrated DB; incremental (delta) matches full-rebuild checksums |
| E2E | CLI generate/rebuild; determinism rerun ⇒ identical checksums; migration 0006 up/down (drops only `feature_*`); stats-sourced/future features declared but not computed |

## Threat Matrix

Not applicable — this introduces no routing, shell-command, subprocess, VCS/PR automation, executable-classification, or process-integration boundary. CLI is argparse-only (mirrors `lip`), never shells out.

## Open Questions

- [ ] Exact set/slugs of the 8–10 base features to pin the generator `FEATURE_GENERATOR_VERSION`.
- [ ] Confirm `feature_values` FK-to-`draw` stays omitted (stat_* parity: draw_number axis only), per exploration recommendation.