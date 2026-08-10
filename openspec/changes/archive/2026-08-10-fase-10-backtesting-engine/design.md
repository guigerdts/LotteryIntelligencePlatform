# Design — Backtesting Engine (`fase-10-backtesting-engine`)

**Change**: `fase-10-backtesting-engine` · **Store**: `openspec` · **Date**: 2026-08-10
**Artifact**: design — technical architecture for the Backtesting Engine.

## 1. Module/Package Map

```
backend/src/backend/app/backtesting/
├── __init__.py              # Package seam (docstring only)
├── types.py                 # BacktestConfig, BacktestResult, MetricSet, DrawContext
├── fingerprint.py           # SHA-256 fingerprint computation (BTE-06)
├── determinism.py           # DeterminismContext, seed management, quantize_metric (BTE-05)
├── splitter.py              # WalkForwardSplitter — window construction (BTE-04, BTE-17)
├── metrics.py               # Lottery-specific metrics calculator (BTE-08)
├── benchmark.py             # UniformRandomBenchmark, HypergeometricBenchmark (BTE-09)
├── strategy.py              # StrategyProtocol, MLStrategyAdapter, DLStrategyAdapter (BTE-03)
├── engine.py                # BacktestEngine orchestrator (BTE-10, BTE-15)
├── snapshot_store.py        # BtSnapshotStore — bt_* I/O owner (BTE-10)
└── version.py               # BACKTEST_GENERATOR_VERSION constant

backend/src/backend/app/models/
├── bt_snapshot.py           # BtSnapshot ORM model
└── bt_result.py             # BtResult ORM model

backend/src/backend/app/services/
├── bt_service.py            # BtService composition root (BTS-04)

backend/src/backend/app/api/v1/
├── bt.py                    # API router (BTS-01)

backend/src/backend/app/schemas/
├── bt.py                    # Pydantic v2 schemas (BTS-03)

backend/alembic/versions/
├── 0012_bt_tables.py        # Migration (BTE-13)

backend/tests/bt/
├── __init__.py
├── test_types.py
├── test_fingerprint.py
├── test_determinism.py
├── test_splitter.py
├── test_metrics.py
├── test_benchmark.py
├── test_strategy.py
├── test_engine.py
├── test_snapshot_store.py
├── test_bt_service.py
├── test_bt_api.py
├── test_bt_cli.py
└── test_bt_e2e.py
```

## 2. Domain Types and Responsibilities

### `types.py`

```python
@dataclass(frozen=True)
class DrawContext:
    """Context for a single draw evaluation point (BTE-03)."""
    lottery_id: int
    draw_date: datetime
    historical_draws: list[Draw]  # expanding window, no future
    feature_set: dict | None = None

@dataclass(frozen=True)
class BacktestConfig:
    """Walk-forward configuration (BTE-04, BTE-18)."""
    train_years: int = 5
    eval_count: int = 1
    step_count: int = 1
    min_train_draws: int = 100
    seed: int = 42
    benchmark_type: str = "both"  # "uniform" | "hypergeometric" | "both"

@dataclass(frozen=True)
class MetricSet:
    """Lottery-specific metrics (BTE-08)."""
    hit_rate: Decimal          # percentage of draws with ≥k matches
    match_distribution: dict[int, int]  # k-of-n histogram
    average_matches: Decimal   # mean matches per draw
    consistency_score: Decimal # std dev of matches
    total_draws_evaluated: int

@dataclass(frozen=True)
class WindowResult:
    """Result of a single walk-forward window (BTE-15)."""
    window_index: int
    train_range: tuple[int, int]  # (start_idx, end_idx)
    eval_range: tuple[int, int]
    strategy_metrics: MetricSet
    uniform_metrics: MetricSet | None
    hypergeometric_metrics: MetricSet | None

@dataclass(frozen=True)
class BacktestResult:
    """Full backtest result (BTE-10)."""
    fingerprint: str
    lottery_id: int
    strategy_id: str
    status: str  # "active" | "retired" | "failed"
    aggregate_metrics: MetricSet
    window_history: list[WindowResult]
    snapshot_id: int | None = None
    version: str | None = None
```

### `version.py`

```python
BACKTEST_GENERATOR_VERSION: Final[str] = "1.0.0"
```

## 3. StrategyProtocol and Adapters

### `strategy.py`

```python
class StrategyProtocol(Protocol):
    """Generic strategy contract (BTE-03)."""
    
    @property
    def strategy_id(self) -> str: ...
    
    def predict(self, draw_context: DrawContext) -> list[int]: ...


class MLStrategyAdapter:
    """Adapts ML engine to StrategyProtocol (BTE-03, BTE-11)."""
    
    def __init__(self, ml_engine: Any, model_set: str = "core-5") -> None:
        self._engine = ml_engine
        self._model_set = model_set
    
    @property
    def strategy_id(self) -> str:
        return f"ml-{self._model_set}"
    
    def predict(self, draw_context: DrawContext) -> list[int]:
        # Lazy import to avoid module-level coupling (BTE-11)
        from backend.app.ml.engine import predict as ml_predict
        return ml_predict(self._engine, draw_context)


class DLStrategyAdapter:
    """Adapts DL engine to StrategyProtocol (BTE-03, BTE-11)."""
    
    def __init__(self, dl_engine: Any, model_set: str = "core-3") -> None:
        self._engine = dl_engine
        self._model_set = model_set
    
    @property
    def strategy_id(self) -> str:
        return f"dl-{self._model_set}"
    
    def predict(self, draw_context: DrawContext) -> list[int]:
        # Lazy import to avoid module-level coupling (BTE-11)
        from backend.app.dl.engine import predict as dl_predict
        return dl_predict(self._engine, draw_context)
```

**Isolation enforcement**: No module-level imports of `ml.*`, `dl.*`, `opt.*`, `services.*`, or `repositories.*` in `backtesting/`. Lazy imports inside functions only.

## 4. Walk-Forward Splitter

### `splitter.py`

```python
class WalkForwardSplitter:
    """Walk-forward window construction (BTE-04, BTE-17)."""
    
    def __init__(self, config: BacktestConfig) -> None:
        self._train_years = config.train_years
        self._eval_count = config.eval_count
        self._step_count = config.step_count
        self._min_train_draws = config.min_train_draws
    
    def split(self, draws: list[Draw]) -> list[Window]:
        """Generate walk-forward windows from sorted draws.
        
        Window construction:
        1. Sort draws by date ascending
        2. Convert train_years to draw count using median draws/year
        3. First window: train [0, train_count), eval [train_count, train_count+eval_count)
        4. Step forward by step_count, generate next window
        5. Continue until eval end exceeds available draws
        
        Temporal ordering (BTE-17):
        - All train draws have dates before all eval draws
        - No future data enters training
        
        First valid window:
        - train_count >= min_train_draws (BTE-07)
        
        Last valid window:
        - eval_range end <= len(draws)
        """
        ...
    
    def _validate_windows(self, windows: list[Window]) -> None:
        """Assert temporal ordering and no overlap (BTE-17)."""
        for w in windows:
            assert max(d.date for d in w.train_draws) < min(d.date for d in w.eval_draws)
```

### Window Construction Example

Given 10 years of draws, train_years=5, eval_count=1, step_count=1:
- Median ~52 draws/year → train_count ≈ 260
- Window 0: train [0, 260), eval [260, 261)
- Window 1: train [52, 312), eval [312, 313)
- ...
- Last window: eval end <= len(draws)

## 5. Backtest Engine Orchestration Flow

### `engine.py`

```python
class BacktestEngine:
    """Orchestrates walk-forward backtesting (BTE-10, BTE-15)."""
    
    def run(
        self,
        strategy: StrategyProtocol,
        draws: list[Draw],
        config: BacktestConfig,
        lottery_id: int,
    ) -> BacktestResult:
        """Execute backtest in one deterministic pass.
        
        Flow:
        1. Validate data floor (BTE-07)
        2. Initialize DeterminismContext with seed (BTE-05)
        3. Compute fingerprint (BTE-06)
        4. Generate walk-forward windows (BTE-04)
        5. For each window:
           a. Train strategy on train_draws (if applicable)
           b. Predict on eval_draws
           c. Compute strategy metrics (BTE-08)
           d. Compute uniform benchmark metrics (BTE-09)
           e. Compute hypergeometric benchmark metrics (BTE-09)
           f. Record WindowResult (BTE-15)
        6. Aggregate metrics across windows
        7. Return BacktestResult (BTE-10)
        """
        ...
```

## 6. Lottery-Specific Metric Calculation

### `metrics.py`

```python
class LotteryMetrics:
    """Lottery-specific metrics calculator (BTE-08)."""
    
    @staticmethod
    def compute(
        predictions: list[list[int]],
        actuals: list[list[int]],
        k_threshold: int = 1,
    ) -> MetricSet:
        """Compute metrics for a set of predictions vs actuals.
        
        Hit Rate: percentage of draws where ≥k numbers match
        Match Distribution: histogram of k-of-n matches (k=0,1,2,...,n)
        Average Matches: mean number of matches per draw
        Consistency Score: std dev of matches (lower = more consistent)
        Total Draws Evaluated: count of draws
        """
        ...
    
    @staticmethod
    def _count_matches(predicted: list[int], actual: list[int]) -> int:
        """Count matching numbers between predicted and actual."""
        return len(set(predicted) & set(actual))
```

## 7. Uniform Benchmark Implementation

### `benchmark.py`

```python
class UniformRandomBenchmark:
    """Uniform random baseline (BTE-09)."""
    
    def __init__(self, number_pool: range, pick_count: int, seed: int) -> None:
        self._pool = number_pool
        self._pick = pick_count
        self._rng = random.Random(seed)
    
    def predict(self, draw_context: DrawContext) -> list[int]:
        """Generate random prediction from uniform distribution."""
        return sorted(self._rng.sample(self._pool, self._pick))
```

## 8. F5 Hypergeometric Benchmark Integration

### `benchmark.py`

```python
class HypergeometricBenchmark:
    """F5 hypergeometric null-model (BTE-09)."""
    
    def __init__(self, lottery_id: int) -> None:
        self._lottery_id = lottery_id
    
    def predict(self, draw_context: DrawContext) -> list[int]:
        """Generate prediction based on F5 hypergeometric probabilities.
        
        Lazy import to avoid module-level coupling (BTE-11).
        """
        from backend.app.probability.engine import hypergeometric_sample
        # Use F5 engine to sample from hypergeometric distribution
        return hypergeometric_sample(self._lottery_id)
```

## 9. Benchmark Evaluation-Period Alignment

**BTE-16**: Both benchmarks use the exact same evaluation windows as the strategy.

```python
# In BacktestEngine.run():
for window in windows:
    # Strategy prediction
    strategy_preds = [strategy.predict(ctx) for ctx in window.eval_contexts]
    
    # Benchmarks use SAME evaluation period
    uniform_preds = [uniform.predict(ctx) for ctx in window.eval_contexts]
    hyper_preds = [hyper.predict(ctx) for ctx in window.eval_contexts]
    
    # All metrics computed on same actuals
    strategy_metrics = LotteryMetrics.compute(strategy_preds, actuals)
    uniform_metrics = LotteryMetrics.compute(uniform_preds, actuals)
    hyper_metrics = LotteryMetrics.compute(hyper_preds, actuals)
```

## 10. Determinism and Seed Propagation

### `determinism.py`

```python
class DeterminismContext:
    """Seed management for reproducibility (BTE-05)."""
    
    def __init__(self, seed: int) -> None:
        self._seed = seed
        self._numpy_rng = numpy.random.default_rng(seed)
        self._python_rng = random.Random(seed)
    
    def get_numpy_rng(self) -> numpy.random.Generator:
        return self._numpy_rng
    
    def get_python_rng(self) -> random.Random:
        return self._python_rng
    
    @staticmethod
    def quantize_metric(value: float) -> Decimal:
        """Quantize to Decimal(20,8) (BTE-08)."""
        return Decimal(str(value)).quantize(Decimal("0.00000001"))
```

**Seed propagation**: Seed passed to strategy predictions where applicable, benchmarks, and metrics calculation.

## 11. Fingerprint Construction

### `fingerprint.py`

```python
def compute_bt_fingerprint(
    strategy_id: str,
    config: BacktestConfig,
    data_hash: str,
    benchmark_type: str,
) -> str:
    """SHA-256 fingerprint (BTE-06, BTE-18).
    
    Inputs:
    - strategy_id
    - config JSON (train_years, eval_count, step_count, min_train_draws)
    - data_hash (SHA-256 of dataset checksum)
    - seed (from config)
    - benchmark_type
    - BACKTEST_GENERATOR_VERSION
    """
    payload = json.dumps({
        "strategy_id": strategy_id,
        "config": {
            "train_years": config.train_years,
            "eval_count": config.eval_count,
            "step_count": config.step_count,
            "min_train_draws": config.min_train_draws,
        },
        "data_hash": data_hash,
        "seed": config.seed,
        "benchmark_type": benchmark_type,
        "version": BACKTEST_GENERATOR_VERSION,
    }, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()
```

## 12. Convergence Tracking

**BTE-15**: Per-window evaluation history stored in `bt_results.window_history_json`.

```python
# In BacktestEngine.run():
window_history = []
for i, window in enumerate(windows):
    window_result = WindowResult(
        window_index=i,
        train_range=(window.train_start, window.train_end),
        eval_range=(window.eval_start, window.eval_end),
        strategy_metrics=strategy_metrics,
        uniform_metrics=uniform_metrics,
        hypergeometric_metrics=hyper_metrics,
    )
    window_history.append(window_result)
```

## 13. Snapshot Lifecycle and Atomic Persistence

### `snapshot_store.py`

```python
class BtSnapshotStore:
    """bt_* read/write owner (BTE-10)."""
    
    def __init__(self, session: Session) -> None:
        self._session = session
    
    def get_active(self, lottery_id: int, strategy_id: str) -> BtSnapshot | None:
        """Return active snapshot for (lottery_id, strategy_id)."""
        ...
    
    def find_by_fingerprint(self, fingerprint: str) -> BtSnapshot | None:
        """Return active snapshot matching fingerprint (idempotency)."""
        ...
    
    def next_version(self, lottery_id: int, strategy_id: str) -> str:
        """Return next monotonic version."""
        ...
    
    def create_active(
        self,
        *,
        lottery_id: int,
        strategy_id: str,
        fingerprint: str,
        version: str,
        aggregate_metrics: dict,
        window_history: list[dict],
    ) -> tuple[BtSnapshot, BtResult]:
        """Atomic write: retire old active → create new active (BTE-10).
        
        Single transaction:
        1. Retire existing active with same fingerprint
        2. Create new snapshot with status='active'
        3. Create result with metrics
        4. Commit
        """
        ...
```

**Lifecycle**:
- New run → `active` (atomic single-transaction write)
- Re-run with same fingerprint → old `active` → `retired`, new → `active`
- Error during run → `failed`

## 14. bt_snapshots / bt_results Data Model

### `bt_snapshot.py`

```python
class BtSnapshot(Base):
    __tablename__ = "bt_snapshots"
    
    id = Column(Integer, primary_key=True)
    lottery_id = Column(Integer, ForeignKey("lottery.id"), nullable=False)
    strategy_id = Column(String(100), nullable=False)
    fingerprint = Column(String(64), nullable=False, unique=True)
    version = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="active")  # active|retired|failed
    config_json = Column(Text, nullable=False)  # BacktestConfig JSON
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    results = relationship("BtResult", back_populates="snapshot")
```

### `bt_result.py`

```python
class BtResult(Base):
    __tablename__ = "bt_results"
    
    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("bt_snapshots.id"), nullable=False)
    aggregate_metrics_json = Column(Text, nullable=False)  # MetricSet JSON
    window_history_json = Column(Text, nullable=False)  # list[WindowResult] JSON
    created_at = Column(DateTime(timezone=True), default=func.now())
    
    # Relationships
    snapshot = relationship("BtSnapshot", back_populates="results")
```

## 15. Migration 0012 Upgrade/Downgrade

### `0012_bt_tables.py`

```python
def upgrade() -> None:
    """Create bt_snapshots and bt_results tables (BTE-13)."""
    op.create_table(
        "bt_snapshots",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("lottery_id", sa.Integer, sa.ForeignKey("lottery.id"), nullable=False),
        sa.Column("strategy_id", sa.String(100), nullable=False),
        sa.Column("fingerprint", sa.String(64), nullable=False, unique=True),
        sa.Column("version", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("config_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "bt_results",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("snapshot_id", sa.Integer, sa.ForeignKey("bt_snapshots.id"), nullable=False),
        sa.Column("aggregate_metrics_json", sa.Text, nullable=False),
        sa.Column("window_history_json", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_bt_snapshots_lottery_strategy", "bt_snapshots", ["lottery_id", "strategy_id"])
    op.create_index("ix_bt_snapshots_fingerprint", "bt_snapshots", ["fingerprint"])
    op.create_index("ix_bt_results_snapshot", "bt_results", ["snapshot_id"])

def downgrade() -> None:
    """Drop only bt_* tables (BTE-13)."""
    op.drop_table("bt_results")
    op.drop_table("bt_snapshots")
```

## 16. Service Layer Composition

### `bt_service.py`

```python
class BtService:
    """Composition root for backtesting (BTS-04)."""
    
    def __init__(
        self,
        session: Session,
        strategy: StrategyProtocol,
        *,
        lottery_id: int,
        config: BacktestConfig | None = None,
        version: str = "1.0.0",
        draw_count: int = 0,
    ) -> None:
        self._session = session
        self._strategy = strategy
        self._lottery_id = lottery_id
        self._config = config or BacktestConfig()
        self._version = version
        self._draw_count = draw_count
    
    def run(self) -> BacktestResult:
        """Execute backtest in one atomic transaction (BTS-04).
        
        Flow:
        1. Validate lottery exists (404 if not)
        2. Check data floor (InsufficientDataError if below) (BTE-07)
        3. Load draws
        4. Compute fingerprint (BTE-06)
        5. Check idempotency (return existing if active) (BTE-10)
        6. Run BacktestEngine with strategy + benchmarks
        7. Persist bt_* snapshot atomically (BTE-10)
        8. Return result
        """
        ...
```

## 17. API Routes

### `bt.py`

```python
router = APIRouter(prefix="/backtesting", tags=["backtesting"])

@router.post("/run", response_model=SuccessEnvelope[dict])
def run_backtest(
    lottery_id: int,
    db: DbSession,
    strategy_id: str = "ml-core-5",
    train_years: int = 5,
    eval_count: int = 1,
    seed: int = 42,
) -> SuccessEnvelope[dict]:
    """Trigger backtesting on demand (BTS-01).
    
    Resolves lottery by id (unknown → 404 RESOURCE_NOT_FOUND).
    Below data floor → InsufficientDataError.
    """
    ...

@router.get("/history", response_model=SuccessEnvelope[list])
def get_history(
    lottery_id: int,
    db: DbSession,
) -> SuccessEnvelope[list]:
    """List backtest runs for a lottery (BTS-01)."""
    ...

@router.get("/results", response_model=SuccessEnvelope[dict])
def get_results(
    lottery_id: int,
    db: DbSession,
    snapshot_id: int | None = None,
) -> SuccessEnvelope[dict]:
    """Get detailed backtest results (BTS-01)."""
    ...
```

## 18. CLI Commands

### `cli.py` additions

```python
# lip bt run
bt_run_parser = subparsers.add_parser("bt-run", help="run backtest")
bt_run_parser.add_argument("--lottery-id", required=True, type=int)
bt_run_parser.add_argument("--strategy", default="ml-core-5")
bt_run_parser.add_argument("--train-years", type=int, default=5)
bt_run_parser.add_argument("--eval-count", type=int, default=1)
bt_run_parser.add_argument("--seed", type=int, default=42)

# lip bt history
bt_history_parser = subparsers.add_parser("bt-history", help="backtest history")
bt_history_parser.add_argument("--lottery-id", required=True, type=int)

# lip bt results
bt_results_parser = subparsers.add_parser("bt-results", help="backtest results")
bt_results_parser.add_argument("--lottery-id", required=True, type=int)
bt_results_parser.add_argument("--snapshot-id", type=int)
```

## 19. Pydantic v2 Schemas

### `schemas/bt.py`

```python
class BacktestConfigSchema(BaseModel):
    train_years: int = 5
    eval_count: int = 1
    step_count: int = 1
    min_train_draws: int = 100
    seed: int = 42
    benchmark_type: str = "both"

class BacktestRequest(BaseModel):
    lottery_id: int
    strategy_id: str = "ml-core-5"
    config: BacktestConfigSchema | None = None

class MetricSetSchema(BaseModel):
    hit_rate: Decimal
    match_distribution: dict[int, int]
    average_matches: Decimal
    consistency_score: Decimal
    total_draws_evaluated: int

class BacktestResultSchema(BaseModel):
    fingerprint: str
    lottery_id: int
    strategy_id: str
    status: str
    aggregate_metrics: MetricSetSchema
    window_count: int
    snapshot_id: int | None = None
    version: str | None = None

class BacktestSummarySchema(BaseModel):
    snapshot_id: int
    strategy_id: str
    fingerprint: str
    version: str
    status: str
    created_at: datetime
```

## 20. Error Handling

### `services/errors.py` additions

```python
class InsufficientDataError(ServiceError):
    """Raised when data floor is not met (BTE-07)."""
    code = "INSUFFICIENT_DATA"
    status_code = 422
```

**Error mapping**:
- Lottery not found → 404 `RESOURCE_NOT_FOUND`
- Below data floor → 422 `INSUFFICIENT_DATA`
- Validation error → 422 `VALIDATION_ERROR`
- Training failure → 500 `training_error`

## 21. Multi-Lottery Isolation

**BTE-14**: Each lottery's backtest is isolated.
- bt_snapshots.lottery_id FK to lottery.id
- Queries always filter by lottery_id
- No cross-lottery reads in backtesting core

## 22. Read-Only Boundaries Against Other Engines

**BTE-02**: Backtesting MUST NOT modify any non-bt_* table.
- All writes target bt_* only
- Reads from lottery, draw, draw_numbers are passive
- No triggers, no hooks, no auto-computation

## 23. F10/F11/F13 Boundaries

| Concern | F10 Backtesting | F11 Experiment | F13 Generator |
|---------|-----------------|----------------|---------------|
| Goal | Evaluate strategies historically | Track/compare runs | Generate numbers |
| Input | Strategy + historical data | Experiment definitions | Strategies + constraints |
| Output | Single-run results | Cross-run comparison | Combinations |
| API | POST /bt/run | POST /exp/create | POST /gen/generate |
| CLI | lip bt ... | lip exp ... | lip gen ... |

**F10 owns**: single-run backtest results
**F11 owns**: experiment tracking, cross-run comparison, ranking
**F13 owns**: number generation, combination selection

## 24. Test Architecture and Requirement Traceability

| Requirement | Test File | Key Tests |
|-------------|-----------|-----------|
| BTE-01 | test_types.py | DrawContext, BacktestConfig, MetricSet creation |
| BTE-02 | test_engine.py | No non-bt_* writes |
| BTE-03 | test_strategy.py | StrategyProtocol compliance, adapter isolation |
| BTE-04 | test_splitter.py | Window construction, temporal ordering |
| BTE-05 | test_determinism.py | Seed reproducibility |
| BTE-06 | test_fingerprint.py | Fingerprint inputs, idempotency |
| BTE-07 | test_engine.py | Data floor enforcement |
| BTE-08 | test_metrics.py | Metric calculation accuracy |
| BTE-09 | test_benchmark.py | Uniform/hypergeometric reproducibility |
| BTE-10 | test_snapshot_store.py | Atomic lifecycle, idempotency |
| BTE-11 | test_strategy.py | No module-level imports |
| BTE-12 | test_bt_api.py | Manual-only, no predict/rank |
| BTE-13 | test_migration.py | Upgrade/downgrade |
| BTE-14 | test_bt_e2e.py | Multi-lottery isolation |
| BTE-15 | test_engine.py | Window history tracking |
| BTE-16 | test_benchmark.py | Same evaluation period |
| BTE-17 | test_splitter.py | Train-before-evaluate |
| BTE-18 | test_fingerprint.py | Config affects fingerprint |
| BTS-01 | test_bt_api.py | API endpoint behavior |
| BTS-02 | test_bt_cli.py | CLI parity |
| BTS-03 | test_bt_schemas.py | Pydantic validation |
| BTS-04 | test_bt_service.py | Service composition |

## 25. PR-by-PR Implementation Plan

### PR1: Foundation (~250 LOC impl)
**Files**: migration 0012, ORM models, types.py, version.py, test_types.py
**Requirements**: BTE-01, BTE-13
**Deliverables**:
- 0012_bt_tables.py (upgrade + downgrade)
- bt_snapshot.py, bt_result.py (ORM models)
- types.py (DrawContext, BacktestConfig, MetricSet, WindowResult, BacktestResult)
- version.py (BACKTEST_GENERATOR_VERSION)
- test_types.py

### PR2: Core Primitives (~300 LOC impl)
**Files**: fingerprint.py, determinism.py, splitter.py, strategy.py
**Requirements**: BTE-03, BTE-05, BTE-06, BTE-04, BTE-17, BTE-18
**Deliverables**:
- fingerprint.py (compute_bt_fingerprint)
- determinism.py (DeterminismContext, quantize_metric)
- splitter.py (WalkForwardSplitter)
- strategy.py (StrategyProtocol, MLStrategyAdapter, DLStrategyAdapter)
- test_fingerprint.py, test_determinism.py, test_splitter.py, test_strategy.py

### PR3: Metrics + Benchmarks (~350 LOC impl)
**Files**: metrics.py, benchmark.py
**Requirements**: BTE-08, BTE-09, BTE-16
**Deliverables**:
- metrics.py (LotteryMetrics)
- benchmark.py (UniformRandomBenchmark, HypergeometricBenchmark)
- test_metrics.py, test_benchmark.py

### PR4: Engine + Snapshot Store (~300 LOC impl)
**Files**: engine.py, snapshot_store.py
**Requirements**: BTE-02, BTE-10, BTE-15
**Deliverables**:
- engine.py (BacktestEngine)
- snapshot_store.py (BtSnapshotStore)
- test_engine.py, test_snapshot_store.py

### PR5: Service + API + CLI (~350 LOC impl)
**Files**: bt_service.py, bt.py (API), bt.py (schemas), cli.py additions
**Requirements**: BTS-01, BTS-02, BTS-03, BTS-04, BTE-12
**Deliverables**:
- bt_service.py (BtService)
- api/v1/bt.py (router)
- schemas/bt.py (Pydantic v2)
- cli.py additions (lip bt run|history|results)
- test_bt_service.py, test_bt_api.py, test_bt_cli.py

### PR6: E2E Tests + Docs (~200 LOC impl)
**Files**: test_bt_e2e.py, PROJECT_STATUS.md update
**Requirements**: BTE-14, all integration tests
**Deliverables**:
- test_bt_e2e.py (multi-lottery isolation, full workflow)
- PROJECT_STATUS.md update
- ruff check + format

**Total estimated LOC**: ~1,750 implementation LOC
**Total PRs**: 6 (all ≤400 LOC each)

## 26. Newly Discovered Architectural Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| F5 hypergeometric lazy import coupling | Low | Lazy import inside function; no module-level dependency |
| Walk-forward window edge cases | Medium | Comprehensive tests for first/last/empty windows |
| Metric calculation precision | Low | Decimal(20,8) quantization; tests against manual calculation |
| Benchmark performance with large datasets | Medium | Vectorized numpy/pandas; configurable window limits |

## 27. Integration Points with Existing F1-F9 Code

| Pattern | Source | Usage in F10 |
|---------|--------|--------------|
| Registry | F7/F8/F9 | Strategy registry (future extension) |
| Fingerprint SHA-256 | F9 | bt_* fingerprint |
| Determinism seed | F9 | DeterminismContext |
| Snapshot lifecycle | F3-F9 | bt_* active/retired/failed |
| Decimal(20,8) | F3-F9 | Metric quantization |
| InsufficientDataError | F9 | Data floor |
| API envelope | F0-F9 | {success, data, error, timestamp} |
| CLI pattern | F0-F9 | lip bt commands |
| Lazy imports | F9 | ML/DL adapters |

---

**Ready for tasks (sdd-tasks) upon confirmation.**
