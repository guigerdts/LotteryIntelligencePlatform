# Delta for Deep Learning Engine (`dl-engine`)

**Change**: `fase-16-performance` · **Date**: 2026-08-18
**Slice**: S6 — deferred torch import (cold start). No computation change.

## ADDED Requirements

### DLE-17: Deferred Heavy-Dependency Import (Cold Start)

Heavy runtime imports (`torch`/`torch.nn` in `dl/*`; `sklearn` in `ml/engine.py`) SHALL be deferred to first use inside the entry functions (`configure_deterministic_torch`, `engine.train`, model builders/`forward`) instead of module top-level. Behavior SHALL be functionally identical before/after deferral: thread/seed configuration applied by `configure_deterministic_torch` at call time (not import time) SHALL be preserved, and DL determinism (DLE-07: seed 0, deterministic ops, fail-explicit) SHALL hold after deferral. Any import-time side effect MUST move with the import to first use. The cold-start target `import backend.app.main` ≤8 s is the transversal gate (PFM-06, proposal §5 baseline 25.3 s).

#### Scenario: deferred import preserves behavior

- GIVEN an app with deferred torch imports
- WHEN a DL entry function (`engine.train` / `configure_deterministic_torch`) first executes
- THEN torch imports successfully at first use and training behaves identically to a pre-deferral run

#### Scenario: DL determinism preserved after deferral

- GIVEN two identical seeded CPU runs
- WHEN one runs before and one after the import deferral
- THEN fingerprints, checksums, and quantized metric rows are byte-identical (DLE-07 gate)

#### Scenario: cold-start target met

- GIVEN the exact command `time python -c "import backend.app.main"`
- WHEN measured after S6
- THEN the wall time is ≤8 s (baseline 25.3 s, proposal §5)