# Archive Report — Fase 10: Backtesting Engine

**Change**: `fase-10-backtesting-engine`
**Store**: `openspec`
**Archived**: `2026-08-10`
**Archived to**: `openspec/changes/archive/2026-08-10-fase-10-backtesting-engine/`

## Purpose

Walk-forward backtesting engine with anti-leakage, deterministic fingerprints (SHA-256), lottery-specific metrics, dual benchmarks (uniform random + hypergeometric), atomic snapshot lifecycle (`active`→`retired`→`failed`), and full API/CLI surface parity. Manual-only — no scheduler, no auto-execution.

## Scope

- **In scope**: Backtesting only — walk-forward splitter, metrics (hit rate, match distribution, average matches, consistency score), benchmarks (uniform random + hypergeometric), engine orchestrator, snapshot store, service layer, API (3 endpoints), CLI (3 commands), E2E determinism/isolation tests
- **Out of scope**: F11 (experiments/comparison), F13 (number generation), F14 (dashboard), any auto-execution

## Final State

### Commits on Main (PR1–PR6)

| PR | Hash | Description |
|----|------|-------------|
| PR1 | `a329b18` | Foundation — migration 0012, ORM models, domain types |
| PR2 | `b1ddd95` | Core primitives — fingerprint, determinism, splitter, strategy |
| PR3 | `8e3fca9` | Metrics + Benchmarks — lottery metrics, uniform/hypergeometric |
| PR4 | `57be286` | Engine orchestrator + SnapshotStore — full walk-forward cycle |
| PR5 | `6fc4f2f` | Service + API + CLI — backtesting surface, manual-only |
| PR6 | `5385681` | E2E tests + docs — Fase 10 final integration |

### Requirements BTE-01..18

| ID | Requirement | PR |
|----|-------------|----|
| BTE-01 | Independent `bt_*` schema | PR1 |
| BTE-02 | Strict read-only vs other engines | PR4 |
| BTE-03 | Generic StrategyProtocol contract | PR2 |
| BTE-04 | Walk-forward window splitter | PR2 |
| BTE-05 | Determinism: seed-based | PR2 |
| BTE-06 | Fingerprint: SHA-256 | PR2 |
| BTE-07 | Data floor: configurable minimum | PR4 |
| BTE-08 | Lottery-specific metrics | PR3 |
| BTE-09 | Dual benchmark | PR3 |
| BTE-10 | Snapshot lifecycle & atomicity | PR4 |
| BTE-11 | Provider Protocols only | PR2 |
| BTE-12 | Manual-only surface | PR5 |
| BTE-13 | Migration 0012 additive | PR1 |
| BTE-14 | Multi-lottery isolation | PR6 |
| BTE-15 | Convergence tracking | PR4 |
| BTE-16 | Benchmark same eval period | PR3 |
| BTE-17 | Temporal ordering | PR2 |
| BTE-18 | Walk-forward in fingerprint | PR2 |

### Requirements BTS-01..04

| ID | Requirement | PR |
|----|-------------|----|
| BTS-01 | API: POST /run, GET /history, GET /results | PR5 |
| BTS-02 | CLI: lip bt run/history/results | PR5 |
| BTS-03 | Pydantic v2 schemas | PR5 |
| BTS-04 | Service layer | PR5 |

### Tests

| Category | Count |
|----------|-------|
| bt_* total | **172** |
| All pass | ✅ |

### Migration Verification

| Check | Status |
|-------|--------|
| Upgrade creates bt_snapshots + bt_results | ✅ |
| Downgrade drops in reverse order | ✅ |
| Additive only — no existing tables touched | ✅ |
| Chain: 0011 → 0012 | ✅ |

### Artifacts Archived

- `openspec/changes/fase-10-backtesting-engine/proposal.md`
- `openspec/changes/fase-10-backtesting-engine/design.md`
- `openspec/changes/fase-10-backtesting-engine/tasks.md`
- `openspec/specs/backtesting-engine/spec.md`

### What Changed

- Archive directory created: `openspec/changes/archive/2026-08-10-fase-10-backtesting-engine/`
- Change artifacts moved to archive
- Delta specs synced to `openspec/specs/backtesting-engine/spec.md`
- `openspec/specs/backend/spec.md` updated with bt_* table references

### What Did NOT Change

- No code modified
- No tests modified
- No dependencies added
- No F11/F13/F14 features
- No commits altered

## Decision History

| Decision | Rationale |
|----------|-----------|
| D1: Generic StrategyProtocol | bt_* is engine-agnostic; ml-* and dl-* strategies can be plugged in via adapter |
| D2: Lottery-specific metrics | Standard financial metrics don't apply; hit rate and match distribution are domain-specific |
| D3: Dual benchmark | Uniform random as baseline + hypergeometric as theoretical optimum |
| D4: Configurable walk-forward | train_years, eval_count, step_count — flexible for different lottery periodicities |
| D5: Direct engine calls via adapters | No external backtesting framework; everything runs in-process |
| D6: numpy/pandas only | No new dependencies; already present in project |

## Notes

- Fingerprint collision across lotteries: `find_by_fingerprint` doesn't filter by lottery_id — same config on different lotteries with same data count produces same fingerprint. Use different seeds to get different fingerprints.
- BtSnapshot uses delete+insert (not retire) because UNIQUE constraint is on `(lottery_id, strategy_id, fingerprint)` without status.
- WalkForwardSplitter train_years converted to draw count via median gap (~7 days/week).
- BtService._make_strategy returns a `_DummyBtStrategy` for PR5; real ML/DL wiring deferred.
- Schemas inline in API file (schemas/bt.py deleted).
