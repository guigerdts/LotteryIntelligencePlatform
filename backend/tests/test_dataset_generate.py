"""PR-3 on-demand dataset generation tests (S3-06; D5/IE-09, CD-03).

Proves ``ImportService.generate_dataset`` over the tmp migrated SQLite DB: the
checksum is stable across two generations of the same content (deterministic),
the created dataset is ``is_locked=True`` and immutable (an update raises
``DatasetLockedError``), filters reduce the selected draw set, malformed filters
raise ``ValidationError``, and — critically — an import NEVER auto-creates a
dataset (IE-09: import only ingests draws).
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from backend.app.models import Dataset, DatasetDraw
from backend.app.services.dataset_service import DatasetService
from backend.app.services.draw_service import DrawService
from backend.app.services.errors import DatasetLockedError, ValidationError
from backend.app.services.import_service import ImportService
from backend.app.services.lottery_service import LotteryService

_GENERATOR_VERSION = "testgen-1"

_HEADERS = ["draw_number", "draw_date", "numbers", "super_number", "jackpot", "winners"]


def _seed_lottery(db: Session, code: str = "BALOTO") -> int:
    return (
        LotteryService(db)
        .create(
            {
                "code": code,
                "name": "Baloto",
                "country": "CO",
                "min_number": 1,
                "max_number": 45,
                "numbers_to_select": 6,
                "super_number_min": 1,
                "super_number_max": 12,
            }
        )
        .id
    )


def _seed_draw(db: Session, lottery_id: int, draw_number: int, when: date) -> None:
    DrawService(db).create_draw_bundle(
        lottery_id=lottery_id,
        draw_number=draw_number,
        draw_date=when,
        numbers=[1, 2, 3, 4, 5, 6],
        super_number=7,
    )
    db.commit()


def _composition_ids(db: Session, dataset_id: int) -> set[int]:
    rows = db.query(DatasetDraw.draw_id).filter(DatasetDraw.dataset_id == dataset_id).all()
    return {int(draw_id) for (draw_id,) in rows}


# --- checksum stability (deterministic, IE-09) -----------------------------


def test_generate_dataset_checksum_stable_across_runs(db: Session) -> None:
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 100, date(2024, 1, 1))
    _seed_draw(db, lottery_id, 101, date(2024, 1, 2))

    service = ImportService(db)
    first = service.generate_dataset(
        version="v1", lottery_id=lottery_id, generator_version=_GENERATOR_VERSION
    )
    second = service.generate_dataset(
        version="v2", lottery_id=lottery_id, generator_version=_GENERATOR_VERSION
    )

    # Same content, same generator -> identical checksum (reproducibility, CD-03).
    assert first.checksum == second.checksum
    assert first.checksum is not None
    assert first.is_locked is True
    assert second.is_locked is True
    # Composition carries the two seeded draws.
    assert _composition_ids(db, first.id) == _composition_ids(db, second.id)


def test_generate_dataset_checksum_depends_on_filters_and_draws(db: Session) -> None:
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 100, date(2024, 1, 1))
    _seed_draw(db, lottery_id, 101, date(2024, 2, 1))

    service = ImportService(db)
    filtered = service.generate_dataset(
        version="f1",
        lottery_id=lottery_id,
        generator_version=_GENERATOR_VERSION,
        filters='{"date_from": "2024-02-01"}',
    )
    unfiltered = service.generate_dataset(
        version="u1", lottery_id=lottery_id, generator_version=_GENERATOR_VERSION
    )

    assert _composition_ids(db, filtered.id) != _composition_ids(db, unfiltered.id)
    assert filtered.checksum != unfiltered.checksum
    assert _composition_ids(db, filtered.id)  # at least one draw selected


# --- immutable + locked semantics (CD-03) ----------------------------------


def test_generated_dataset_is_locked_and_immutable(db: Session) -> None:
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 100, date(2024, 1, 1))
    dataset = ImportService(db).generate_dataset(
        version="v1", lottery_id=lottery_id, generator_version=_GENERATOR_VERSION
    )

    assert dataset.is_locked is True
    # A locked dataset rejects any mutation (DatasetLockedError, DATASET_LOCKED).
    with pytest.raises(DatasetLockedError):
        DatasetService(db).update(dataset.id, description="hacked")
    db.rollback()

    refreshed = db.get(Dataset, dataset.id)
    assert refreshed.is_locked is True
    assert refreshed.checksum == dataset.checksum


def test_generate_dataset_duplicate_version_raises_duplicate_resource(db: Session) -> None:
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 100, date(2024, 1, 1))

    ImportService(db).generate_dataset(
        version="v1", lottery_id=lottery_id, generator_version=_GENERATOR_VERSION
    )
    with pytest.raises(Exception) as excinfo:
        ImportService(db).generate_dataset(
            version="v1", lottery_id=lottery_id, generator_version=_GENERATOR_VERSION
        )
    assert type(excinfo.value).__name__ == "DuplicateError"
    assert getattr(excinfo.value, "code", "") == "DUPLICATE_RESOURCE"


def test_generate_dataset_malformed_filters_raises_validation_error(db: Session) -> None:
    lottery_id = _seed_lottery(db)
    _seed_draw(db, lottery_id, 100, date(2024, 1, 1))

    service = ImportService(db)
    with pytest.raises(ValidationError):
        service.generate_dataset(
            version="v1",
            lottery_id=lottery_id,
            generator_version=_GENERATOR_VERSION,
            filters="not-json",
        )
    with pytest.raises(ValidationError):
        service.generate_dataset(
            version="v1",
            lottery_id=lottery_id,
            generator_version=_GENERATOR_VERSION,
            filters='{"bogus_key": 1}',
        )
    with pytest.raises(ValidationError):
        service.generate_dataset(
            version="v1",
            lottery_id=lottery_id,
            generator_version=_GENERATOR_VERSION,
            filters='{"date_from": "yesterday"}',
        )


# --- import never auto-creates a dataset (D5/IE-09) -------------------------


def test_import_does_not_auto_create_dataset(db: Session, tmp_path: Path) -> None:
    lottery_id = _seed_lottery(db)
    source = tmp_path / "import.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(_HEADERS)
        writer.writerow(["100", "2024-01-05", "1,2,3,4,5,6", "7", "5000000.00", "3"])

    summary = ImportService(db).run_import(lottery_id=lottery_id, source_path=source)
    assert summary["status"] == "completed"
    assert summary["imported_rows"] == 1

    # The import ingested a draw but created NO dataset (D5/IE-09).
    assert not db.query(Dataset).all()
    assert not db.query(DatasetDraw).all()
