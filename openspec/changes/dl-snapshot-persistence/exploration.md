# Exploration — dl-snapshot-persistence

## Summary

DL training works end-to-end in memory but nothing persists its results: `dl.engine.train()` returns a `TrainResult` (quantized Decimal metrics, fingerprint-bound `weights_blob`, W, seed) that dies when the process exits. The database schema is fully ready (`dl_snapshots`, `dl_metrics`, `dl_weights` created by migration `0010_dl_tables`; alembic head `0016`), ORM models exist, and three consumers already query these tables assuming the documented lifecycle — yet no writer exists anywhere in the application layer (no store, no service, no CLI command, no API route). A live walkthrough on real Baloto data proved the engine path (291+73 windows, MLP/LSTM byte-identical across runs), so the gap is strictly the persistence/service/surface layer.

## Evidence map

| Fact | Location | Note |
|---|---|---|
| Engine returns artifacts, memory only | `backend/src/backend/app/dl/engine.py:7-9,46-57` | "Persistence is service-layer responsibility" |
| No writer for DL tables | grep `DlSnapshot|DlMetric|DlWeight` over `backend/src` | Only `models/` definitions + re-exports |
| Tables exist, empty | live probe | `dl_snapshots=0 dl_metrics=0 dl_weights=0` |
| Migration created tables | `backend/alembic/versions/0010_dl_tables.py:18-19,111-113` | head = `0016_exp_comparisons_run_ids` |
| `MlSnapshotStore` flush-only | `backend/src/backend/app/ml/snapshot_store.py:23-141` | Store never commits; caller owns tx |
| ML atomic failure order | `backend/src/backend/app/services/ml_service.py:176-179` | `rollback() -> mark_failed(id) -> commit()` |
| DlWeight uninspected until now | `backend/src/backend/app/models/dl_weight.py:27-59` | blob LargeBinary ≤16 MiB CHECK; NO unique on (snapshot_id, model_id); DB has index `ix_dweight_snapshot_model_id` not declared in ORM |
| Weights envelope self-validating | `backend/src/backend/app/dl/weights.py:32-34,72-150,156-257` | magic `LIPDLW01`, fmt 1, sha256 trailer, optional expected_fingerprint |
| meta reads newest active DL snapshot | `backend/src/backend/app/meta/context.py:98-118` | fields: `draws_from, draws_to, cut, window`; none active → `ValueError` |
| exp validates by input_fingerprint | `backend/src/backend/app/services/exp_service.py:34-39,645-654` | `engine_type in ("ml","dl") -> snapshot.input_fingerprint` |
| meta_service lists all active + metrics | `backend/src/backend/app/services/meta_service.py:458-469` | model key `f"dl-{s.model_set}-{s.id}"` |
| exp reads DL metrics by name | `backend/src/backend/app/services/exp_service.py:513-527` | `_read_dl_metrics`: `float(row.value)`, duplicate names averaged |
| Fingerprint spec payload | `openspec/specs/dl-engine/spec.md:194-197` | includes **cut**; engine passes `cut=0` (`dl/engine.py:230-238`) |
| API already promises DL endpoints | `openspec/specs/backend/spec.md:136,162,188` | `POST /dl/train` idempotent, `GET /dl/models` |

## ML vs DL equivalence analysis

Transfers 1:1 (proven house pattern):
- Store class owning I/O only, **flush-only**, caller commits (`snapshot_store.py` style).
- Service atomic tx per run: create header `status="active", is_locked=True` with placeholder checksum/fingerprint → train → fill header in place → bulk insert metrics (+ weights rows for DL) → `retire_old_active(keep_id)` → single commit.
- Failure path exactly: `session.rollback()` → `mark_failed(snapshot_id)` → `commit()`; outcome carries `snapshot_id` + error.
- Versioning: `next_version` = max(version)+1 as string; UNIQUE `(lottery_id, model_set, version)` guards races at the DB level.
- Response cache: module-level `ThreadSafeLRU(maxsize=256)` + `register_cache`, keyed like `("dl:metrics", snapshot.id, model_id?)`.
- Surface duplication convention: CLI and API each own thin adapters; not shared.

Must differ / DL-specific:
1. **Weights persistence** (no ML counterpart): one `dl_weights` row per trained model (Fase-8 design D-A1: 2 models/run ⇒ 2 weight rows + 2×N metrics). Bind `weights_fingerprint` = run fingerprint; enforce ≤16 MiB before INSERT (CHECK `ck_dl_weights_max_size`); `format_version`=1 from encoder. No unique constraint on `(snapshot_id, model_id)` — dedup belongs at header idempotency level (DLE-12), not row level.
2. **Retire must also retire old weights**: DLE-12 explicitly retires "the old active (and its weights rows)" in the same transaction — ML has no analog. Implementation choice: mark old weight rows (needs status column — schema change) vs delete vs leave-orphaned-but-header-retired. Spec text says "(and its weights rows)" without naming a mechanism; simplest compliant reading: delete old-active's weight rows in-tx (header rows remain immutable/auditable), or keep rows since header retirement makes them unreachable. Decision needed at design.
3. **cut participates in fingerprint** (DLE-04/05/08) — ML parity exists (`ml/engine.py:229` passes real cut) but DL engine hardcodes `cut=0` ("not relevant at engine level"). Persisted header would then carry a real `cut` NOT covered by the invalidation key, violating the merged spec. Fix belongs in this change: thread real `cut` into `train()` and into `compute_dl_fingerprint`.
4. **Idempotency**: rerun whose `input_fingerprint` matches an existing snapshot SHALL return that snapshot (DLE-12) — ML has `find_by_fingerprint`; DL store needs the same.
5. Metric names canonical set `{accuracy, precision, recall, f1, roc_auc}` comes from design decision **D-A8** (`design.md:21`); code comments mis-cite "D-A7" (which is error-mapping 422 mapping, `design.md:20`). Minor doc correction opportunity while touching files.

## Consumer contracts (must keep working)

- `meta/context.py:101-106`: newest ACTIVE `DlSnapshot` per lottery; reads `draws_from, draws_to, cut, window` into `ContextVector`; zero actives → `ValueError("No active engine snapshot found…")`. Wrong values silently corrupt META context hash (leakage bound).
- `meta_service.py:458-469`: all active snapshots + their metrics, keyed `dl-{model_set}-{id}`.
- `exp_service.py:37,477,513-527,635-654`: ENGINE_TABLES guard; `_validate_snapshot` returns `input_fingerprint` for dl; `_read_dl_metrics` averages duplicates by `metric_name`.
- All assume: exactly one active per `(lottery_id, model_set)`, honest header values, Decimal metric values readable via `float()`.

## Spec constraints extracted (verbatim)

From `openspec/specs/dl-engine/spec.md`:
- **DLE-12** (:286-291): "`dl_snapshots` SHALL hold exactly one `active` per `(lottery_id, model_set)`; a successful run writes the new version and retires the old active (and its weights rows) IN the same transaction. On any failure the transaction rolls back and ONLY a terminal `failed` header is persisted — never `active`/`partial`; `is_locked` is set on commit. A rerun whose `input_fingerprint` matches an existing snapshot SHALL return that snapshot — no duplicate version or weights row."
- **DLE-08** (:194-197): "`input_fingerprint` SHALL be canonical SHA-256 over `{data_hash, hyperparameters, architecture, seed, window W, cut, DL_GENERATOR_VERSION}`; `checksum` SHALL be canonical SHA-256 over the Decimal-quantized metric payload only. Float MUST NEVER enter a fingerprint, checksum, or persisted value; canonical JSON is `sort_keys=True` (MLE-05 parity)." Acceptance: "changing `W` or `cut` changes the fingerprint."
- **DLE-04** (:103-104): "window length `W` SHALL default to 10, SHALL be restricted to `2..20`, and SHALL be a fingerprint-affecting hyperparameter."
- **DLE-05** (:127): "`cut` SHALL be declared per run and participate in the fingerprint."
- **DLE-09** (:215-218): "`dl_weights` SHALL store one BLOB per trained model in the custom format `magic + format_version + fingerprint + tensor manifest + raw float32 + SHA-256`. Persistence SHALL use NO pickle/joblib. Size SHALL be ≤16 MiB per BLOB."
- **DLE-11** (:265-268): registry dispatches on `model_set`; `core-3` registers the 2 executed families (MLP, LSTM).
- **DLE-01** (:52-56): header + normalized metrics payload; `value` Numeric(20,8) Decimal; `params_json` hyperparameters only; "model bytes live exclusively in `dl_weights` (DLE-09)".
From `openspec/specs/backend/spec.md:136,162,188`: `POST /dl/train` produces idempotent `dl_*` snapshot version; `GET /dl/models` — the public API surface is already specified.

## Migration assessment

- All three tables created by `0010_dl_tables.py` (chain linear 0001→0016; head `0016_exp_comparisons_run_ids`). `dl_weights` DDL matches ORM column-for-column incl. CHECK; only nuance: composite index `ix_dweight_snapshot_model_id` exists in DB only.
- **Conclusion: an INSERT-only persistence writer requires NO new migration.**

## Surface integration points

- CLI (`cli.py`): group parser registration at :174-192 (`ml` precedent; `opt` at :195-227); handlers :618-672 use `with SessionLocal()`, `_resolve_lottery(session, args.lottery)` (:602-607), deferred imports, plain-JSON output (`{family,status,snapshot_id,fingerprint,metrics_checksum,error}` list for train; snapshot dict or `{"error": …}` for models). Adapters `_CliDrawAdapter/_CliFeatureAdapter` :1207-1273 reusable as-is for DL carriers (convert at composition root per DLE-13).
- API (`api/v1/ml.py`): `POST /ml/train?lottery_id=&family=` (:27-66), `GET /models` (:69-90), `GET /metrics` with ETag/304 (:93-123); `SuccessEnvelope[dict|list[dict]]`; per-request adapter instances (:133-200). Router mount: one import + `include_router` in `api/v1/router.py` (:11-40). New file `api/v1/dl.py` mirrors this; backend spec already names `POST /dl/train`, `GET /dl/models`.
- Service slot free: `services/dl_service.py` (18 services follow `<domain>_service.py`).

## Determinism constants

`DL_GENERATOR_VERSION="1.0.0"` (`dl/version.py:14`); `DL_SEED=0`; `configure_deterministic_torch(seed)`: manual_seed(+cuda), `use_deterministic_algorithms(True)`, single thread; torch deferred-imported (DLE-17). GF-1 verified on real data this session (byte-identical blobs/fingerprints across runs).

## Open decisions for proposal/design

1. **cut-in-fingerprint fix scope** (evidence strongly dictates including real cut per DLE-04/05/08 + ML parity): change `dl.engine.train()` signature to accept `cut` and pass it to `compute_dl_fingerprint`. Touches engine contract used by tests/opt objective/backtesting strategy — bounded, but it IS a production-code change inside this change.
2. **Old weights on retire**: delete previous active's `dl_weights` rows in-tx (spec-literal reading) vs keep them (header retirement renders unreachable). Schema change (status column on dl_weights) rejected as over-engineering unless evidence demands.
3. **Training entrypoint shape**: new CLI group `lip dl {train,models,metrics}` + `POST /dl/train|GET /dl/models|GET /dl/metrics` (mirrors ml; backend spec already promises these routes). Default `--window 10`, `--cut` required or defaulted to 80% walk-forward boundary? (ML defaults cut internally at 4/5; DL spec says cut "SHALL be declared per run".)
4. **Idempotent rerun response**: return existing snapshot metadata (with flag `reused: true`?) vs silent reuse — ML precedent: `find_by_fingerprint` reuse without flag.
5. **Doc citation cleanup**: fix stale "D-A7" cites in `dl_metric.py:6` / `determinism.py:48` while touching (tiny, in-scope).

## Risks & gotchas

- Retire semantics: consumers filter `status=="active"` assuming EXACTLY one active — any non-atomic window breaks meta/exp. Single-commit discipline is mandatory, not stylistic.
- SQLite concurrency: two simultaneous trains could race version generation; UNIQUE constraint converts loss into IntegrityError → failed terminal (acceptable; note in design).
- 16 MiB blob ceiling: LSTM ~212 KB today; safe margin, still pre-validate size before INSERT.
- Float red line: metrics must pass `quantize_metric` before insert; `params_json` sorted-keys JSON.
- Torch deferred import rule (DLE-17): service must not import torch at module load.
- `is_locked` set on commit (DLE-12); `mark_failed` clears lock.
- exp/meta read mid-flight snapshots: placeholder header (empty fingerprint/checksum) must never be visible uncommitted — flush-only store + single commit guarantees this within one session, but other sessions see nothing until commit (SQLite locking).

## Recommended next phase

proposal — frame the change as "DL persistence layer: DlSnapshotStore + DlService + CLI/API surfaces + cut-in-fingerprint engine fix", scope-bounded to existing schema, driven by verbatim DLE-12/08/09/04/05 requirements above.
