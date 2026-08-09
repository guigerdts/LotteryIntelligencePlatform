# Tasks: Fase 6 — Graph Engine

**Change**: fase-6-graph-engine · **Store**: openspec · **Date**: 2026-08-08

## PR Plan

| PR | Description | Est. LOC | Dependencies |
|----|-------------|----------|--------------|
| PR1a | Migration 0008 only | ~231 | None |
| PR1b | ORM models + __init__ | ~285 | PR1a |
| PR2 | Co-occurrence + Adjacency + DrawReader + Fingerprint | ~370 | PR1b |
| PR3 | Centrality + Communities + Metrics + Registry | ~400 | PR2 |
| PR4 | Snapshot store + Schemas | ~375 | PR3 |
| PR5 | Graph service orchestration | ~380 | PR4 |
| PR6 | REST API + CLI | ~375 | PR5 |
| PR7 | Baloto fixtures + E2E + Docs | ~270 | PR6 |

## Tasks

### Task 1: Create migration 0008_graph_tables.py
**PR**: PR1a
**Requirements**: REQ-07
**Decisions**: D5, D-A2
**Description**: Create Alembic migration for graph_snapshots and graph_values tables
**Files**:
- create: backend/alembic/versions/0008_graph_tables.py
**Estimated LOC**: ~80
**Dependencies**: None
**Verification**:
- Upgrade + downgrade both implemented
- down_revision = '0007_probability_tables'
- Only graph_* tables affected

### Task 1b: Test migration 0008
**PR**: PR1a
**Requirements**: REQ-07
**Decisions**: D5
**Description**: Tests for migration 0008 upgrade and downgrade
**Files**:
- modify: backend/tests/test_migrations.py
**Estimated LOC**: ~151
**Dependencies**: Task 1
**Verification**:
- test_upgrade_0008_* passes
- test_downgrade_0008_* passes

### Task 2: Create graph ORM models
**PR**: PR1b
**Requirements**: REQ-07
**Decisions**: D7, A2, A3
**Description**: Create GraphSnapshot and GraphValue ORM models
**Files**:
- create: backend/src/backend/app/models/graph_snapshot.py
- create: backend/src/backend/app/models/graph_value.py
- modify: backend/src/backend/app/models/__init__.py
**Estimated LOC**: ~125
**Dependencies**: PR1a
**Verification**:
- Import works
- Decimal(20,8) round-trip
- Unique constraints correct

### Task 2b: Test graph ORM models
**PR**: PR1b
**Requirements**: REQ-07
**Decisions**: D7
**Description**: Tests for graph ORM models
**Files**:
- create: backend/tests/graph/test_graph_models.py
**Estimated LOC**: ~160
**Dependencies**: Task 2
**Verification**:
- Decimal round-trip test
- FK RESTRICT tests
- UNQ scope-version + cell tests

### Task 3: Implement co-occurrence engine (GM-01)
**PR**: PR2
**Requirements**: REQ-01, REQ-02, GES-01
**Decisions**: D1, D2, D8, A6
**Description**: Implement co-occurrence matrix computation
**Files**:
- create: backend/src/backend/app/graph/cooccurrence.py
**Estimated LOC**: ~120
**Dependencies**: PR1b
**Verification**:
- Matrix symmetry
- Integer arithmetic (no float)
- Full-history and rolling-window
- Byte-identical reruns

### Task 4: Implement graph construction (GM-02)
**PR**: PR2
**Requirements**: GES-02
**Decisions**: D1, D8
**Description**: Implement adjacency graph from co-occurrence matrix
**Files**:
- create: backend/src/backend/app/graph/construction.py
**Estimated LOC**: ~80
**Dependencies**: Task 3
**Verification**:
- Threshold semantics
- Canonical node order
- No self-loops

### Task 5: Create DrawReader Protocol + fingerprint
**PR**: PR2
**Requirements**: REQ-06
**Decisions**: D7, A9, A6
**Description**: Create DrawReader Protocol and fingerprint computation
**Files**:
- create: backend/src/backend/app/graph/__init__.py
- create: backend/src/backend/app/graph/engine.py
**Estimated LOC**: ~170
**Dependencies**: Tasks 3, 4
**Verification**:
- DrawReader protocol defined
- Fingerprint includes window params
- Engine orchestrates GM-01, GM-02

### Task 6: Implement centrality engine (GM-03)
**PR**: PR3
**Requirements**: REQ-03, GES-03
**Decisions**: D1, D4, D8, A7, A8
**Description**: Implement degree, closeness, betweenness centrality
**Files**:
- create: backend/src/backend/app/graph/centrality.py
**Estimated LOC**: ~150
**Dependencies**: PR2
**Verification**:
- Degree: O(1)/node
- Closeness: O(V²)
- Betweenness: Brandes with int path counts
- All Decimal-safe
- No float leakage

### Task 7: Implement community detection (GM-04)
**PR**: PR3
**Requirements**: REQ-04, GES-04
**Decisions**: D1, D3, D8
**Description**: Implement pure-greedy modularity community detection
**Files**:
- create: backend/src/backend/app/graph/community.py
**Estimated LOC**: ~120
**Dependencies**: PR2
**Verification**:
- Deterministic by construction
- Canonical node order
- Tie-break by node id
- Byte-identical reruns
- No PRNG

### Task 8: Implement network metrics + registry (GM-05)
**PR**: PR3
**Requirements**: REQ-05, GES-05
**Decisions**: D1, D8
**Description**: Implement density, modularity score, and method registry
**Files**:
- create: backend/src/backend/app/graph/metrics.py
**Estimated LOC**: ~130
**Dependencies**: Tasks 6, 7
**Verification**:
- Density: |E| / (V*(V-1)/2)
- Modularity: Newman score
- Registry: GM-01..GM-05 registered

### Task 9: Implement snapshot store lifecycle
**PR**: PR4
**Requirements**: REQ-07
**Decisions**: D7, A2
**Description**: Implement graph snapshot store with lifecycle
**Files**:
- create: backend/src/backend/app/graph/snapshot_store.py
**Estimated LOC**: ~170
**Dependencies**: PR3
**Verification**:
- Save/load snapshots
- Fingerprint-based lookup
- Empty snapshot handling

### Task 10: Create graph schemas
**PR**: PR4
**Requirements**: REQ-08
**Decisions**: D7
**Description**: Create Pydantic schemas for graph API
**Files**:
- create: backend/src/backend/app/schemas/graph.py
**Estimated LOC**: ~205
**Dependencies**: Task 9
**Verification**:
- Request/response schemas
- Validation rules
- Type hints

### Task 11: Implement graph service
**PR**: PR5
**Requirements**: REQ-08, REQ-09
**Decisions**: D7, A9
**Description**: Implement graph service orchestration
**Files**:
- create: backend/src/backend/app/services/graph_service.py
**Estimated LOC**: ~380
**Dependencies**: PR4
**Verification**:
- Full pipeline: co-occurrence → construction → centrality/community/metrics
- Snapshot persistence
- Error handling

### Task 12: Implement REST API
**PR**: PR6
**Requirements**: REQ-08
**Decisions**: D7
**Description**: Implement graph REST endpoints
**Files**:
- create: backend/src/backend/app/api/v1/graph.py
**Estimated LOC**: ~200
**Dependencies**: PR5
**Verification**:
- GET /graph/snapshots
- GET /graph/snapshots/{id}
- POST /graph/compute

### Task 13: Implement CLI subparser
**PR**: PR6
**Requirements**: REQ-09
**Decisions**: D7
**Description**: Implement graph CLI commands
**Files**:
- modify: backend/src/backend/app/cli.py
**Estimated LOC**: ~175
**Dependencies**: PR5
**Verification**:
- graph compute command
- graph list command
- graph show command

### Task 14: Create Baloto fixtures
**PR**: PR7
**Requirements**: REQ-10
**Decisions**: D-Fixture
**Description**: Create Baloto draw fixtures for testing
**Files**:
- create: backend/tests/fixtures/baloto_draws.json
**Estimated LOC**: ~50
**Dependencies**: None
**Verification**:
- Real Baloto draws
- Sufficient for co-occurrence/community/centrality testing

### Task 15: E2E acceptance tests
**PR**: PR7
**Requirements**: REQ-10, EC-01..06
**Decisions**: All
**Description**: End-to-end acceptance tests with Baloto oracle
**Files**:
- create: backend/tests/graph/test_graph_e2e.py
**Estimated LOC**: ~170
**Dependencies**: Tasks 11, 12, 13, 14
**Verification**:
- Baloto oracle deterministic
- Empty graph handling
- Disconnected graph handling
- Snapshot lifecycle

### Task 16: Documentation refresh
**PR**: PR7
**Requirements**: All
**Decisions**: All
**Description**: Refresh spec and README for graph engine
**Files**:
- modify: openspec/specs/graph-engine/spec.md
- modify: README.md
**Estimated LOC**: ~50
**Dependencies**: All
**Verification**:
- Spec reflects implementation
- README updated

## Gates Checklist

### Per PR Gate
- [ ] Byte-identical determinism
- [ ] Matrix symmetry (where applicable)
- [ ] No float in sensitive calculations
- [ ] Allowed centrality only (degree/closeness/betweenness)
- [ ] Deterministic modularity
- [ ] Fingerprint includes window params
- [ ] Migration up/down
- [ ] Snapshot lifecycle
- [ ] Empty DB acceptance
- [ ] Isolation from F3/F4/F5
- [ ] networkx/numpy/scipy banned
