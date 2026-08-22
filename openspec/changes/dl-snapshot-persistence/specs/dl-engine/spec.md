# Delta for dl-engine

**Change**: `dl-snapshot-persistence` · **Store**: `openspec` · **Date**: 2026-08-22

## No Requirement Deltas

This is an IMPLEMENTATION-ONLY change. It adds no requirements, modifies none, removes none,
and renames none. Every behavior in the proposal is already mandated verbatim by the main
specs below; this change builds the persistence/service/surface layer those requirements
require. Nothing in this delta merges into `openspec/specs/dl-engine/spec.md` at archive.

## Coverage (proposal behavior → existing requirement)

| Proposal behavior | Covered by |
|---|---|
| `DlSnapshotStore`: flush-only, `find_by_fingerprint`, `next_version`, `create_snapshot`, `bulk_insert_metrics`, `retire_old_active`, `mark_failed` | DLE-12, DLE-01 |
| Atomic tx per run: placeholder header → train → fill → metrics + weights → retire old active AND its weights rows → single commit; failure = rollback → `mark_failed` → commit; ONLY terminal `failed` persists; `is_locked` on commit | DLE-12 (verbatim) |
| Idempotent rerun by `input_fingerprint`, no duplicate version/weights | DLE-12 |
| One weights row per trained model; custom format; ≤16 MiB pre-check; no pickle/joblib | DLE-09, DLE-11, DE-01, DE-02 |
| Decimal-quantized metrics only; float never persisted/digested | DLE-08, DLE-01 |
| Engine fix: thread real `cut` into fingerprint; expose `cut` on `TrainResult` | DLE-05, DLE-08 — conformance to existing acceptance "changing `W` or `cut` changes the fingerprint"; current hardcoded `cut=0` violates it. No new behavior specified. |
| `W` default 10, bounds 2..20, fingerprint-affecting | DLE-04 |

## Design-Routed Resolutions (no spec text)

- DLE-12 "(and its weights rows)" retirement mechanism: proposal Decision #2 — DELETE the old
  active's `dl_weights` rows within the same transaction (header rows stay immutable). The
  spec fixes the observable outcome; delete-vs-mark-vs-orphan is HOW and is ratified at
  sdd-design.
