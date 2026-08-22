# Proposal: Fase 13 — Intelligent Generator

## 1. Problem

After F12 selects best models, no mechanism produces concrete lottery combinations weighted by those selections. F13 generates reproducible combinations from F12 scores + F5 probability distributions, persisted as immutable snapshots.

## 2. Goals / Non-Goals

**Goals**: Score-weighted generation, exact `count` output, deterministic, snapshot lifecycle (active|retired|failed), API/CLI mirroring F12.

**Non-Goals**: No ML/DL inference (C2), no evaluation (C4), no historical exclusion (C5), no F5 modification (N4), no inverse coupling.

## 3. Key Decisions

| Decision | Choice |
|----------|--------|
| N1: Count | Default 10, max 100, configurable |
| N2: Allocation | F12 scores → weight → deterministic count split |
| N3: Seed | SHA-256(selection_fingerprint, lottery_id, count, GENERATOR_VERSION); optional override |
| N4: Module | New `generators/`; reuse only `derive_seed`/`isolated_rng` from F5 |
| N5: score | Nullable on `gen_combinations` |

**Allocation rule** (hard requirement for sdd-spec): `cᵢ = floor(sᵢ/Σs × count)`. Remainder distributed one-per-candidate in descending score order (ties by rank). `Σcᵢ == count` exactly.

## 4. Scope

**In**: `generators/` module, `GenService`, migration 0015, 4 API endpoints, 4 CLI commands, error taxonomy.

**Out**: Evaluation, ML/DL inference, statistical filters, F5 modifications.

## 5. Approach

**Flow**: Resolve F12 selection → allocate count → load F5 distributions → sample with isolated RNG → validate (C1) → persist snapshot.

**Module**: `generators/` reuses `derive_seed`/`isolated_rng` only. F5 untouched.

**Persistence (C7)**: `gen_snapshots` (lottery_id, selection_id FK, version, status, fingerprint, config_json) + `gen_combinations` (snapshot_id FK, position, numbers JSON, super_number, score). Migration 0015 additive.

**Surface (C8)**: POST /gen/generate, GET /gen/combinations, POST /gen/snapshot, GET /gen/snapshots. `lip gen generate|combinations|snapshot|snapshots`.

## 6. Affected Areas

| Area | Impact |
|------|--------|
| `generators/` | New module |
| `models/gen_*.py` | New ORM |
| `services/gen_service.py` | New service |
| `api/v1/gen.py` | New router |
| `schemas/gen.py` | New schemas |
| `alembic/versions/0015_gen_tables.py` | New migration |
| `cli.py` | Modified (gen subcommands) |
| `api/v1/router.py` | Modified (include gen) |

## 7. Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| F5 distribution unavailable | Medium | Error (C6), no fallback |
| Count-allocation drift | High | Integer rule (N2) |
| Scope creep | Medium | MVP enforced |

## 8. Rollback

`alembic downgrade -1` drops gen_* tables. No existing tables modified.

## 9. Dependencies

- F12 active selection, F5 active probability snapshots, lottery config.

## 10. Success Criteria

- [ ] Exactly `count` combinations per successful generation
- [ ] Determinism: same inputs + seed → identical output
- [ ] Combinations respect lottery config
- [ ] Insufficient selection → typed error
- [ ] Snapshot idempotency via fingerprint
- [ ] No inverse coupling F5→F13
- [ ] All tests pass
