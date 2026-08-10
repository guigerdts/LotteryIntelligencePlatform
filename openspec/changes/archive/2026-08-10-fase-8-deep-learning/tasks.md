# Tasks: Fase 8 — Deep Learning Engine

**Change**: `fase-8-deep-learning` · **Store**: openspec · **Date**: 2026-08-09
**Strict TDD**: RED→GREEN per task (runner `backend/.venv/bin/pytest`, CWD=backend/) · Threat matrix: N/A (design §10 — no routing/shell boundary; security handled in `weights.py` tests).

## Review Workload Forecast

| Field | Value |
|-------|-------|
| Estimated changed lines | ~2,040 (240+380+360+380+330+350) |
| 400-line budget risk | High (total ≫ 400; per-PR ≤400) |
| Chained PRs recommended | Yes |
| Suggested split | PR1 → PR2 → PR3 → PR4 → PR5 → PR6 |
| Delivery strategy | ask-on-risk |
| Chain strategy | stacked-to-main (design D8, proposal D9) |

```text
Decision needed before apply: Yes
Chained PRs recommended: Yes
Chain strategy: stacked-to-main
400-line budget risk: High
```

### Suggested Work Units

| Unit | Goal | Likely PR | Focused test command (CWD=backend/) | Runtime harness | Rollback boundary |
|------|------|-----------|--------------------------------------|-----------------|-------------------|
| 1 | torch pin + 0010 + models + gates | PR1 | `pytest tests/test_dl_pr1.py tests/test_migrations.py` | N/A — dep/migration gates, no runtime boundary | Revert pyproject pin; `alembic downgrade 0010` drops only `dl_*`; delete 3 models |
| 2 | dl core: registry/fingerprint/determinism/version/providers | PR2 | `pytest tests/dl/test_fingerprint.py tests/dl/test_determinism.py tests/dl/test_registry.py` | N/A — pure engine modules (threat matrix N/A) | Delete `app/dl/` core modules; nothing downstream exists yet |
| 3 | window + splitter + sequence builder | PR3 | `pytest tests/dl/test_window.py tests/dl/test_splitter.py tests/dl/test_sequence.py` | N/A — pure engine modules | Delete window/splitter/sequence modules |
| 4 | engine (MLP/LSTM) + weights store | PR4 | `pytest tests/dl/test_weights.py tests/dl/test_engine.py tests/dl/test_snapshot_store.py` | N/A — unit/integration layer; service runtime lands PR5 | Delete engine/weights/snapshot_store modules |
| 5 | service + API + CLI + schemas | PR5 | `pytest tests/dl/test_api.py tests/dl/test_cli.py tests/dl/test_floor.py` | `lip dl train|models|metrics` against fixture DB (TestClient parity) | Remove routes/CLI/service; 0010 downgrade |
| 6 | E2E (GF1) + docs | PR6 | `pytest tests/dl/test_dl_determinism_e2e.py` then full `pytest` + `ruff check .` | GF1: two seeded CPU runs on synthetic 120-draw fixture, two DBs | Revert docs (API_SPEC §9, README, PROJECT_STATUS); remove e2e tests |

## Dependency Graph

```
T-01(pin) ──► T-04             T-02(models) ──► T-03(migration) ──► T-04(gates)
PR1 ──► PR2: T-05 ─► T-06 ─► T-07 ─► T-09 ; T-08(providers) independent seam
PR2 ──► PR3: T-11(window) ─► T-12(splitter) ─► T-13(sequence, needs T-08 targets)
PR3 ──► PR4: T-15(weights) ; T-16(engine: needs T-06/T-13/T-15) ─► T-17(store: needs T-02/T-16)
PR4 ──► PR5: T-19(errors) ─► T-20(service: needs T-11/12/16/17) ─► T-21(schemas) ─► T-22(api) ─► T-23(cli)
T-22/T-23 ─► T-24(inte tests)
PR5 ──► PR6: T-25(e2e) ; T-26(docs) ; T-27(verify pass)
```

## PR1 — Deps + Migration + Models + Ban-Gate (~250 LOC)

| Task | Description | Files | Blocked-by | LOC | Must-pass tests |
|------|-------------|-------|------------|-----|-----------------|
| T-01 | Exact-pin `torch==2.5.1` (CPU wheel, resolved at apply) + signed networkx-transitive exception comment (D1, DLE-06) | `backend/pyproject.toml` (M) | — | 15 | `test_dl_pr1.py::test_torch_exact_pin` |
| T-02 | Create `DlSnapshot`/`DlMetric`/`DlWeight` ORM entities: `Numeric(20,8)`, FK RESTRICT, UNIQUE per DLE-01/09 (CHECK status, size≤16 MiB); register in `__init__` | `models/dl_snapshot.py`, `dl_metric.py`, `dl_weight.py` (C), `models/__init__.py` (M) | — | 120 | `test_dl_pr1.py::test_dl_metadata_registered` |
| T-03 | Migration `0010_dl_tables` (`down_revision="0009_ml_tables"`): 3 tables + 3 indexes; downgrade drops ONLY `dl_*` (DLE-16) | `alembic/versions/0010_dl_tables.py` (C) | T-02 | 75 | `test_migrations.py` 0010 up/down; `ml_*` intact |
| T-04 | New `test_dl_pr1.py` gate: torch pin, ban-gate scan extended to `backend.app.dl` (no networkx/banned imports), 0010 non-destructive; extend `test_ml_pr1.py` deny-list (RED-first, fails pre-T-01..03) | `tests/test_dl_pr1.py` (C), `tests/test_ml_pr1.py` (M) | T-01, T-03 | 55 | `pytest tests/test_dl_pr1.py tests/test_ml_pr1.py` |

## PR2 — DL Core: Registry · Fingerprint · Determinism · Providers · Version (~380 LOC)

| Task | Description | Files | Blocked-by | LOC | Must-pass tests |
|------|-------------|-------|------------|-----|-----------------|
| T-05 | `DL_GENERATOR_VERSION = "1.0.0"` constant + package seam docstrings only | `dl/__init__.py`, `dl/version.py` (C) | — | 5 | import smoke |
| T-06 | `configure_deterministic_torch()` (seed 0, `use_deterministic_algorithms(True)`, `set_num_threads(1)`, float32) + local `quantize_metric(20,8)` + `compute_metrics_checksum` (Decimal-only digest, D-A2) | `dl/determinism.py` (C) | T-05 | 75 | `test_determinism.py` (RED: non-det op fails clean, no active snapshot) |
| T-07 | `compute_dl_fingerprint(...)` canonical SHA-256 over `{data_hash, hyperparams{mlp,lstm}, architecture, seed, window, cut, version}`, `sort_keys=True`, run-scoped (D-A4, DLE-08) | `dl/fingerprint.py` (C) | T-06 | 40 | `test_fingerprint.py` (W/cut change ⇒ digest change; float never in digest) |
| T-08 | `DrawHistoryProvider`/`FeatureSnapshotProvider` Protocols + frozen `DrawRow`/`FeatureRow`; absence ⇒ `None` (SNAPSHOT_NOT_FOUND), never zero-guessed (DLE-13) | `dl/providers.py` (C) | — | 65 | `test_providers.py` seam: no F5/F7 adapter import |
| T-09 | `build_dl_registry()`: core-3 = {mlp, lstm} executed; future-dl = {transformer, tensorflow} declared; unknown family fail-fast listing known (DLE-11) | `dl/registry.py` (C) | T-05 | 35 | `test_registry.py` (core-3 exactly MLP+LSTM; future-dl zero rows) |
| T-10 | Unit suites for T-05..09 (fingerprint digest, determinism fail-explicit, registry dispatch) | `tests/dl/test_fingerprint.py`, `test_determinism.py`, `test_registry.py` (C) | T-06/07/09 | 160 | `pytest tests/dl/test_fingerprint.py tests/dl/test_determinism.py tests/dl/test_registry.py` |

## PR3 — Window · Splitter · Sequence Builder (~360 LOC)

| Task | Description | Files | Blocked-by | LOC | Must-pass tests |
|------|-------------|-------|------------|-----|-----------------|
| T-11 | `WindowBuilder.build_windows(draws, rows, W)`: W consecutive F4 vectors `n-W+1..n`, frames `n∈[W,N-1]`; W∉2..20 or W>draws−1 ⇒ clean validation error; missing draws ⇒ SNAPSHOT_NOT_FOUND; no padding (DLE-04) | `dl/window.py` (C) | T-08 | 70 | `test_window.py` (default W=10, W=1/25 rejected, history<W error) |
| T-12 | `split_windows`/`validate_windows`: train end ≤ cut, eval start > cut, gap dropped; straddle/interleave/shuffle ⇒ `LeakageError` (DLE-05, D-A7) | `dl/splitter.py` (C) | T-11 | 60 | `test_splitter.py` — RED-first: straddle/shuffle fail, no snapshot; clean split passes |
| T-13 | `build_tensors(windows, draws)`: per-number binary y from n+1 (DLE-03 F7-identical), float32 tensors oldest→newest, canonical feature order (F12 parity), no shuffle (DLE-04/07) | `dl/sequence_builder.py` (C) | T-11, T-08 | 50 | `test_sequence.py` (shape/order/dtype float32) |
| T-14 | Unit suites for T-11..13 | `tests/dl/test_window.py`, `test_splitter.py`, `test_sequence.py` (C) | T-11/12/13 | 180 | `pytest tests/dl/test_window.py tests/dl/test_splitter.py tests/dl/test_sequence.py` |

## PR4 — Training Engine + Weights Store (~380 LOC)

| Task | Description | Files | Blocked-by | LOC | Must-pass tests |
|------|-------------|-------|------------|-----|-----------------|
| T-15 | `encode_weights`/`validate_weights`: magic `LIPDLW01` + fv=1 + fingerprint + JSON manifest + raw float32 LE + SHA-256; no pickle/joblib; ≤16 MiB; reject tamper/version/fingerprint/size (DLE-09) | `dl/weights.py` (C) | — | 80 | `test_weights.py` — RED-first: round-trip, tamper/W-version/foreign-fp/size rejected |
| T-16 | `DlEngine.train(family, ...)`: MLP (flatten→Linear(100,64)→ReLU→Linear(64,1)) + LSTM (LSTM(F,64,1) seeded→Linear(64,1)), BCEWithLogits, Adam 1e-3, 50 ep, batch 32 (D-A8/DE-01/02); eval-only metrics {accuracy, precision, recall, f1, roc_auc}; non-determinism ⇒ explicit failure (DLE-07) | `dl/engine.py` (C) | T-06, T-13, T-15 | 110 | `test_engine.py` — RED-first: metrics persisted + checksum; same-env rerun identical |
| T-17 | `DlSnapshotStore`: get_active, find_by_fingerprint, next_version, create_snapshot, retire_old_active, mark_failed, bulk metrics/weights, weights_for_snapshot (DLE-12 D-A1) | `dl/snapshot_store.py` (C) | T-02, T-16 | 85 | `test_snapshot_store.py` (atomic replace retires old+weights; failure ⇒ only `failed`; fingerprint idempotent) |
| T-18 | Unit/integration suites for T-15..17 | `tests/dl/test_weights.py`, `test_engine.py`, `test_snapshot_store.py` (C) | T-15/16/17 | 105 | `pytest tests/dl/test_weights.py tests/dl/test_engine.py tests/dl/test_snapshot_store.py` |

## PR5 — Service + API + CLI + Schemas (~330 LOC)

| Task | Description | Files | Blocked-by | LOC | Must-pass tests |
|------|-------------|-------|------------|-----|-----------------|
| T-19 | Add `InsufficientDataError("INSUFFICIENT_DATA")` (D-A7; 422) — LeakageError ⇒ `ValidationError` mapping | `services/errors.py` (M) | — | 8 | `test_api_errors.py` code map |
| T-20 | `DlService.train(...)` composition root: floor check→active F4 snapshot→WindowBuilder→Splitter→DlEngine→create_snapshot+retire old in ONE tx; failure ⇒ rollback + terminal `failed`; `find_by_fingerprint` idempotency (DLE-10/12/13) | `services/dl_service.py` (C) | T-11/12/16/17, T-19 | 105 | `test_floor.py` (10-draw ⇒ INSUFFICIENT_DATA zero rows — RED-first) |
| T-21 | `TrainRequest` (lottery_id\|code, model_set="core-3", window=None, cut=None), `ModelsList`, `MetricsRead` (design-time parity, D-A-schemas) | `schemas/dl.py` (C) | — | 40 | pydantic validation (W bounds 2..20) |
| T-22 | Routes `POST /dl/train`, `GET /dl/models`, `GET /dl/metrics` + `_DrawAdapter`/`_FeatureAdapter`; 404/422 maps; NO `/dl/predict` (DLE-14); mount in router | `api/v1/dl.py` (C), `api/v1/router.py` (M) | T-20, T-21 | 60 | `test_api.py` (3 routes, 404 SNAPSHOT_NOT_FOUND, 422 floor/leakage, no predict route) |
| T-23 | `lip dl train|models|metrics` + `_CliDrawAdapter`/`_CliFeatureAdapter` (REQ-12 parity, no predict/weights command) | `cli.py` (M) | T-20 | 45 | `test_cli.py` parity + floor behavior |
| T-24 | Integration suites for T-20..23 | `tests/dl/test_floor.py`, `test_api.py`, `test_cli.py` (C) | T-22/23 | 72 | `pytest tests/dl/test_floor.py tests/dl/test_api.py tests/dl/test_cli.py` |

## PR6 — E2E + Documentation (~350 LOC)

| Task | Description | Files | Blocked-by | LOC | Must-pass tests |
|------|-------------|-------|------------|-----|-----------------|
| T-25 | GF1 e2e: two seeded CPU runs on synthetic 120-draw fixture (structural/E2E only, DLE-10) in two DBs ⇒ identical fingerprint+checksum+metric rows+weights bytes; anti-leakage e2e (straddle writes nothing); weights only in `dl_weights` BLOB (RED-first) | `tests/dl/test_dl_determinism_e2e.py` + fixture (C) | T-24 | 230 | `pytest tests/dl/test_dl_determinism_e2e.py` |
| T-26 | Docs-drift: API_SPEC §9 (remove `/dl/predict`, add 3 routes), README, PROJECT_STATUS, spec sync note | `API_SPECIFICATION.md`, `README.md`, `PROJECT_STATUS.md` (M) | T-22 | 90 | prose review; routes list matches T-22 |
| T-27 | Full verification: entire `pytest` + `ruff check .` + `ruff format` green; `git diff` scope check: F1–F7 untouched; migration up/down idempotent | repo-wide | T-25, T-26 | 30 | full suite + ruff + scope diff |

**Total**: 27 tasks ≈ 2,040 LOC · 6 PRs (each ≤400) · 6 rollback boundaries.

## Risk Register

| PR | Risk | L | Mitigation |
|----|------|---|------------|
| PR1 | Exact torch CPU version drift at apply; networkx exception scope creep | Med | T-01 resolve stable 2.x at apply; T-04 ban-gate deny-list asserts networkx/banned absent from installable deps; exception comment signed torch/F8 |
| PR1 | 0010 head mismatch (0009 not yet archived) | Med | `down_revision="0009_ml_tables"` pinned; T-03/T-04 up-down idempotence + `ml_*` intact assertions |
| PR2 | CPU determinism gaps (torch ops may be non-deterministic under `use_deterministic_algorithms`) | Med | T-06 fail-explicit gate; GF1 same-env gate (T-25); non-det op ⇒ clean `failed`, never silent |
| PR2 | future-dl family accidentally executes | Low | T-09 dispatch dict + T-10 registry test asserts core-3 = exactly {mlp, lstm} |
| PR3 | Leakage edge cases at `cut`/window boundaries; missing draws silently padded | Med | T-12 `LeakageError` RED tests; T-11 no-padding + SNAPSHOT_NOT_FOUND |
| PR4 | LSTM hidden-init determinism (seeded init order); single-class eval split (roc_auc baseline) | Med | T-16 seed 0 init + T-18 deterministic replay test; roc_auc chance baseline (F7 parity, D-A6) |
| PR4 | Weights BLOB >16 MiB (2 models × ~50 numbers) rejected at commit | Med | T-15 size gate + CHECK constraint (T-02); T-18 oversized reject |
| PR5 | 422 vs 400 for INSUFFICIENT_DATA (open question) | Low | D-A7 chose 422; confirm at review; T-24 asserts envelope code not status internals |
| PR5 | Sync training latency blocks request thread | Med | manual-only + CLI-first; small e2e epochs; no automatic triggers (DLE-14) |
| PR6 | Two-DB e2e non-identical floats (GC/thread) | Med | float32 + single thread + seed 0; GF1 compares quantized Decimal rows + checksum + weights bytes; mismatch = run failure, never degrade |

## Success Criteria (from proposal §10)

- [ ] GF1 two-DB e2e: identical fingerprint + checksum + metrics rows on CPU (T-25)
- [ ] <100 draws ⇒ `INSUFFICIENT_DATA`, no snapshot (T-20/T-24)
- [ ] Straddle/shuffle ⇒ `LeakageError`; walk-forward passes (T-12/T-14)
- [ ] No pickle/joblib bytes; tampered weights rejected (T-15/T-18)
- [ ] 0010 up/down non-destructive; `ml_*` untouched (T-03/T-04)
- [ ] 6 PRs ≤400 LOC; pytest + ruff green (T-27)