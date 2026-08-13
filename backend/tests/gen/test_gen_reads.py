"""Tests for GenService reads and lifecycle — stored data, never recompute.

Spec refs: GEN-007 (lifecycle transitions), GEN-010 (stored reads),
GEN-013 (error taxonomy on reads). Design refs: GenService section.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.app.models.gen_snapshot import GenSnapshot
from backend.app.services.errors import GenServiceError
from backend.app.services.gen_service import GenService


def _service(db: Session) -> GenService:
    """GenService bound to the migrated test session."""
    return GenService(db)


class TestGetCombinations:
    """get_combinations() — stored reads, never recompute (GEN-010)."""

    def test_active_snapshot_by_default(self, db: Session, seed_gen_data) -> None:
        """Without snapshot_id → active snapshot combos."""
        ids = seed_gen_data()
        generated = _service(db).generate(lottery_id=ids["lottery_id"])
        result = _service(db).get_combinations(ids["lottery_id"])
        assert result.snapshot_id == generated.snapshot_id
        assert len(result.combinations) == 10

    def test_by_snapshot_id(self, db: Session, seed_gen_data) -> None:
        """With snapshot_id → that snapshot's combos."""
        ids = seed_gen_data()
        svc = _service(db)
        generated = svc.generate(lottery_id=ids["lottery_id"])
        result = svc.get_combinations(ids["lottery_id"], snapshot_id=generated.snapshot_id)
        assert result.snapshot_id == generated.snapshot_id

    def test_unknown_snapshot_raises(self, db: Session, seed_gen_data) -> None:
        """Unknown snapshot_id → GEN_SNAPSHOT_NOT_FOUND."""
        ids = seed_gen_data()
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).get_combinations(ids["lottery_id"], snapshot_id=9999)
        assert exc_info.value.code == GenServiceError.GEN_SNAPSHOT_NOT_FOUND

    def test_no_active_snapshot_raises(self, db: Session, seed_gen_data) -> None:
        """No active snapshot → GEN_SNAPSHOT_NOT_FOUND."""
        ids = seed_gen_data()
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).get_combinations(ids["lottery_id"])
        assert exc_info.value.code == GenServiceError.GEN_SNAPSHOT_NOT_FOUND

    def test_unknown_lottery_raises(self, db: Session) -> None:
        """Unknown lottery → GEN_LOTTERY_NOT_FOUND."""
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).get_combinations(9999)
        assert exc_info.value.code == GenServiceError.GEN_LOTTERY_NOT_FOUND


class TestUpdateSnapshot:
    """update_snapshot() — lifecycle transitions (GEN-007)."""

    def test_retire_snapshot(self, db: Session, seed_gen_data) -> None:
        """Transition to 'retired' persists."""
        ids = seed_gen_data()
        generated = _service(db).generate(lottery_id=ids["lottery_id"])
        result = _service(db).update_snapshot(ids["lottery_id"], generated.snapshot_id, "retired")
        assert result.status == "retired"
        assert db.get(GenSnapshot, generated.snapshot_id).status == "retired"

    def test_fail_snapshot(self, db: Session, seed_gen_data) -> None:
        """Transition to 'failed' persists."""
        ids = seed_gen_data()
        generated = _service(db).generate(lottery_id=ids["lottery_id"])
        result = _service(db).update_snapshot(ids["lottery_id"], generated.snapshot_id, "failed")
        assert result.status == "failed"

    def test_activate_raises_duplicate(self, db: Session, seed_gen_data) -> None:
        """Activation → GEN_DUPLICATE_SNAPSHOT (409)."""
        ids = seed_gen_data()
        generated = _service(db).generate(lottery_id=ids["lottery_id"])
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).update_snapshot(ids["lottery_id"], generated.snapshot_id, "active")
        assert exc_info.value.code == GenServiceError.GEN_DUPLICATE_SNAPSHOT

    def test_unknown_snapshot_raises(self, db: Session, seed_gen_data) -> None:
        """Unknown snapshot → GEN_SNAPSHOT_NOT_FOUND."""
        ids = seed_gen_data()
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).update_snapshot(ids["lottery_id"], 9999, "retired")
        assert exc_info.value.code == GenServiceError.GEN_SNAPSHOT_NOT_FOUND


class TestGetSnapshots:
    """get_snapshots() — list stored snapshots (GEN-010)."""

    def test_lists_snapshots(self, db: Session, seed_gen_data) -> None:
        """Generated snapshots are listed ordered by version DESC."""
        ids = seed_gen_data()
        svc = _service(db)
        svc.generate(lottery_id=ids["lottery_id"], seed=1)
        svc.generate(lottery_id=ids["lottery_id"], seed=2)
        result = svc.get_snapshots(ids["lottery_id"])
        assert len(result.snapshots) == 2
        assert int(result.snapshots[0].version) > int(result.snapshots[1].version)

    def test_empty_raises(self, db: Session, seed_gen_data) -> None:
        """No snapshots → GEN_SNAPSHOT_NOT_FOUND."""
        ids = seed_gen_data()
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).get_snapshots(ids["lottery_id"])
        assert exc_info.value.code == GenServiceError.GEN_SNAPSHOT_NOT_FOUND
