# Delta for backend

**Change**: `dl-snapshot-persistence` · **Store**: `openspec` · **Date**: 2026-08-22

## No Requirement Deltas

IMPLEMENTATION-ONLY change: no ADDED, MODIFIED, REMOVED, or RENAMED requirements. The DL
API/CLI surfaces this change implements are already specified verbatim in
`openspec/specs/backend/spec.md`. Nothing here merges into the main spec at archive.

## Coverage (proposal behavior → existing requirement)

| Proposal behavior | Covered by |
|---|---|
| `POST /dl/train` — fields `lottery_id\|code`, `model_set` (`core-3` default), optional `window` (default 10, bounds 2..20), optional `cut`; invalid lottery → 404; floor → `INSUFFICIENT_DATA`; leakage split rejected; failure → `training_error` (500); never overlaps reads or fires on import | REQ-10 (dl paragraph), DLE-14, DLE-04, DLE-05, DLE-10 |
| `GET /dl/models`, `GET /dl/metrics` — storage-only, MUST NOT train, missing snapshot → 404 `SNAPSHOT_NOT_FOUND`, no weights exposure, ETag/304 per ml house pattern | REQ-11 (dl paragraph), DLE-14 |
| Router mount of DL routes; only train/models/metrics registered; `/dl/predict`, ranking, weights-download absent | REQ-11 ("dl routes are limited to train/models/metrics"), DLE-14 |
| CLI `lip dl train\|models\|metrics` mirroring the API options and floor behavior; no predict/export/weights command | REQ-12 (dl paragraph + "CLI trains dl snapshot") |

## Design-Routed Resolutions (no spec text)

- Default when request omits `cut`: proposal Decision #3 — walk-forward boundary
  `len(frame)*4//5` (M-A8 parity with `ml/engine.py`). REQ-10 already declares `cut` optional;
  the concrete fallback value is an interface default ratified at sdd-design.
