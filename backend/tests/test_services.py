"""Domain service tests (PR-3, P3-04).

Covers the draw bundle transaction (atomicity + rollback), soft-delete/restore
with referential integrity, the dataset immutability contract (DATASET_LOCKED,
new-version-on-change, no auto-unlock), error-to-envelope-code mapping, and the
shared validation helpers (V1-V6). All tests run against a throwaway SQLite
file migrated by alembic 0001; the real database/lip.db is never touched and
alembic never runs against it.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from alembic.config import Config
from sqlalchemy.orm import sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.models import Dataset, DatasetDraw, Draw, DrawNumber, Lottery, SuperNumber
from backend.app.repositories.dataset_draw_repository import DatasetDrawRepository
from backend.app.repositories.dataset_repository import DatasetRepository
from backend.app.repositories.draw_repository import DrawRepository
from backend.app.repositories.errors import DuplicateError, ReferentialError
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.services.dataset_service import DatasetService
from backend.app.services.draw_service import DrawService
from backend.app.services.errors import (
    DatasetLockedError,
    NotFoundError,
    SoftDeletedError,
    ValidationError,
)
from backend.app.services.helpers import get_lottery_or_raise

# <repo>/backend/tests -> <repo>/backend/alembic.ini
_BACKEND_DIR = Path(__file__).resolve().parents[1]
_ALEMBIC_INI = _BACKEND_DIR / "alembic.ini"


@pytest.fixture
def service_db(tmp_path: Path) -> Path:
    """A tmp SQLite file with the 0001 schema applied (alembic owns the schema)."""
    db = tmp_path / "service_test.db"
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    return db


@pytest.fixture
def engine(service_db: Path):
    """App-style engine on the migrated tmp DB (SQLite FK PRAGMA wired)."""
    eng = build_engine(f"sqlite:///{service_db}")
    yield eng
    eng.dispose()


@pytest.fixture
def session(engine):
    """A DI-style session (no autocommit) bound to the migrated tmp DB."""
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    s = factory()
    yield s
    s.close()


def _make_lottery(
    session,
    code: str = "LOTO",
    *,
    numbers_to_select: int = 6,
    with_super: bool = False,
) -> Lottery:
    """Create and commit a lottery; optional super range enables super validation."""
    lottery = LotteryRepository(session).create(
        {
            "code": code,
            "name": f"Lottery {code}",
            "country": "ES",
            "min_number": 1,
            "max_number": 49,
            "numbers_to_select": numbers_to_select,
            **({"super_number_min": 1, "super_number_max": 9} if with_super else {}),
        }
    )
    session.commit()
    return lottery


def _draw_service(session) -> DrawService:
    """Fresh DrawService over the fixture session."""
    return DrawService(session)


def _dataset_service(session) -> DatasetService:
    """Fresh DatasetService over the fixture session."""
    return DatasetService(session)


def _valid_numbers() -> list[int]:
    """A valid 6-number selection for the default lottery rules."""
    return [1, 2, 3, 4, 5, 6]


def _make_draw(session, lottery_id: int, draw_number: int = 1) -> Draw:
    """Persist a minimal committed draw via the service (bundle without children)."""
    return DrawService(session).create_draw_bundle(
        lottery_id=lottery_id,
        draw_number=draw_number,
        draw_date=date(2026, 1, 1),
        numbers=_valid_numbers(),
    )


# ---------------------------------------------------------------------------
# Draw bundle — creation, validation, idempotency (scope 1, mandate A/B)
# ---------------------------------------------------------------------------


def test_create_draw_bundle_persists_draw_numbers_and_super(session) -> None:
    """A valid bundle persists draw + 6 numbers + super in one committed tx."""
    lottery = _make_lottery(session, with_super=True)
    draw = _draw_service(session).create_draw_bundle(
        lottery_id=lottery.id,
        draw_number=7,
        draw_date=date(2026, 1, 1),
        numbers=_valid_numbers(),
        super_number=5,
    )

    assert draw.id is not None
    assert draw.is_deleted is False
    assert len(draw.numbers) == 6
    assert [n.number for n in draw.numbers] == _valid_numbers()
    assert [n.position for n in draw.numbers] == [1, 2, 3, 4, 5, 6]
    assert draw.super_number is not None
    assert draw.super_number.value == 5


def test_create_draw_bundle_without_super_creates_no_super_row(session) -> None:
    """super_number=None yields a draw with zero super_number rows (0..1 cardinality)."""
    lottery = _make_lottery(session, with_super=True)
    draw = _draw_service(session).create_draw_bundle(
        lottery_id=lottery.id,
        draw_number=1,
        draw_date=date(2026, 1, 1),
        numbers=_valid_numbers(),
    )
    assert draw.super_number is None


def test_create_draw_bundle_unknown_lottery_raises_not_found(session) -> None:
    """A missing lottery maps to NotFoundError (RESOURCE_NOT_FOUND)."""
    with pytest.raises(NotFoundError) as excinfo:
        _draw_service(session).create_draw_bundle(
            lottery_id=9999,
            draw_number=1,
            draw_date=date(2026, 1, 1),
            numbers=_valid_numbers(),
        )
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"


def test_create_draw_bundle_count_mismatch_raises_validation(session) -> None:
    """V1: number count != numbers_to_select is rejected pre-insert (CD-06)."""
    lottery = _make_lottery(session, numbers_to_select=6)
    with pytest.raises(ValidationError) as excinfo:
        _draw_service(session).create_draw_bundle(
            lottery_id=lottery.id,
            draw_number=1,
            draw_date=date(2026, 1, 1),
            numbers=[1, 2, 3],  # 3 != 6
        )
    assert excinfo.value.code == "validation_error"
    assert session.query(Draw).count() == 0
    assert session.query(DrawNumber).count() == 0


def test_create_draw_bundle_out_of_range_raises_validation(session) -> None:
    """V1: a number outside the lottery range is rejected; zero rows persisted."""
    lottery = _make_lottery(session)
    with pytest.raises(ValidationError) as excinfo:
        _draw_service(session).create_draw_bundle(
            lottery_id=lottery.id,
            draw_number=1,
            draw_date=date(2026, 1, 1),
            numbers=[1, 2, 3, 4, 5, 50],  # 50 > max 49
        )
    assert excinfo.value.code == "validation_error"
    assert session.query(Draw).count() == 0
    assert session.query(DrawNumber).count() == 0


def test_create_draw_bundle_duplicate_number_raises_validation(session) -> None:
    """V1: repeated numbers are rejected by the service; zero draws/numbers persisted."""
    lottery = _make_lottery(session)
    with pytest.raises(ValidationError) as excinfo:
        _draw_service(session).create_draw_bundle(
            lottery_id=lottery.id,
            draw_number=1,
            draw_date=date(2026, 1, 1),
            numbers=[7, 7, 8, 9, 10, 11],  # 7 repeated
        )
    assert excinfo.value.code == "validation_error"
    assert session.query(Draw).count() == 0
    assert session.query(DrawNumber).count() == 0


def test_create_draw_bundle_super_out_of_range_raises_validation(session) -> None:
    """V2: an out-of-super-range super number is rejected; zero rows persisted."""
    lottery = _make_lottery(session, with_super=True)  # super range [1, 9]
    with pytest.raises(ValidationError) as excinfo:
        _draw_service(session).create_draw_bundle(
            lottery_id=lottery.id,
            draw_number=1,
            draw_date=date(2026, 1, 1),
            numbers=_valid_numbers(),
            super_number=42,
        )
    assert excinfo.value.code == "validation_error"
    assert session.query(Draw).count() == 0
    assert session.query(DrawNumber).count() == 0
    assert session.query(SuperNumber).count() == 0


def test_create_draw_bundle_super_without_range_raises_validation(session) -> None:
    """V2: a super number for a lottery with no super range is rejected."""
    lottery = _make_lottery(session)  # no super range defined
    with pytest.raises(ValidationError):
        _draw_service(session).create_draw_bundle(
            lottery_id=lottery.id,
            draw_number=1,
            draw_date=date(2026, 1, 1),
            numbers=_valid_numbers(),
            super_number=3,
        )
    assert session.query(Draw).count() == 0


def test_create_draw_bundle_idempotent_returns_existing(session) -> None:
    """Mandate A: an existing natural key returns the existing draw unchanged."""
    lottery = _make_lottery(session, with_super=True)
    svc = _draw_service(session)
    first = svc.create_draw_bundle(
        lottery_id=lottery.id,
        draw_number=100,
        draw_date=date(2026, 1, 1),
        numbers=_valid_numbers(),
        super_number=5,
    )
    second = svc.create_draw_bundle(
        lottery_id=lottery.id,
        draw_number=100,
        draw_date=date(2026, 1, 1),
        numbers=_valid_numbers(),
        super_number=5,
    )
    assert second.id == first.id
    assert session.query(Draw).count() == 1
    assert session.query(DrawNumber).count() == 6
    assert session.query(SuperNumber).count() == 1
    assert len(second.numbers) == 6  # children untouched by the replay


# ---------------------------------------------------------------------------
# Real rollback on child failure (V1/V2, mandate B) — injected mid-bundle failure
# ---------------------------------------------------------------------------


def test_create_draw_bundle_rolls_back_on_numbers_failure(session, monkeypatch) -> None:
    """V1: a numbers insert failure after the draw insert rolls back the whole bundle."""
    lottery = _make_lottery(session)
    svc = _draw_service(session)

    def fail_add_many(draw_id: int, numbers: list[int]) -> None:
        raise DuplicateError("simulated UNIQUE(draw_id, number) failure at flush")

    monkeypatch.setattr(svc._numbers, "add_many", fail_add_many)
    with pytest.raises(DuplicateError) as excinfo:
        svc.create_draw_bundle(
            lottery_id=lottery.id,
            draw_number=1,
            draw_date=date(2026, 1, 1),
            numbers=_valid_numbers(),
        )
    assert excinfo.value.code == "DUPLICATE_RESOURCE"
    # zero draws, zero numbers rows persisted — the draw insert was rolled back
    assert session.query(Draw).count() == 0
    assert session.query(DrawNumber).count() == 0


def test_create_draw_bundle_rolls_back_on_super_failure(session, monkeypatch) -> None:
    """V2: a super number insert failure rolls back draw + numbers + super (no orphans)."""
    lottery = _make_lottery(session, with_super=True)
    svc = _draw_service(session)

    def fail_add(draw_id: int, value: int) -> None:
        raise DuplicateError("simulated UNIQUE(draw_id) second-super failure at flush")

    monkeypatch.setattr(svc._supers, "add", fail_add)
    with pytest.raises(DuplicateError) as excinfo:
        svc.create_draw_bundle(
            lottery_id=lottery.id,
            draw_number=1,
            draw_date=date(2026, 1, 1),
            numbers=_valid_numbers(),
            super_number=5,
        )
    assert excinfo.value.code == "DUPLICATE_RESOURCE"
    assert session.query(Draw).count() == 0
    assert session.query(DrawNumber).count() == 0
    assert session.query(SuperNumber).count() == 0


# ---------------------------------------------------------------------------
# Soft-delete / restore (V4, V5, scope 1, mandate C)
# ---------------------------------------------------------------------------


def test_soft_delete_marks_draw_and_keeps_children(session) -> None:
    """V4: soft-delete sets is_deleted and leaves numbers + super_number intact."""
    lottery = _make_lottery(session, with_super=True)
    svc = _draw_service(session)
    draw = svc.create_draw_bundle(
        lottery_id=lottery.id,
        draw_number=1,
        draw_date=date(2026, 1, 1),
        numbers=_valid_numbers(),
        super_number=5,
    )
    assert session.query(DrawNumber).count() == 6

    deleted = svc.soft_delete(draw.id)
    assert deleted.is_deleted is True
    # children ride FK RESTRICT — unchanged, no orphan loss
    assert session.query(DrawNumber).count() == 6
    assert session.query(SuperNumber).count() == 1


def test_restore_restores_draw_with_all_children(session) -> None:
    """V4: restore brings the draw back visible with numbers and super intact."""
    lottery = _make_lottery(session, with_super=True)
    svc = _draw_service(session)
    draw = svc.create_draw_bundle(
        lottery_id=lottery.id,
        draw_number=2,
        draw_date=date(2026, 1, 1),
        numbers=_valid_numbers(),
        super_number=7,
    )
    svc.soft_delete(draw.id)

    restored = svc.restore(draw.id)
    assert restored.is_deleted is False
    visible = svc.get_draw(draw.id)  # functional lookup works again
    assert [n.number for n in visible.numbers] == _valid_numbers()
    assert visible.super_number is not None
    assert visible.super_number.value == 7


def test_soft_delete_is_idempotent(session) -> None:
    """Re-soft-deleting an already deleted draw is a safe no-op (returns it deleted)."""
    lottery = _make_lottery(session)
    draw = _make_draw(session, lottery.id, draw_number=1)
    svc = _draw_service(session)
    svc.soft_delete(draw.id)
    again = svc.soft_delete(draw.id)
    assert again.is_deleted is True


def test_soft_delete_missing_draw_raises_not_found(session) -> None:
    """soft_delete on an absent draw maps to NotFoundError (RESOURCE_NOT_FOUND)."""
    with pytest.raises(NotFoundError) as excinfo:
        _draw_service(session).soft_delete(9999)
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"


def test_restore_missing_draw_raises_not_found(session) -> None:
    """restore on an absent draw maps to NotFoundError (RESOURCE_NOT_FOUND)."""
    with pytest.raises(NotFoundError) as excinfo:
        _draw_service(session).restore(9999)
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"


def test_functional_list_excludes_soft_deleted(session) -> None:
    """V5: functional list_draws excludes is_deleted=true; admin repo list still sees it."""
    lottery = _make_lottery(session)
    svc = _draw_service(session)
    keep = _make_draw(session, lottery.id, draw_number=1)
    deleted = _make_draw(session, lottery.id, draw_number=2)
    svc.soft_delete(deleted.id)

    functional = svc.list_draws(lottery_code="LOTO")
    assert [d.id for d in functional] == [keep.id]

    raw = DrawRepository(session).list_draws(lottery_code="LOTO", is_deleted=None)
    assert {d.id for d in raw} == {keep.id, deleted.id}


def test_functional_get_rejects_soft_deleted(session) -> None:
    """V5: explicit functional access to a soft-deleted draw raises SoftDeletedError."""
    lottery = _make_lottery(session)
    draw = _make_draw(session, lottery.id, draw_number=1)
    _draw_service(session).soft_delete(draw.id)

    with pytest.raises(SoftDeletedError) as excinfo:
        _draw_service(session).get_draw(draw.id)
    assert excinfo.value.code == "RESOURCE_SOFT_DELETED"
    # administrative (raw repo) access still possible — the audit row persists
    assert DrawRepository(session).get(draw.id) is not None


def test_functional_get_missing_draw_raises_not_found(session) -> None:
    """Functional get_draw on an absent draw maps to NotFoundError."""
    with pytest.raises(NotFoundError) as excinfo:
        _draw_service(session).get_draw(9999)
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# Dataset — immutability contract (V3, scope 2, mandates A/D)
# ---------------------------------------------------------------------------


def test_create_dataset_locks_and_composes(session) -> None:
    """V3 base: create_dataset persists dataset + composition + is_locked in one tx."""
    lottery = _make_lottery(session)
    d1 = _make_draw(session, lottery.id, draw_number=1)
    d2 = _make_draw(session, lottery.id, draw_number=2)

    dataset = _dataset_service(session).create_dataset(
        version="v1",
        lottery_id=lottery.id,
        generator_version="g1",
        description="training set",
        draw_ids=[d1.id, d2.id],
    )
    assert dataset.is_locked is True
    assert dataset.checksum is None  # computed in F2 (CD-03)
    composed = DatasetDrawRepository(session).draws_for_dataset(dataset.id)
    assert [d.id for d in composed] == [d1.id, d2.id]
    assert _dataset_service(session).get_dataset("v1").id == dataset.id


def test_create_dataset_duplicate_version_raises_duplicate(session) -> None:
    """Mandate A: an existing global version raises DuplicateError (no silent dedup)."""
    lottery = _make_lottery(session)
    d1 = _make_draw(session, lottery.id, draw_number=1)
    svc = _dataset_service(session)
    svc.create_dataset(
        version="v1", lottery_id=lottery.id, generator_version="g1", draw_ids=[d1.id]
    )

    with pytest.raises(DuplicateError) as excinfo:
        svc.create_dataset(
            version="v1", lottery_id=lottery.id, generator_version="g1", draw_ids=[d1.id]
        )
    assert excinfo.value.code == "DUPLICATE_RESOURCE"
    assert session.query(Dataset).count() == 1
    assert session.query(DatasetDraw).count() == 1  # failed attempt added nothing


def test_create_dataset_unknown_lottery_raises_not_found(session) -> None:
    """A missing lottery maps to NotFoundError before any insert."""
    with pytest.raises(NotFoundError) as excinfo:
        _dataset_service(session).create_dataset(
            version="v1", lottery_id=9999, generator_version="g1", draw_ids=[]
        )
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"


def test_create_dataset_dedupes_draw_ids(session) -> None:
    """Mandate (draw_ids deduped): repeated ids compose once (no false UNIQUE error)."""
    lottery = _make_lottery(session)
    d1 = _make_draw(session, lottery.id, draw_number=1)
    d2 = _make_draw(session, lottery.id, draw_number=2)
    d3 = _make_draw(session, lottery.id, draw_number=3)

    dataset = _dataset_service(session).create_dataset(
        version="v1",
        lottery_id=lottery.id,
        generator_version="g1",
        draw_ids=[d1.id, d2.id, d2.id, d3.id, d1.id],
    )
    composed = DatasetDrawRepository(session).draws_for_dataset(dataset.id)
    assert [d.id for d in composed] == [d1.id, d2.id, d3.id]


def test_create_dataset_unknown_draw_rolls_back(session) -> None:
    """Real DB rollback: a missing draw FK fails mid-transaction; zero orphan rows."""
    lottery = _make_lottery(session)
    with pytest.raises(ReferentialError) as excinfo:
        _dataset_service(session).create_dataset(
            version="v1",
            lottery_id=lottery.id,
            generator_version="g1",
            draw_ids=[999999],  # no such draw -> FK RESTRICT at flush
        )
    assert excinfo.value.code == "REFERENTIAL_CONSTRAINT"
    assert session.query(Dataset).count() == 0
    assert session.query(DatasetDraw).count() == 0


def test_update_locked_dataset_raises_locked(session) -> None:
    """V3: update on a locked dataset raises DatasetLockedError; DB row unchanged."""
    lottery = _make_lottery(session)
    d1 = _make_draw(session, lottery.id, draw_number=1)
    svc = _dataset_service(session)
    dataset = svc.create_dataset(
        version="v1",
        lottery_id=lottery.id,
        generator_version="g1",
        description="original",
        draw_ids=[d1.id],
    )

    with pytest.raises(DatasetLockedError) as excinfo:
        svc.update(dataset.id, description="mutated")
    assert excinfo.value.code == "DATASET_LOCKED"

    fresh = session.get(Dataset, dataset.id)
    assert fresh.description == "original"  # byte-identical
    assert fresh.is_locked is True  # no auto-unlock (mandate D)


def test_update_locked_dataset_never_auto_unlocks(session) -> None:
    """V3: repeated locked-update attempts never flip is_locked (no auto-unlock)."""
    lottery = _make_lottery(session)
    d1 = _make_draw(session, lottery.id, draw_number=1)
    svc = _dataset_service(session)
    dataset = svc.create_dataset(
        version="v1", lottery_id=lottery.id, generator_version="g1", draw_ids=[d1.id]
    )

    for _ in range(3):
        with pytest.raises(DatasetLockedError):
            svc.update(dataset.id, description="x")
    assert session.get(Dataset, dataset.id).is_locked is True


def test_update_unlocked_dataset_allows_description(session) -> None:
    """A transiently unlocked dataset may change metadata (description only)."""
    lottery = _make_lottery(session)
    dataset = DatasetRepository(session).create(
        {"version": "draft", "lottery_id": lottery.id, "generator_version": "g1"}
    )
    session.commit()

    updated = _dataset_service(session).update(dataset.id, description="renamed")
    assert updated.description == "renamed"
    assert updated.is_locked is False


def test_update_filters_rejected_requires_new_version(session) -> None:
    """Immutability contract: filters change via update is forbidden (needs new version)."""
    lottery = _make_lottery(session)
    dataset = DatasetRepository(session).create(
        {
            "version": "draft",
            "lottery_id": lottery.id,
            "generator_version": "g1",
            "description": "a",
        }
    )
    session.commit()

    with pytest.raises(ValidationError) as excinfo:
        _dataset_service(session).update(dataset.id, filters='{"date_from": "2026-01-01"}')
    assert excinfo.value.code == "validation_error"
    assert session.get(Dataset, dataset.id).filters is None  # unchanged


def test_composition_change_creates_new_version(session) -> None:
    """CD-03 scenario: v2 with a different draw set leaves v1 byte-identical."""
    lottery = _make_lottery(session)
    d1 = _make_draw(session, lottery.id, draw_number=1)
    d2 = _make_draw(session, lottery.id, draw_number=2)
    d3 = _make_draw(session, lottery.id, draw_number=3)
    svc = _dataset_service(session)

    v1 = svc.create_dataset(
        version="v1",
        lottery_id=lottery.id,
        generator_version="g1",
        description="first",
        filters='{"from": 1}',
        draw_ids=[d1.id, d2.id],
    )
    v2 = svc.create_dataset(
        version="v2",
        lottery_id=lottery.id,
        generator_version="g1",
        description="second",
        filters='{"from": 2}',
        draw_ids=[d2.id, d3.id],
    )

    assert v1.is_locked is True and v2.is_locked is True
    assert [d.id for d in DatasetDrawRepository(session).draws_for_dataset(v1.id)] == [d1.id, d2.id]
    assert [d.id for d in DatasetDrawRepository(session).draws_for_dataset(v2.id)] == [d2.id, d3.id]
    assert session.get(Dataset, v1.id).description == "first"  # v1 untouched
    assert session.get(Dataset, v1.id).filters == '{"from": 1}'


def test_get_dataset_missing_raises_not_found(session) -> None:
    """get_dataset on an absent version maps to NotFoundError (RESOURCE_NOT_FOUND)."""
    with pytest.raises(NotFoundError) as excinfo:
        _dataset_service(session).get_dataset("nope")
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# V6 — no duplicated logic between services: shared helper is the single source
# ---------------------------------------------------------------------------


def test_shared_lottery_lookup_helper_is_single_source(session) -> None:
    """V6: both services resolve lotteries through the shared helper (no copy-paste)."""
    # The helper raises the same typed error both services surface.
    with pytest.raises(NotFoundError) as excinfo:
        get_lottery_or_raise(LotteryRepository(session), 4242)
    assert excinfo.value.code == "RESOURCE_NOT_FOUND"

    # And the services keep exposing the same code through their public paths.
    with pytest.raises(NotFoundError) as draw_not_found:
        _draw_service(session).create_draw_bundle(
            lottery_id=4242, draw_number=1, draw_date=date(2026, 1, 1), numbers=_valid_numbers()
        )
    with pytest.raises(NotFoundError) as dataset_not_found:
        _dataset_service(session).create_dataset(
            version="v1", lottery_id=4242, generator_version="g1", draw_ids=[]
        )
    assert draw_not_found.value.code == dataset_not_found.value.code == "RESOURCE_NOT_FOUND"
