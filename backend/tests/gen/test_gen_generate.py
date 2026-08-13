"""Tests for GenService.generate() — pipeline, determinism and GEN-013 errors.

Spec refs: GEN-001 (pipeline), GEN-002 (count), GEN-003 (selection), GEN-005
(determinism via isolated_rng), GEN-007 (lifecycle on generate), GEN-008
(idempotency), GEN-013 (error taxonomy), GEN-014 (no distribution). Design
refs: GenService section.
"""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from backend.app.generators.snapshot_store import GenSnapshotStore
from backend.app.models.gen_snapshot import GenSnapshot
from backend.app.services.errors import GenServiceError
from backend.app.services.gen_service import GenService


def _service(db: Session) -> GenService:
    """GenService bound to the migrated test session."""
    return GenService(db)


class TestGenerate:
    """generate() — full pipeline, count, determinism, idempotency."""

    def test_full_workflow_persists_active_snapshot(self, db: Session, seed_gen_data) -> None:
        """Selection→allocation→sample→persist produces exactly count combos (GEN-001)."""
        ids = seed_gen_data()
        result = _service(db).generate(lottery_id=ids["lottery_id"])
        assert result.status == "active"
        assert result.selection_id == ids["selection_id"]
        assert len(result.combinations) == 10  # default count (GEN-002)

        snapshot = db.get(GenSnapshot, result.snapshot_id)
        assert snapshot is not None
        assert snapshot.status == "active"
        stored = _service(db).get_combinations(ids["lottery_id"])
        assert len(stored.combinations) == 10
        for row in stored.combinations:
            assert len(row.numbers) == 6
            assert row.numbers == sorted(set(row.numbers))
            assert all(1 <= n <= 49 for n in row.numbers)

    def test_explicit_count(self, db: Session, seed_gen_data) -> None:
        """count=5 → exactly 5 combinations (NFR-GEN-02)."""
        ids = seed_gen_data()
        result = _service(db).generate(lottery_id=ids["lottery_id"], count=5)
        assert len(result.combinations) == 5

    def test_deterministic_same_inputs(self, db: Session, seed_gen_data) -> None:
        """Same inputs → identical output (NFR-GEN-01)."""
        ids = seed_gen_data()
        svc = _service(db)
        r1 = svc.generate(lottery_id=ids["lottery_id"])
        r2 = svc.generate(lottery_id=ids["lottery_id"])
        assert r1.fingerprint == r2.fingerprint
        assert [c.numbers for c in r1.combinations] == [c.numbers for c in r2.combinations]

    def test_seed_override_is_deterministic(self, db: Session, seed_gen_data) -> None:
        """seed=42 → reproducible across calls (GEN-009)."""
        ids = seed_gen_data()
        svc = _service(db)
        r1 = svc.generate(lottery_id=ids["lottery_id"], seed=42)
        r2 = svc.generate(lottery_id=ids["lottery_id"], seed=42)
        assert r1.snapshot_id == r2.snapshot_id
        assert [c.numbers for c in r1.combinations] == [c.numbers for c in r2.combinations]

    def test_idempotency_returns_existing(self, db: Session, seed_gen_data) -> None:
        """Same fingerprint → existing snapshot returned, no new rows (GEN-008)."""
        ids = seed_gen_data()
        svc = _service(db)
        first = svc.generate(lottery_id=ids["lottery_id"])
        second = svc.generate(lottery_id=ids["lottery_id"])
        assert second.snapshot_id == first.snapshot_id
        assert (
            db.query(GenSnapshot).filter(GenSnapshot.lottery_id == ids["lottery_id"]).count() == 1
        )

    def test_version_monotonic(self, db: Session, seed_gen_data) -> None:
        """New fingerprint → new version, old active retired (GEN-007)."""
        ids = seed_gen_data()
        svc = _service(db)
        first = svc.generate(lottery_id=ids["lottery_id"], seed=1)
        second = svc.generate(lottery_id=ids["lottery_id"], seed=2)
        assert int(second.version) > int(first.version)
        assert db.get(GenSnapshot, first.snapshot_id).status == "retired"
        assert db.get(GenSnapshot, second.snapshot_id).status == "active"

    def test_lottery_isolation(self, db: Session, seed_gen_data) -> None:
        """Snapshots are scoped per lottery (GEN-007)."""
        ids_a = seed_gen_data(context="A")
        ids_b = seed_gen_data(context="B")
        svc = _service(db)
        result_a = svc.generate(lottery_id=ids_a["lottery_id"])
        result_b = svc.generate(lottery_id=ids_b["lottery_id"])
        assert result_a.snapshot_id != result_b.snapshot_id
        assert (
            db.query(GenSnapshot).filter(GenSnapshot.lottery_id == ids_a["lottery_id"]).count() == 1
        )
        assert (
            db.query(GenSnapshot).filter(GenSnapshot.lottery_id == ids_b["lottery_id"]).count() == 1
        )

    def test_selection_override(self, db: Session, seed_gen_data) -> None:
        """selection_id override drives the generation (GEN-003)."""
        ids = seed_gen_data()
        result = _service(db).generate(
            lottery_id=ids["lottery_id"], selection_id=ids["selection_id"]
        )
        assert result.selection_id == ids["selection_id"]

    def test_selection_override_wrong_lottery(self, db: Session, seed_gen_data) -> None:
        """Override from another lottery → GEN_NO_SELECTION (GEN-003)."""
        ids_a = seed_gen_data(context="A")
        ids_b = seed_gen_data(context="B")
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).generate(
                lottery_id=ids_a["lottery_id"], selection_id=ids_b["selection_id"]
            )
        assert exc_info.value.code == GenServiceError.GEN_NO_SELECTION


class TestGenerateErrors:
    """generate() — GEN-013 error taxonomy."""

    @pytest.mark.parametrize("bad_count", [0, 101])
    def test_invalid_count_raises(self, db: Session, seed_gen_data, bad_count: int) -> None:
        """count outside [1,100] → GEN_COUNT_INVALID (GEN-002)."""
        ids = seed_gen_data()
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).generate(lottery_id=ids["lottery_id"], count=bad_count)
        assert exc_info.value.code == GenServiceError.GEN_COUNT_INVALID

    def test_lottery_not_found_raises(self, db: Session) -> None:
        """Unknown lottery → GEN_LOTTERY_NOT_FOUND (GEN-013)."""
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).generate(lottery_id=9999)
        assert exc_info.value.code == GenServiceError.GEN_LOTTERY_NOT_FOUND

    def test_no_selection_raises(self, db: Session, seed_gen_data) -> None:
        """No active F12 selection → GEN_NO_SELECTION (GEN-003, GEN-013)."""
        ids = seed_gen_data(selection_status="retired")
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).generate(lottery_id=ids["lottery_id"])
        assert exc_info.value.code == GenServiceError.GEN_NO_SELECTION

    def test_no_distribution_raises(self, db: Session, seed_gen_data) -> None:
        """No active F5 distribution → GEN_NO_DISTRIBUTION, zero combos (GEN-014)."""
        ids = seed_gen_data(with_distribution=False)
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).generate(lottery_id=ids["lottery_id"])
        assert exc_info.value.code == GenServiceError.GEN_NO_DISTRIBUTION
        assert (
            db.query(GenSnapshot).filter(GenSnapshot.lottery_id == ids["lottery_id"]).count() == 0
        )

    def test_space_exhausted_raises_zero_persisted(self, db: Session, seed_gen_data) -> None:
        """Tiny valid space → GEN_SPACE_EXHAUSTED, zero combos (GEN-013)."""
        ids = seed_gen_data(min_number=1, max_number=7, numbers_to_select=6, context="tiny")
        with pytest.raises(GenServiceError) as exc_info:
            _service(db).generate(lottery_id=ids["lottery_id"], count=10)
        assert exc_info.value.code == GenServiceError.GEN_SPACE_EXHAUSTED
        assert (
            db.query(GenSnapshot).filter(GenSnapshot.lottery_id == ids["lottery_id"]).count() == 0
        )

    def test_duplicate_snapshot_raises(self, db: Session, seed_gen_data) -> None:
        """Retired row already owning the fingerprint → GEN_DUPLICATE_SNAPSHOT (GEN-013)."""
        ids = seed_gen_data()
        svc = _service(db)
        first = svc.generate(lottery_id=ids["lottery_id"])
        # Retire the only active — its fingerprint is now a non-active duplicate.
        store = GenSnapshotStore(db)
        store.retire_active(ids["lottery_id"], ids["selection_id"])
        db.commit()
        with pytest.raises(GenServiceError) as exc_info:
            svc.generate(lottery_id=ids["lottery_id"])
        assert exc_info.value.code == GenServiceError.GEN_DUPLICATE_SNAPSHOT
        assert first.fingerprint in str(exc_info.value)
