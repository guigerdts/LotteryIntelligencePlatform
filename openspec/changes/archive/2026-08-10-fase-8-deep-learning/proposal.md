# Proposal: Fase 8 — Deep Learning Engine

**Change**: `fase-8-deep-learning` · Store: openspec · Date: 2026-08-09 · Predecessor: exploration

## 1. Intent

Deterministic CPU-only PyTorch training (MLP/LSTM) on windowed F4 sequences; window-aware walk-forward anti-leakage; authorized weight persistence for `dl/` only; ≥100 real draws; new engine parallel to `ml/` (F7 contracts frozen, untouched).

## 2. Scope

**In**: `app/dl/` (registry, fingerprint, determinism, window splitter, sequence builder, training, weights store, providers); migration `0010_dl_tables` (`dl_snapshots`, `dl_metrics`, `dl_weights`); torch exact-pin + signed networkx exception; CLI `lip dl train|models|metrics`; API `POST /dl/train`, `GET /dl/models`, `GET /dl/metrics`; new `dl-engine` spec + backend delta.

**Out**: `/dl/predict` (F7 no-predict-in-production); weights download endpoint; Transformer execution (declared `future-dl`); stat/graph/prob inputs (F3 slices absent); F5 adapter reuse + F5-bug fix; any F3–F7 change.

## 3. Capabilities

- **New** `dl-engine` → `openspec/specs/dl-engine/spec.md` (engine `DLE-..`, per-model `DE-..`)
- **Modified** `backend` REQ-10/11/12 — `/dl/*` route + `lip dl` parity (delta)

## 4. Decisions

- **D1 Deps**: PyTorch only, CPU wheels, exact-pinned (e.g. `torch==2.5.1`, resolved to stable 2.x at apply, tree via uv.lock); torch→networkx/sympy/jinja2/filelock/fsspec/typing-extensions = signed exception limited to torch/F8; installable-deps deny-check unchanged (networkx never installable).
- **D2 Weights**: `dl_weights` BLOB; custom format (magic + format_version + fingerprint + tensor manifest + raw float32 + SHA-256); no pickle/joblib; load rejects tampered bytes; ≤16 MiB; MLE-01 exception limited to `dl/`, versioned via fingerprint.
- **D3 Determinism**: GF1 same-env byte-identical CPU; seed 0; `use_deterministic_algorithms(True)`, `set_num_threads(1)`, float32; canonical ordering (draw_number, feature order, W); fingerprint `{data_hash, params, architecture, seed, window, cut, DL_GENERATOR_VERSION}`; checksum over Decimal-quantized metrics; non-deterministic op ⇒ training FAILS, never degrades.
- **D4 Floor**: ≥100 real draws; else clean `INSUFFICIENT_DATA`, no snapshot; synthetic fixtures structural/E2E only.
- **D5 Target/input**: F7-identical binary per-number participation in draw n+1 (F12 comparability); X = window of W consecutive frozen F4 vectors; W=10 default (bounds 2..20, fingerprint-affecting).
- **D6 Leakage**: new window-aware splitter — train windows end ≤ cut, eval windows start > cut; straddle/shuffle ⇒ `LeakageError`.
- **D7 Scope**: `core-3` = MLP + LSTM executed; Transformer, TensorFlow declared `future-dl`.
- **D8 PR chain** (≤400 LOC, stacked-to-main): deps+0010+models (~240) · dl core (~380) · windower+splitter (~360) · training+weights (~380) · service+API+CLI (~330) · e2e+docs (~350).

## 5. Approach

F7 mirror: pure engine, composition-root service, own provider Protocols (`dl/providers.py`), stateless pure helpers shared by import (quantize, canonical digest), atomic active→retired→failed, fingerprint idempotency, manual-only reads (404 absent), additive `0010` (down_revision `0009_ml_tables`).

## 6. Affected Areas

| Area | Impact |
|---|---|
| `backend/pyproject.toml`, ban-gate test | Modified |
| `models/dl_snapshot.py`, `dl_metric.py`, `dl_weight.py`, `0010_dl_tables.py` | New |
| `app/dl/**`, `services/dl_service.py` | New |
| `api/v1/dl.py`, `schemas/dl.py`, `cli.py` | New/Mod |
| `tests/dl/*`, `test_dl_pr1.py` | New |
| `specs/dl-engine`, README, PROJECT_STATUS, API_SPEC §9 | New/Mod |

## 7. Risks

| Risk | L | Mitigation |
|---|---|---|
| torch CPU determinism gaps | Med | fail-explicit + same-env GF1 gate |
| networkx exception scope creep | Med | signed comment, torch/F8-bound test |
| Untrusted weights | High | custom format, fingerprint+size validation, no public load |
| Data scarcity (0 live draws) | High | INSUFFICIENT_DATA floor; fixtures structural-only |
| Sync training latency | Med | manual-only, CLI-first, small e2e epochs |

## 8. Rollback

`alembic downgrade 0010` drops only `dl_*`; revert torch pin + exception comment; remove `app/dl/`, service, routes; F1–F7 untouched.

## 9. Dependencies

F1 draws + F4 active feature snapshot (providers); `torch` CPU pinned; numpy shared; sklearn untouched.

## 10. Success Criteria

- GF1 two-DB e2e: identical fingerprint + checksum + metrics rows on CPU
- <100 draws ⇒ `INSUFFICIENT_DATA`, no snapshot written
- Straddle/shuffle test fails; walk-forward passes
- No pickle/joblib bytes; tampered weights rejected
- 0010 up/down non-destructive; `ml_*` untouched
- 6 PRs ≤400 LOC; pytest + ruff green

## Proposal question round

Relay to user — assumptions to confirm before specs: (1) MLP+LSTM executed, Transformer deferred to `future-dl`; (2) target = F7 binary per-number n+1; (3) W=10 default; (4) `/dl/predict` deferred; (5) weights = SQLite BLOB, custom format, ≤16 MiB. Correct any answer or request a second round.