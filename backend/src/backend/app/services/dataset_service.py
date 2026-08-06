"""Dataset domain service: immutable, versioned composition (CD-03, scope item 2).

Immutability is enforced here, in the service layer, because portable DB
triggers do not exist (design: app guard + RESTRICT FKs are the portable
enforcement). A created dataset is locked atomically inside its creating
transaction, and no service path can mutate a locked dataset: any update raises
``DatasetLockedError`` (DATASET_LOCKED) and never auto-unlocks (mandate D). All
filter / composition changes are expressed by creating a NEW dataset version —
the only way to change an immutable artifact. Repositories stay
persistence-only; this service owns the lock policy, the version-uniqueness
pre-check and the composition transaction (mandate B: rollback on any failure,
zero orphan rows).
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.app.models.dataset import Dataset
from backend.app.repositories.dataset_draw_repository import DatasetDrawRepository
from backend.app.repositories.dataset_repository import DatasetRepository
from backend.app.repositories.errors import DuplicateError
from backend.app.repositories.lottery_repository import LotteryRepository
from backend.app.services.errors import DatasetLockedError, NotFoundError, ValidationError
from backend.app.services.helpers import get_lottery_or_raise


def _dedupe_preserving_order(ids: list[int]) -> list[int]:
    """Return distinct ids in first-seen order (composition de-duplication).

    ``UNIQUE(dataset_id, draw_id)`` would reject a repeated id with a false
    ``DuplicateError``; the service removes duplicates before composing so the
    constraint only guards genuinely duplicated compositions.
    """
    seen: set[int] = set()
    result: list[int] = []
    for value in ids:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


class DatasetService:
    """Dataset use cases over one DI session transaction (CD-03 reproducibility contract)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._lotteries = LotteryRepository(session)
        self._datasets = DatasetRepository(session)
        self._composition = DatasetDrawRepository(session)

    def create_dataset(
        self,
        *,
        version: str,
        lottery_id: int,
        generator_version: str,
        draw_ids: list[int],
        description: str | None = None,
        filters: str | None = None,
        checksum: str | None = None,
    ) -> Dataset:
        """Create a dataset + its composition + the lock in ONE transaction (CD-03).

        ``version`` is globally UNIQUE: an existing version raises
        ``DuplicateError`` (DUPLICATE_RESOURCE) — dataset versions are distinct
        immutable artifacts and MUST NOT be silently de-duplicated (mandate A).
        ``draw_ids`` are de-duplicated before composing. The row is created with
        ``is_locked=True`` in the same transaction that inserts the composition,
        so the artifact is immutable from its first visible state. ``checksum``
        is an additive parameter: it defaults to ``None`` (F1 behaviour, computed
        in F2) and, when provided (F2 ``ImportService.generate_dataset``), is
        stored and makes the dataset reproducible (CD-03). Any failure — version
        UNIQUE, FK to a missing lottery/draw, composition constraint — rolls the
        whole operation back, leaving zero dataset rows and zero composition rows.
        """
        get_lottery_or_raise(self._lotteries, lottery_id)
        if self._datasets.get_by_version(version) is not None:
            raise DuplicateError(f"dataset version {version!r} already exists")

        deduped = _dedupe_preserving_order(draw_ids)
        try:
            dataset = self._datasets.create(
                {
                    "version": version,
                    "description": description,
                    "lottery_id": lottery_id,
                    "filters": filters,
                    "generator_version": generator_version,
                    "checksum": checksum,
                    "is_locked": True,
                }
            )
            if deduped:
                self._composition.add_many(dataset_id=dataset.id, draw_ids=deduped)
            self._session.commit()
            return dataset
        except Exception:
            self._session.rollback()
            raise

    def update(
        self,
        dataset_id: int,
        *,
        description: str | None = None,
        filters: str | None = None,
    ) -> Dataset:
        """Update a dataset under the immutability contract (CD-03).

        A locked dataset can never be modified: any attempt raises
        ``DatasetLockedError`` (DATASET_LOCKED) before touching the DB — the row
        stays byte-identical and the lock is never removed (no auto-unlock,
        mandate D). Changing ``filters`` is rejected with ``ValidationError``
        even while unlocked because filter/composition changes SHALL create a
        NEW dataset version. Only the ``description`` metadata may change, and
        only while the dataset is (transiently) unlocked.
        """
        dataset = self._require_dataset(dataset_id)
        if dataset.is_locked:
            raise DatasetLockedError("dataset is immutable (locked)")
        if filters is not None:
            raise ValidationError("changing dataset filters requires a new dataset version")
        if description is None:
            return dataset
        try:
            self._datasets.update(dataset_id, {"description": description})
            self._session.commit()
            return dataset
        except Exception:
            self._session.rollback()
            raise

    def get_dataset(self, version: str) -> Dataset:
        """Look up a dataset by its ``version`` natural key (CD-03, RESOURCE_NOT_FOUND)."""
        dataset = self._datasets.get_by_version(version)
        if dataset is None:
            raise NotFoundError(f"dataset version {version!r} does not exist")
        return dataset

    def list_datasets(self, *, page: int = 1, page_size: int = 50) -> list[Dataset]:
        """Page of datasets ordered by id (functional lookup)."""
        return self._datasets.list(page=page, page_size=page_size)

    # --- private helpers ---------------------------------------------------

    def _require_dataset(self, dataset_id: int) -> Dataset:
        """Look up a dataset by id; a missing row maps to ``NotFoundError``."""
        dataset = self._datasets.get(dataset_id)
        if dataset is None:
            raise NotFoundError(f"dataset {dataset_id} does not exist")
        return dataset
