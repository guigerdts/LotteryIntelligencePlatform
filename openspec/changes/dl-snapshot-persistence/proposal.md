# Proposal: DL Snapshot Persistence (`dl-snapshot-persistence`)

## Intent

DL training works end-to-end in memory but nothing persists its output: `dl.engine.train()` returns a `TrainResult` that dies with the process, while `dl_snapshots`/`dl_metrics`/`dl_weights` (migration `0010`, alembic head `0016`) sit empty and three consumers (`meta/context.py`, `meta_service.py`, `exp_service.py`) already query them assuming the documented lifecycle. No writer exists anywhere in the application layer. This change delivers the persistence/service/surface layer already mandated by spec.

## Scope

### In Scope

- `dl/snapshot_store.py` — flush-only `DlSnapshotStore` mirroring `MlSnapshotStore`: `get_active`, `find_by_fingerprint(lottery_id, model_set, fingerprint)`, `next_version`, `create_snapshot`, `bulk_insert_metrics`, `insert_weights` (≤16 MiB pre-check), `delete_weights_for`, `retire_old_active(keep_id)`, `mark_failed`.
- `services/dl_service.py` — atomic tx per run: placeholder header (`active`, locked) → engine train → fill header in place → bulk metrics + one weight row per trained model (2 for core-3) → retire old active AND its weight rows → single commit. Failure path exactly ML's: `rollback()` → `mark_failed(id)` → `commit()`; only a terminal `failed` header persists (DLE-12).
- CLI group `lip dl {train,models,metrics}` in `cli.py` (ml precedent: deferred imports, `_resolve_lottery`, plain-JSON output).
- API router `api/v1/dl.py`: `POST /dl/train`, `GET /dl/models`, `GET /dl/metrics` (ETag/304 like ml), mounted in `api/v1/router.py`.
- Spec-mandated engine fix: thread real `cut` through `DlEngine.train()` into `compute_dl_fingerprint`; expose `cut` on `TrainResult`.
- Tests: store unit, service atomicity/idempotency/failure-terminal, surface E2E, cut-in-fingerprint regression (TDD per config).
- Doc cleanup: stale `D-A7` citations → `D-A8` (see Inconsistencies).

### Out of Scope (Non-goals)

- Schema migrations — INSERT-only writer; existing DDL verified column-for-column against ORM.
- Any ML-engine change; any `model_set` beyond `core-3`.
- Scheduler/auto-retrain; `/dl/predict`, ranking, or any weights-download/read surface (DLE-14 prohibition).

## Capabilities

> Contract for sdd-spec. Researched against `openspec/specs/`.

### New Capabilities

None.

### Modified Capabilities

None — this change implements existing requirements verbatim; no spec-level behavior changes. Verified coverage: `dl-engine` DLE-01/04/05/08/09/11/12/14/16 and `backend` REQ-10 (`POST /dl/train`), REQ-11 (`GET /dl/models|metrics` reads, 404 `SNAPSHOT_NOT_FOUND`), REQ-12 (`lip dl train|models|metrics`). sdd-spec should confirm zero deltas.

## Open Decisions — Positions Taken

| # | Decision | Position | Rationale |
|---|----------|----------|-----------|
| 1 | Cut-in-fingerprint fix | In scope | DLE-08 acceptance "changing `W` or `cut` changes the fingerprint" + DLE-05 declare-per-run mandate it; ML parity exists (`ml/engine.py:229` passes real cut). Persisting headers whose invalidation key ignores real `cut` would violate the merged spec. |
| 2 | Old weights on retire | DELETE old-active's `dl_weights` rows in-tx | Simplest spec-compliant reading of DLE-12 "(and its weights rows)"; header rows stay immutable/auditable; avoids a schema change (no status column). |
| 3 | Surface shape | Mirror ml exactly (REQ-12 names `lip dl train|models|metrics`); `--window` defaults 10, validated 2..20; `--cut` declared per run, defaulting to `len(frame)*4//5` walk-forward boundary when omitted | DLE-04 fixes W default/bounds; DLE-05 requires declaration but backend REQ-10 lists `cut` optional — M-A8 default is house precedent (`ml/engine.py:159`). |
| 4 | Idempotent rerun | Follow ML `find_by_fingerprint` precedent: return existing snapshot metadata in the same response shape as a fresh run (`{status, snapshot_id, fingerprint, metrics_checksum, error}`), no reuse flag | DLE-12 mandates fingerprint reuse without prescribing response shape; silent reuse is the established pattern. |
| 5 | Doc citations | Fix rides along | Two comment corrections, recorded below. |

## Approach

Replicate the proven ML pipeline: store owns I/O only (flush-only, caller owns the transaction); service owns one atomic tx per run; CLI and API each own thin adapters reusing `_CliDrawAdapter/_CliFeatureAdapter` carriers converted at the composition root (DLE-13). Weight rows bind `weights_fingerprint` = run fingerprint, `format_version=1`, size pre-checked before INSERT (DDL CHECK `ck_dl_weights_max_size` backstop), no pickle/joblib (DLE-09). Torch stays deferred-imported in the service (DLE-17). Response cache `ThreadSafeLRU(maxsize=256)` keyed like `("dl:metrics", snapshot.id, model_id?)`.

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `backend/src/backend/app/dl/snapshot_store.py` | New | dl_* I/O owner (flush-only) |
| `backend/src/backend/app/services/dl_service.py` | New | Atomic orchestration per run |
| `backend/src/backend/app/dl/engine.py` | Modified | Real `cut` threaded into fingerprint; `TrainResult.cut` |
| `backend/src/backend/app/cli.py` | Modified | `lip dl {train,models,metrics}` group |
| `backend/src/backend/app/api/v1/dl.py` (+ `router.py`) | New/Modified | DL routes registered |
| `backend/src/backend/app/models/dl_metric.py`, `dl/determinism.py` | Modified | Comment-only citation fix |
| `backend/tests/**` | New | Store/service/surface/engine-fix coverage |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Non-atomic window leaves two actives → meta/exp corruption (consumers assume exactly one active per `(lottery_id, model_set)`) | Med | Single-commit discipline; tests asserting exactly-one-active after success AND after failure |
| SQLite concurrent trains race version generation | Low | UNIQUE `(lottery_id, model_set, version)` converts loss into IntegrityError → terminal `failed` (acceptable outcome) |
| >16 MiB blob rejected mid-tx | Low | Size pre-checked before INSERT (LSTM ≈212 KB today); rejection lands on failed-terminal path regardless |
| Engine signature change breaks existing callers/tests/opt objective | Low | Blast radius verified bounded; callers updated with regression tests |

## Rollback Plan

Revert this change's commit(s): all writes are additive rows, so there is no data migration to undo and no schema change. Deep fallback mirrors DLE-16: downgrade `0010` drops ONLY `dl_*`; F1–F7 untouched.

## Dependencies

- F4 feature snapshots resolvable via DL provider protocols (DLE-13); ≥100 real draws floor (DLE-10).
- Alembic head `0016` with `dl_*` tables from `0010_dl_tables` — no new migration required.

## Inconsistencies Found (recorded per `rules.proposal`)

- `models/dl_metric.py:6` and `dl/determinism.py:48` cite design decision **D-A7** for the canonical metric set / Decimal quantization; fase-8 `design.md:21` defines **D-A8** as the metric set (`accuracy, precision, recall, f1, roc_auc`) while D-A7 (:20) is error mapping (`INSUFFICIENT_DATA` → 422). Comments corrected to D-A8 in scope.
- Index `ix_dweight_snapshot_model_id` exists in SQLite but not in ORM metadata — informational for design; no action in this change.

## Success Criteria

- [ ] Real-data `lip dl train` persists one active snapshot + 2 `dl_weights` rows + Decimal metrics in a single committed transaction.
- [ ] Identical rerun returns the existing snapshot by fingerprint — no duplicate version or weights row.
- [ ] Changing `W` or `cut` changes the persisted `input_fingerprint` (regression test proves the engine fix).
- [ ] Forced failure leaves ONLY a terminal `failed` header; `meta/context`, `meta_service` listing, and exp validation work against persisted rows.
- [ ] Reads answer from storage only (404 `SNAPSHOT_NOT_FOUND` otherwise); backend pytest suite + ruff green.
