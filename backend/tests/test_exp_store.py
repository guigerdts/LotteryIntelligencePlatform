"""Tests for ExpSnapshotStore persistence (EXP-001/002/004, NFR-EXP-03/005).

CRUD lifecycle, version monotonicity, fingerprint idempotency, lottery
isolation, and mark_failed.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.experiments.fingerprint import compute_exp_fingerprint
from backend.app.experiments.snapshot_store import ExpSnapshotStore
from backend.app.models.exp_experiment import ExpExperiment
from backend.app.models.lottery import Lottery

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_lottery(session: Session, lottery_id: int = 1) -> Lottery:
    """Seed a lottery row for FK references."""
    lottery = Lottery(
        code=f"L{lottery_id}",
        name=f"Lottery {lottery_id}",
        country="CO",
        min_number=1,
        max_number=50,
        numbers_to_select=5,
        super_number_min=1,
        super_number_max=16,
    )
    session.add(lottery)
    session.flush()
    return lottery


def _make_fingerprint(
    name: str = "test-exp",
    lottery_id: int = 1,
    config_json: str | None = None,
    description: str | None = None,
    status: str = "active",
) -> str:
    return compute_exp_fingerprint(
        name=name,
        lottery_id=lottery_id,
        config_json=config_json,
        description=description,
        status=status,
    )


def _create_experiment(
    session: Session,
    *,
    lottery_id: int = 1,
    name: str = "test-exp",
    status: str = "active",
    config_json: str | None = None,
    description: str | None = None,
) -> ExpExperiment:
    """Helper to create an experiment via the store."""
    store = ExpSnapshotStore(session)
    fp = _make_fingerprint(
        name=name,
        lottery_id=lottery_id,
        config_json=config_json,
        description=description,
        status=status,
    )
    version = store.next_version(lottery_id, name)
    return store.create(
        lottery_id=lottery_id,
        name=name,
        description=description,
        status=status,
        fingerprint=fp,
        version=version,
        config_json=config_json,
    )


# ---------------------------------------------------------------------------
# T-EXP-008: CRUD lifecycle
# ---------------------------------------------------------------------------


class TestCrudLifecycle:
    """EXP-001: create, get, update, list, retire lifecycle."""

    def test_create_and_get(self, db: Session) -> None:
        """Create an experiment and retrieve by ID."""
        _seed_lottery(db)
        exp = _create_experiment(db, lottery_id=1, name="crud-test")
        db.commit()

        store = ExpSnapshotStore(db)
        fetched = store.get(exp.id)
        assert fetched is not None
        assert fetched.id == exp.id
        assert fetched.name == "crud-test"
        assert fetched.lottery_id == 1
        assert fetched.status == "active"
        assert fetched.version == "1"

    def test_get_nonexistent_returns_none(self, db: Session) -> None:
        """get() returns None for a non-existent ID."""
        store = ExpSnapshotStore(db)
        assert store.get(99999) is None

    def test_update_fields(self, db: Session) -> None:
        """Update mutable fields on an existing experiment."""
        _seed_lottery(db)
        exp = _create_experiment(db, name="update-test")
        db.commit()

        store = ExpSnapshotStore(db)
        new_fp = _make_fingerprint(name="updated-name", lottery_id=1)
        store.update(
            exp,
            name="updated-name",
            description="new desc",
            fingerprint=new_fp,
            version="2",
        )
        db.commit()

        fetched = store.get(exp.id)
        assert fetched is not None
        assert fetched.name == "updated-name"
        assert fetched.description == "new desc"
        assert fetched.fingerprint == new_fp
        assert fetched.version == "2"

    def test_list_by_lottery(self, db: Session) -> None:
        """list_by_lottery returns experiments for the given lottery only."""
        _seed_lottery(db, 1)
        _seed_lottery(db, 2)
        _create_experiment(db, lottery_id=1, name="exp-a")
        _create_experiment(db, lottery_id=1, name="exp-b")
        _create_experiment(db, lottery_id=2, name="exp-c")
        db.commit()

        store = ExpSnapshotStore(db)
        results = store.list_by_lottery(1)
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"exp-a", "exp-b"}

    def test_list_by_lottery_with_status_filter(self, db: Session) -> None:
        """list_by_lottery filters by status when provided."""
        _seed_lottery(db)
        _create_experiment(db, lottery_id=1, name="active-exp")
        exp = _create_experiment(db, lottery_id=1, name="retired-exp")
        exp.status = "retired"
        db.commit()

        store = ExpSnapshotStore(db)
        active = store.list_by_lottery(1, status="active")
        assert len(active) == 1
        assert active[0].name == "active-exp"

        retired = store.list_by_lottery(1, status="retired")
        assert len(retired) == 1
        assert retired[0].name == "retired-exp"

    def test_list_by_lottery_ordered_desc(self, db: Session) -> None:
        """list_by_lottery orders by created_at DESC."""
        _seed_lottery(db)
        _create_experiment(db, lottery_id=1, name="first")
        _create_experiment(db, lottery_id=1, name="second")
        db.commit()

        store = ExpSnapshotStore(db)
        results = store.list_by_lottery(1)
        assert results[0].name == "second"
        assert results[1].name == "first"


# ---------------------------------------------------------------------------
# T-EXP-008: Version monotonicity
# ---------------------------------------------------------------------------


class TestVersionMonotonicity:
    """EXP-002: version increments monotonically per (lottery_id, name)."""

    def test_first_version_is_one(self, db: Session) -> None:
        """next_version returns '1' when no experiments exist for the scope."""
        store = ExpSnapshotStore(db)
        v = store.next_version(1, "new-exp")
        assert v == "1"

    def test_version_increments(self, db: Session) -> None:
        """next_version increments after each creation.

        Each experiment gets a different status to produce a different
        fingerprint (same fingerprint = idempotent → same row returned).
        """
        _seed_lottery(db)
        store = ExpSnapshotStore(db)
        assert store.next_version(1, "v-test") == "1"

        _create_experiment(db, lottery_id=1, name="v-test", status="active")
        db.commit()

        assert store.next_version(1, "v-test") == "2"

        # Different status → different fingerprint → unique constraint satisfied
        _create_experiment(db, lottery_id=1, name="v-test", status="retired")
        db.commit()

        assert store.next_version(1, "v-test") == "3"

    def test_version_scoped_per_name(self, db: Session) -> None:
        """Version is independent per (lottery_id, name) pair."""
        _seed_lottery(db)
        store = ExpSnapshotStore(db)
        _create_experiment(db, lottery_id=1, name="exp-a")
        _create_experiment(db, lottery_id=1, name="exp-b")
        db.commit()

        assert store.next_version(1, "exp-a") == "2"
        assert store.next_version(1, "exp-b") == "2"


# ---------------------------------------------------------------------------
# T-EXP-008: Fingerprint idempotency
# ---------------------------------------------------------------------------


class TestFingerprintIdempotency:
    """EXP-002/NFR-EXP-03: same fingerprint returns existing experiment."""

    def test_same_fingerprint_returns_existing(self, db: Session) -> None:
        """find_by_fingerprint returns the active experiment with that fingerprint."""
        _seed_lottery(db)
        exp = _create_experiment(db, name="fp-test")
        db.commit()

        store = ExpSnapshotStore(db)
        fp = _make_fingerprint(name="fp-test", lottery_id=1)
        found = store.find_by_fingerprint(fp)
        assert found is not None
        assert found.id == exp.id

    def test_different_fingerprint_returns_none(self, db: Session) -> None:
        """find_by_fingerprint returns None when no match."""
        _seed_lottery(db)
        _create_experiment(db, name="fp-test-2")
        db.commit()

        store = ExpSnapshotStore(db)
        found = store.find_by_fingerprint("nonexistent-fingerprint")
        assert found is None


# ---------------------------------------------------------------------------
# T-EXP-008: Lottery isolation
# ---------------------------------------------------------------------------


class TestLotteryIsolation:
    """NFR-EXP-05: experiments scoped per lottery; no cross-lottery contamination."""

    def test_lotteries_isolated(self, db: Session) -> None:
        """Experiments from different lotteries are invisible to each other."""
        _seed_lottery(db, 1)
        _seed_lottery(db, 2)
        _create_experiment(db, lottery_id=1, name="shared-name")
        _create_experiment(db, lottery_id=2, name="shared-name")
        db.commit()

        store = ExpSnapshotStore(db)
        l1 = store.list_by_lottery(1)
        l2 = store.list_by_lottery(2)
        assert len(l1) == 1
        assert len(l2) == 1
        assert l1[0].lottery_id == 1
        assert l2[0].lottery_id == 2

    def test_version_scoped_per_lottery(self, db: Session) -> None:
        """Version is independent per lottery."""
        _seed_lottery(db, 1)
        _seed_lottery(db, 2)
        store = ExpSnapshotStore(db)
        _create_experiment(db, lottery_id=1, name="v-test")
        _create_experiment(db, lottery_id=2, name="v-test")
        db.commit()

        assert store.next_version(1, "v-test") == "2"
        assert store.next_version(2, "v-test") == "2"


# ---------------------------------------------------------------------------
# T-EXP-008: mark_failed
# ---------------------------------------------------------------------------


class TestMarkFailed:
    """EXP-001: mark_failed transitions active → failed."""

    def test_mark_failed(self, db: Session) -> None:
        """mark_failed sets status to 'failed' for an active experiment."""
        _seed_lottery(db)
        exp = _create_experiment(db, name="fail-test")
        db.commit()

        store = ExpSnapshotStore(db)
        store.mark_failed(exp.id)
        db.commit()

        fetched = store.get(exp.id)
        assert fetched is not None
        assert fetched.status == "failed"

    def test_mark_failed_only_affects_active(self, db: Session) -> None:
        """mark_failed does not affect non-active experiments."""
        _seed_lottery(db)
        exp = _create_experiment(db, name="fail-inactive")
        exp.status = "retired"
        db.commit()

        store = ExpSnapshotStore(db)
        store.mark_failed(exp.id)
        db.commit()

        fetched = store.get(exp.id)
        assert fetched is not None
        assert fetched.status == "retired"


# ---------------------------------------------------------------------------
# Additional: dataclass and fingerprint tests
# ---------------------------------------------------------------------------


class TestExperimentConfig:
    """T-EXP-004: ExperimentConfig dataclass."""

    def test_default_params(self) -> None:
        from backend.app.experiments.types import ExperimentConfig

        cfg = ExperimentConfig()
        assert cfg.params == {}

    def test_custom_params(self) -> None:
        from backend.app.experiments.types import ExperimentConfig

        cfg = ExperimentConfig(params={"seed": 42, "epochs": 100})
        assert cfg.params["seed"] == 42
        assert cfg.params["epochs"] == 100


class TestComparisonResult:
    """T-EXP-004: ComparisonResult dataclass."""

    def test_default_fields(self) -> None:
        from backend.app.experiments.types import ComparisonResult

        cr = ComparisonResult(experiment_id=1)
        assert cr.experiment_id == 1
        assert cr.runs == []
        assert cr.metric_names == []


class TestVersionConstant:
    """T-EXP-005: version constant."""

    def test_version_equals_1_0_0(self) -> None:
        from backend.app.experiments.version import EXPERIMENT_GENERATOR_VERSION

        assert EXPERIMENT_GENERATOR_VERSION == "1.0.0"


class TestFingerprint:
    """T-EXP-006: fingerprint determinism and sensitivity."""

    def test_same_inputs_same_fingerprint(self) -> None:
        fp1 = _make_fingerprint(name="a", lottery_id=1)
        fp2 = _make_fingerprint(name="a", lottery_id=1)
        assert fp1 == fp2

    def test_different_name_different_fingerprint(self) -> None:
        fp1 = _make_fingerprint(name="a", lottery_id=1)
        fp2 = _make_fingerprint(name="b", lottery_id=1)
        assert fp1 != fp2

    def test_different_lottery_different_fingerprint(self) -> None:
        fp1 = _make_fingerprint(name="a", lottery_id=1)
        fp2 = _make_fingerprint(name="a", lottery_id=2)
        assert fp1 != fp2

    def test_different_config_different_fingerprint(self) -> None:
        fp1 = _make_fingerprint(name="a", lottery_id=1, config_json='{"seed": 1}')
        fp2 = _make_fingerprint(name="a", lottery_id=1, config_json='{"seed": 2}')
        assert fp1 != fp2

    def test_fingerprint_is_hex_64(self) -> None:
        fp = _make_fingerprint()
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


# ---------------------------------------------------------------------------
# Migration verification test
# ---------------------------------------------------------------------------


class TestMigrationTables:
    """Verify exp_* tables exist after migration."""

    def test_exp_experiments_table_exists(self, db: Session) -> None:
        """exp_experiments table is queryable."""
        result = db.execute(db.query(ExpExperiment).statement).fetchall()
        assert isinstance(result, list)

    def test_exp_runs_table_exists(self, db: Session) -> None:
        """exp_runs table is queryable."""
        from backend.app.models.exp_run import ExpRun

        result = db.execute(db.query(ExpRun).statement).fetchall()
        assert isinstance(result, list)

    def test_exp_comparisons_table_exists(self, db: Session) -> None:
        """exp_comparisons table is queryable."""
        from backend.app.models.exp_comparison import ExpComparison

        result = db.execute(db.query(ExpComparison).statement).fetchall()
        assert isinstance(result, list)
