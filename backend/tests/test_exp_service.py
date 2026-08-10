"""Tests for ExpService (EXP-001/002/003/004)."""

import pytest

from backend.app.models.lottery import Lottery
from backend.app.services.errors import (
    ExperimentError,
    ExperimentNotFoundError,
    NotFoundError,
    ValidationError,
)
from backend.app.services.exp_service import ExpService


@pytest.fixture
def seeded_lottery(db):
    """Seed a lottery row for FK compliance."""
    lottery = Lottery(
        id=1,
        code="TEST",
        name="Test Lottery",
        country="US",
        min_number=1,
        max_number=50,
        numbers_to_select=5,
    )
    db.add(lottery)
    db.commit()
    return lottery


class TestExpServiceCreate:
    """Test ExpService.create() method."""

    def test_create_experiment(self, db, seeded_lottery):
        """Create an experiment and verify it returns correct data."""
        service = ExpService(db)
        outcome = service.create(
            lottery_id=1,
            name="Test Experiment",
            description="A test experiment",
            config_json='{"param": "value"}',
        )

        assert outcome.lottery_id == 1
        assert outcome.name == "Test Experiment"
        assert outcome.status == "active"
        assert outcome.version == "1"
        assert len(outcome.fingerprint) == 64  # SHA-256 hex digest

    def test_create_experiment_idempotent(self, db, seeded_lottery):
        """Creating the same experiment twice returns the same result."""
        service = ExpService(db)
        outcome1 = service.create(
            lottery_id=1,
            name="Idempotent Experiment",
            description="Test idempotency",
        )
        outcome2 = service.create(
            lottery_id=1,
            name="Idempotent Experiment",
            description="Test idempotency",
        )

        assert outcome1.experiment_id == outcome2.experiment_id
        assert outcome1.fingerprint == outcome2.fingerprint

    def test_create_experiment_duplicate_name_different_fingerprint(self, db, seeded_lottery):
        """Creating experiment with same name but different fingerprint fails."""
        service = ExpService(db)
        service.create(
            lottery_id=1,
            name="Duplicate Name",
            description="First version",
        )

        with pytest.raises(ExperimentError) as exc_info:
            service.create(
                lottery_id=1,
                name="Duplicate Name",
                description="Second version",  # Different description = different fingerprint
            )
        assert exc_info.value.code == "DUPLICATE_EXPERIMENT"

    def test_create_experiment_invalid_lottery(self, db):
        """Creating experiment with non-existent lottery fails."""
        service = ExpService(db)
        with pytest.raises(NotFoundError):
            service.create(lottery_id=999, name="Invalid Lottery")


class TestExpServiceGet:
    """Test ExpService.get() method."""

    def test_get_experiment(self, db, seeded_lottery):
        """Get an experiment by ID."""
        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Get Test")

        entry = service.get(outcome.experiment_id)
        assert entry.experiment_id == outcome.experiment_id
        assert entry.name == "Get Test"
        assert entry.status == "active"

    def test_get_nonexistent_experiment(self, db):
        """Getting non-existent experiment raises ExperimentNotFoundError."""
        service = ExpService(db)
        with pytest.raises(ExperimentNotFoundError):
            service.get(999)


class TestExpServiceUpdate:
    """Test ExpService.update() method."""

    def test_update_experiment(self, db, seeded_lottery):
        """Update experiment fields."""
        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Update Test")

        updated = service.update(
            outcome.experiment_id,
            description="Updated description",
        )

        assert updated.experiment_id == outcome.experiment_id
        assert updated.version == "2"  # Version incremented
        assert updated.fingerprint != outcome.fingerprint  # Fingerprint changed

    def test_update_experiment_idempotent(self, db, seeded_lottery):
        """Updating with same values is idempotent."""
        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Idempotent Update")

        updated = service.update(
            outcome.experiment_id,
            name="Idempotent Update",  # Same name
        )

        assert updated.version == outcome.version  # Version unchanged
        assert updated.fingerprint == outcome.fingerprint  # Fingerprint unchanged

    def test_update_retired_experiment(self, db, seeded_lottery):
        """Updating retired experiment raises ExperimentError."""
        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Retired Update")
        service.retire(outcome.experiment_id)

        with pytest.raises(ExperimentError) as exc_info:
            service.update(outcome.experiment_id, description="Should fail")
        assert exc_info.value.code == "EXPERIMENT_RETIRED"

    def test_update_experiment_invalid_status(self, db, seeded_lottery):
        """Updating with invalid status raises ValidationError."""
        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Invalid Status")

        with pytest.raises(ValidationError):
            service.update(outcome.experiment_id, status="invalid")


class TestExpServiceRetire:
    """Test ExpService.retire() method."""

    def test_retire_experiment(self, db, seeded_lottery):
        """Retire an experiment."""
        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Retire Test")

        retired = service.retire(outcome.experiment_id)
        assert retired.status == "retired"
        assert retired.version == "2"


class TestExpServiceAddRun:
    """Test ExpService.add_run() method."""

    def test_add_run_to_active_experiment(self, db, seeded_lottery):
        """Add a run to an active experiment."""
        # Create a bt_snapshot first
        from backend.app.models.bt_snapshot import BtSnapshot

        snapshot = BtSnapshot(
            lottery_id=1,
            strategy_id="test-strategy",
            fingerprint="abc123",
            version="1",
            status="active",
            config_json="{}",  # Required field
        )
        db.add(snapshot)
        db.flush()

        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Run Test")

        run = service.add_run(
            outcome.experiment_id,
            run_label="baseline",
            engine_type="backtesting",
            engine_snapshot_id=snapshot.id,
            notes="Initial run",
        )

        assert run.run_id is not None
        assert run.engine_fingerprint == "abc123"

    def test_add_run_to_retired_experiment(self, db, seeded_lottery):
        """Adding run to retired experiment raises ExperimentError."""
        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Retired Run")
        service.retire(outcome.experiment_id)

        with pytest.raises(ExperimentError) as exc_info:
            service.add_run(
                outcome.experiment_id,
                run_label="should-fail",
                engine_type="backtesting",
                engine_snapshot_id=1,
            )
        assert exc_info.value.code == "EXPERIMENT_RETIRED"

    def test_add_run_invalid_engine_type(self, db, seeded_lottery):
        """Adding run with invalid engine type raises ValidationError."""
        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Invalid Engine")

        with pytest.raises(ValidationError):
            service.add_run(
                outcome.experiment_id,
                run_label="should-fail",
                engine_type="invalid",
                engine_snapshot_id=1,
            )

    def test_add_run_nonexistent_snapshot(self, db, seeded_lottery):
        """Adding run with non-existent snapshot raises ExpSnapshotNotFoundError."""
        from backend.app.services.errors import ExpSnapshotNotFoundError

        service = ExpService(db)
        outcome = service.create(lottery_id=1, name="Missing Snapshot")

        with pytest.raises(ExpSnapshotNotFoundError) as exc_info:
            service.add_run(
                outcome.experiment_id,
                run_label="should-fail",
                engine_type="backtesting",
                engine_snapshot_id=999,
            )
        assert exc_info.value.code == "SNAPSHOT_NOT_FOUND"


class TestExpServiceList:
    """Test ExpService.list_experiments() method."""

    def test_list_experiments(self, db, seeded_lottery):
        """List experiments for a lottery."""
        service = ExpService(db)
        service.create(lottery_id=1, name="List Test 1")
        service.create(lottery_id=1, name="List Test 2")

        entries = service.list_experiments(lottery_id=1)
        assert len(entries) == 2
        assert entries[0].name == "List Test 2"  # Ordered by created_at DESC
        assert entries[1].name == "List Test 1"

    def test_list_experiments_with_status_filter(self, db, seeded_lottery):
        """List experiments filtered by status."""
        service = ExpService(db)
        service.create(lottery_id=1, name="Active Exp")
        outcome = service.create(lottery_id=1, name="Retired Exp")
        service.retire(outcome.experiment_id)

        active_entries = service.list_experiments(lottery_id=1, status="active")
        retired_entries = service.list_experiments(lottery_id=1, status="retired")

        assert len(active_entries) == 1
        assert len(retired_entries) == 1
        assert active_entries[0].name == "Active Exp"
        assert retired_entries[0].name == "Retired Exp"

    def test_list_experiments_empty_lottery(self, db, seeded_lottery):
        """List experiments for lottery with no experiments."""
        service = ExpService(db)
        entries = service.list_experiments(lottery_id=1)
        assert entries == []

    def test_list_experiments_invalid_lottery(self, db):
        """List experiments for non-existent lottery raises NotFoundError."""
        service = ExpService(db)
        with pytest.raises(NotFoundError):
            service.list_experiments(lottery_id=999)
