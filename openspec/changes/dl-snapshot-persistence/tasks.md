# Tasks: DL Snapshot Persistence

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High

Strict TDD (`openspec/config.yaml`: `tdd: true`) — every `[TDD-RED]` precedes its `[TDD-GREEN]`.

| Unit | Goal | PR | Focused test command | Runtime harness | Rollback boundary |
|------|------|----|----------------------|-----------------|-------------------|
| 1 | Engine cut threading | 1 | `.venv/bin/pytest tests/dl/test_engine.py -q` | GF-1 determinism e2e (task 1.5) | Revert engine/objective edits |
| 2 | DlSnapshotStore | 2 | `.venv/bin/pytest tests/dl/test_snapshot_store.py -q` | N/A — prod-mirror SQLite fixture unit | Delete store + tests |
| 3 | DlService atomic flow | 3 | `.venv/bin/pytest tests/dl/test_service.py -q` | N/A — unit level; real smoke is Unit 5 | Delete service + tests |
| 4 | CLI + API surfaces | 4 | `.venv/bin/pytest tests/test_dl_cli.py tests/test_dl_api.py -q` | N/A — TestClient/CLI runner; real smoke Unit 5 | Revert cli.py; delete api/v1/dl.py + mount + tests |
| 5 | Cleanup + sweep | 5 | Full suite + ruff (6.2) | `lip dl train --lottery baloto` on real DB | Revert comment fixes |

## Phase 1: Engine Conformance Fix (cut threading + fingerprint kw)

- [x] 1.1 [TDD-RED] Extend `backend/tests/dl/test_engine.py`: every `train(...)` call gains `cut=`; new tests — same inputs + different `cut` ⇒ different fingerprint; `TrainResult.cut` equals declared value. Red: unexpected kwarg.
- [x] 1.2 [TDD-RED] Update `backend/tests/dl/test_dl_determinism_e2e.py` `_run_training`: pass fixed `cut=`; GF-1 byte-identical assertion unchanged.
- [x] 1.3 [TDD-GREEN] `backend/src/backend/app/dl/engine.py`: `train(..., *, cut: int, fingerprint: str | None = None)` — thread real cut into `compute_dl_fingerprint` (replaces hardcoded `cut=0`); expose `TrainResult.cut`.
- [x] 1.4 [TDD-GREEN] `opt/objective.py` `evaluate`: pass `cut=int(params.get("cut", 0))`; opt suite green.
- [x] 1.5 Regression: `.venv/bin/pytest tests/dl tests/bt -q` — proves `backtesting` (imports `predict`, not `train`) unaffected.

## Phase 2: DlSnapshotStore

- [x] 2.1 [TDD-RED] Create `backend/tests/dl/test_snapshot_store.py` CRUD: newest-active `get_active`, active-only `find_by_fingerprint`, `next_version` `"1"` first then max+1, metrics filter by `model_id`. Red: missing module.
- [x] 2.2 [TDD-RED] Failure/idempotency tests: >16 MiB weights `ValueError` before add; Decimal bulk metrics; `retire_old_active(keep_id)` flips old actives AND deletes their weight rows in-tx; post-rollback `mark_failed` re-inserts terminal failed header, `is_locked=False` (recreate-pattern gotcha).
- [x] 2.3 [TDD-GREEN] Create `backend/src/backend/app/dl/snapshot_store.py` mirroring `ml/snapshot_store.py` method-for-method — flush-only, never commit/rollback; caller owns the single commit.

## Phase 3: DlService Atomic Train Flow

- [x] 3.1 [TDD-RED] Create `backend/tests/dl/test_service.py` success-tx: exactly-one-active per `(lottery_id, model_set)`; 2 weight rows (`format_version=1`, run-fp); one aggregate metric row per family×name (`number=0`, Decimal); filled header; sorted `params_json`.
- [x] 3.2 [TDD-RED] Forced failure: rollback → recreate-`mark_failed` → commit leaves ONLY terminal failed header; outcome carries `snapshot_id`+`error`; no active/partial.
- [x] 3.3 [TDD-RED] Idempotent rerun: fingerprint hit returns existing metadata, zero writes, no duplicate version/weights.
- [x] 3.4 [TDD-RED] No active F4 snapshot ⇒ failed outcome before any header write.
- [x] 3.5 [TDD-GREEN] Create `services/dl_service.py`: `(session, draw_reader, feature_provider)`; frame → windows(W) → split(`real_cut = cut or len(frame)*4//5`) → tensors via providers; run fp = f(data_hash, params, "core-3", seed, W, real_cut); reuse branch; placeholder → train mlp→lstm → fill header → metrics → weights → `retire_old_active(keep_id)` → single commit; lazy `dl.engine` import (DLE-17 torch ban).
- [x] 3.6 [TDD-GREEN] `_DL_CACHE = ThreadSafeLRU(256)` + register; key `("dl:metrics", snapshot.id, model_id)`; response-cache suite green.

## Phase 4: CLI Surface `lip dl`

- [x] 4.1 [TDD-RED] Create `backend/tests/test_dl_cli.py`: train/models/metrics plain-JSON output (`{family,status,snapshot_id,fingerprint,metrics_checksum,error}`); unknown lottery errors; window outside 2..20 rejected.
- [x] 4.2 [TDD-GREEN] `cli.py`: `dl` argparse group after ml block; `_cmd_dl_*` handlers — deferred imports, `SessionLocal()`, `_resolve_lottery`, adapter conversion at handler, `print(json.dumps(...))`.

## Phase 5: API Router `/dl`

- [x] 5.1 [TDD-RED] Create `backend/tests/test_dl_api.py`: POST /dl/train SuccessEnvelope shape + invalid-lottery 404; GET /dl/models 404 `SNAPSHOT_NOT_FOUND`; GET /dl/metrics ETag ⇒ 304 empty body; no `/dl/predict` route.
- [x] 5.2 [TDD-GREEN] Create `api/v1/dl.py`: three routes; `_resolve_lottery`+`NotFoundError`; `SnapshotNotFoundError`; `etag_for`/`should_not_modify`; per-request adapters; reads never train (DLE-14).
- [x] 5.3 [TDD-GREEN] Mount in `api/v1/router.py` beside `ml_router`.

## Phase 6: Cleanup Rides & Regression Sweep

- [x] 6.1 Comment fix D-A7→D-A8 in `models/dl_metric.py:6`, `dl/determinism.py:48`; grep clean, ruff green.
- [x] 6.2 Sweep: `pytest backend/tests -q`; `ruff check .`; `ruff format --check .` — meta/exp suites prove consumer contracts intact.
- [x] 6.3 Real-data smoke: `lip dl train --lottery baloto` persists one active + 2 weights + Decimal metrics in one tx; meta/exp read persisted rows; rerun returns same `snapshot_id`; record evidence for verify-report.

## Review Workload Forecast

Estimated changed lines: **~830 total** — engine fix ~30 (+2 objective), store ~120, service ~150, CLI ~90, API ~80 (+3 router), tests ~350 (engine ~45, e2e ~5, store ~90, service ~100, CLI ~55, API ~70), cleanup ~4 (per design.md).

Exceeds 400-line budget: **yes** (~2x). Chained PRs recommended: **yes** — five units above (PR1 engine → PR2 store → PR3 service → PR4 surfaces → PR5 sweep), each independently verifiable/revertible. Decision needed before apply: **yes** — strategy `ask-on-risk`; user must pick chain strategy before `sdd-apply`.

Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: pending
400-line budget risk: High
