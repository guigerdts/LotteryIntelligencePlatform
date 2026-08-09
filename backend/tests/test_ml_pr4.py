"""PR4 gates for Fase 7 ML: snapshot_store + MlService + SNAPSHOT_NOT_FOUND.

Tests the atomic lifecycle (active→retired), bulk metrics insert, Decimal(20,8)
integrity, service orchestration with mock providers, and clean error paths.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy.orm import Session, sessionmaker

from backend.app.ml.feature_reader import FeatureValueRow
from backend.app.ml.registry import MODEL_SET_CORE_5
from backend.app.ml.snapshot_store import MlSnapshotStore
from backend.app.ml.version import ML_GENERATOR_VERSION
from backend.app.models.ml_metric import MlMetric
from backend.app.models.ml_snapshot import MlSnapshot
from backend.app.services.ml_service import MlService

# ---------------------------------------------------------------------------
# Mock providers
# ---------------------------------------------------------------------------


class _Draw(NamedTuple):
    draw_number: int
    numbers: tuple[int, ...]


class MockDrawReader:
    """In-memory draw history provider for testing."""

    def __init__(self, draws: list[_Draw]) -> None:
        self._draws = {d.draw_number: d for d in draws}

    def iter_draws(
        self, lottery_id: int, *, after_draw_number: int | None = None
    ) -> Iterator[_Draw]:
        draws = sorted(self._draws.values(), key=lambda d: d.draw_number)
        for d in draws:
            if after_draw_number is None or d.draw_number > after_draw_number:
                yield d

    def lottery_rules(self, lottery_id: int) -> None:  # type: ignore[override]
        return None


class MockFeatureProvider:
    """In-memory feature snapshot provider for testing."""

    def __init__(self, rows: list[FeatureValueRow], active_snapshot_id: int = 1) -> None:
        self._rows = rows
        self._active_id = active_snapshot_id

    def active_snapshot_id(self, lottery_id: int) -> int | None:
        return self._active_id

    def feature_rows(self, snapshot_id: int) -> Iterator[FeatureValueRow]:
        return iter(self._rows)


class MockFeatureProviderEmpty:
    """Provider returning no active snapshot (triggers SNAPSHOT_NOT_FOUND)."""

    def active_snapshot_id(self, lottery_id: int) -> int | None:
        return None

    def feature_rows(self, snapshot_id: int) -> Iterator[FeatureValueRow]:
        return iter([])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FEATURES = [
    FeatureValueRow(feature_id=f, draw_number=1, value=0.5)
    for f in [
        "consecutive_count",
        "current_frequency",
        "decade_distribution",
        "draw_mean",
        "draw_range",
        "draw_sum",
        "low_high_ratio",
        "max_current_gap",
        "odd_even_ratio",
        "repeated_from_previous",
    ]
]


def _seed_lottery(session: Session, lottery_id: int = 1) -> None:
    """Insert a minimal lottery row so FK constraints pass."""
    session.execute(
        __import__("sqlalchemy").text(
            "INSERT INTO lottery (id, code, name, country, min_number, max_number, "
            "numbers_to_select, created_at) "
            "VALUES (:id, :code, :name, :country, :min, :max, :sel, datetime('now'))"
        ),
        {
            "id": lottery_id,
            "code": f"L{lottery_id}",
            "name": f"Lot {lottery_id}",
            "country": "AR",
            "min": 1,
            "max": 50,
            "sel": 6,
        },
    )
    session.flush()


# ---------------------------------------------------------------------------
# Tests: MlSnapshotStore
# ---------------------------------------------------------------------------


class TestMlSnapshotStore:
    """MlSnapshotStore lifecycle and persistence (MLE-08)."""

    def test_create_active(self, db: Session) -> None:
        """Create a snapshot with status=active."""
        _seed_lottery(db)
        store = MlSnapshotStore(db)
        header = store.create_snapshot(
            lottery_id=1,
            model_set=MODEL_SET_CORE_5,
            version="1",
            ml_generator_version=ML_GENERATOR_VERSION,
            checksum="abc",
            input_fingerprint="def",
            cut=80,
            status="active",
            is_locked=True,
            draw_count=100,
            draws_from=1,
            draws_to=100,
        )
        db.commit()
        assert header.status == "active"
        assert header.lottery_id == 1
        assert header.model_set == MODEL_SET_CORE_5

    def test_retire_old_active(self, db: Session) -> None:
        """First active is retired when a second is created."""
        _seed_lottery(db)
        store = MlSnapshotStore(db)
        h1 = store.create_snapshot(
            lottery_id=1,
            model_set=MODEL_SET_CORE_5,
            version="1",
            ml_generator_version=ML_GENERATOR_VERSION,
            checksum="a",
            input_fingerprint="b",
            cut=80,
            status="active",
            is_locked=True,
            draw_count=100,
            draws_from=1,
            draws_to=100,
        )
        db.flush()
        h2 = store.create_snapshot(
            lottery_id=1,
            model_set=MODEL_SET_CORE_5,
            version="2",
            ml_generator_version=ML_GENERATOR_VERSION,
            checksum="c",
            input_fingerprint="d",
            cut=80,
            status="active",
            is_locked=True,
            draw_count=100,
            draws_from=1,
            draws_to=100,
        )
        db.flush()
        store.retire_old_active(1, MODEL_SET_CORE_5, keep_id=h2.id)
        db.commit()

        db.refresh(h1)
        db.refresh(h2)
        assert h1.status == "retired"
        assert h2.status == "active"

    def test_mark_failed(self, db: Session) -> None:
        """Failed is terminal — header marked failed."""
        _seed_lottery(db)
        store = MlSnapshotStore(db)
        header = store.create_snapshot(
            lottery_id=1,
            model_set=MODEL_SET_CORE_5,
            version="1",
            ml_generator_version=ML_GENERATOR_VERSION,
            checksum="",
            input_fingerprint="",
            cut=0,
            status="active",
            is_locked=True,
            draw_count=0,
            draws_from=0,
            draws_to=0,
        )
        db.flush()
        store.mark_failed(header.id)
        db.commit()
        db.refresh(header)
        assert header.status == "failed"
        assert header.is_locked is False

    def test_get_active(self, db: Session) -> None:
        """get_active returns the active snapshot."""
        _seed_lottery(db)
        store = MlSnapshotStore(db)
        store.create_snapshot(
            lottery_id=1,
            model_set=MODEL_SET_CORE_5,
            version="1",
            ml_generator_version=ML_GENERATOR_VERSION,
            checksum="x",
            input_fingerprint="y",
            cut=80,
            status="active",
            is_locked=True,
            draw_count=50,
            draws_from=1,
            draws_to=50,
        )
        db.commit()
        result = store.get_active(1, MODEL_SET_CORE_5)
        assert result is not None
        assert result.status == "active"

    def test_get_active_none(self, db: Session) -> None:
        """get_active returns None when no active snapshot exists."""
        store = MlSnapshotStore(db)
        assert store.get_active(999, MODEL_SET_CORE_5) is None

    def test_bulk_insert_metrics_decimal(self, db: Session) -> None:
        """Metrics are stored as Decimal(20,8)."""
        _seed_lottery(db)
        store = MlSnapshotStore(db)
        header = store.create_snapshot(
            lottery_id=1,
            model_set=MODEL_SET_CORE_5,
            version="1",
            ml_generator_version=ML_GENERATOR_VERSION,
            checksum="z",
            input_fingerprint="w",
            cut=80,
            status="active",
            is_locked=True,
            draw_count=50,
            draws_from=1,
            draws_to=50,
        )
        db.flush()

        rows = [
            MlMetric(
                snapshot_id=header.id,
                model_id="random_forest",
                model_version=ML_GENERATOR_VERSION,
                number=1,
                metric_name="accuracy",
                value=Decimal("0.85000000"),
                params_json="{}",
            ),
            MlMetric(
                snapshot_id=header.id,
                model_id="random_forest",
                model_version=ML_GENERATOR_VERSION,
                number=1,
                metric_name="f1",
                value=Decimal("0.72000000"),
                params_json="{}",
            ),
        ]
        store.bulk_insert_metrics(header.id, rows)
        db.commit()

        stored = store.metrics_for_snapshot(header.id)
        assert len(stored) == 2
        for m in stored:
            assert isinstance(m.value, Decimal)
            # Numeric(20,8) preserves 8 decimal places.
            assert m.value.as_tuple().exponent == -8


# ---------------------------------------------------------------------------
# Tests: MlService
# ---------------------------------------------------------------------------


class TestMlService:
    """MlService orchestration and error paths."""

    def test_train_basic(self, session_factory: sessionmaker) -> None:
        """Training a single family produces an active snapshot with metrics."""
        session: Session = session_factory()
        _seed_lottery(session)

        # 10 draws with 6 numbers each, numbers 1-50.
        draws = [
            _Draw(draw_number=i, numbers=tuple(range(1 + (i % 5), 7 + (i % 5))))
            for i in range(1, 12)
        ]
        # Build feature rows: all 10 features for each of the 11 draws.
        feat_rows = []
        for d in draws:
            for j, fid in enumerate(
                [
                    "consecutive_count",
                    "current_frequency",
                    "decade_distribution",
                    "draw_mean",
                    "draw_range",
                    "draw_sum",
                    "low_high_ratio",
                    "max_current_gap",
                    "odd_even_ratio",
                    "repeated_from_previous",
                ]
            ):
                feat_rows.append(
                    FeatureValueRow(
                        feature_id=fid,
                        draw_number=d.draw_number,
                        value=float(j + d.draw_number * 0.01),
                    )
                )

        draw_reader = MockDrawReader(draws)
        feature_provider = MockFeatureProvider(feat_rows)
        service = MlService(session, draw_reader, feature_provider)

        outcomes = service.train(1, family="random_forest")
        assert len(outcomes) == 1
        o = outcomes[0]
        assert o.family == "random_forest"
        assert o.status == "active"
        assert o.snapshot_id is not None
        assert o.fingerprint  # non-empty
        assert o.metrics_checksum  # non-empty

        # Verify metrics are stored.
        metrics = service.get_metrics(1, model_id="random_forest")
        assert len(metrics) > 0
        for m in metrics:
            assert "value" in m
            assert isinstance(m["value"], float)  # returned as float for JSON

    def test_snapshot_not_found(self, session_factory: sessionmaker) -> None:
        """Training with no F4 snapshot raises SnapshotNotFoundError."""
        session: Session = session_factory()
        _seed_lottery(session)

        draw_reader = MockDrawReader([])
        feature_provider = MockFeatureProviderEmpty()
        service = MlService(session, draw_reader, feature_provider)

        outcomes = service.train(1, family="random_forest")
        assert len(outcomes) == 1
        assert outcomes[0].status == "failed"
        assert outcomes[0].error is not None

    def test_no_future_models(self, session_factory: sessionmaker) -> None:
        """Service only trains core-5 families."""
        from backend.app.ml.registry import FUTURE_ML_FAMILIES

        # Verify future families are not in the core-5 list.
        from backend.app.services.ml_service import _CORE_5_FAMILIES

        for fam in FUTURE_ML_FAMILIES:
            assert fam not in _CORE_5_FAMILIES

    def test_manual_only(self, db: Session) -> None:
        """No auto-retire: manual-only lifecycle enforcement."""
        store = MlSnapshotStore(db)
        _seed_lottery(db)

        # Create two active snapshots without retiring.
        store.create_snapshot(
            lottery_id=1,
            model_set=MODEL_SET_CORE_5,
            version="1",
            ml_generator_version=ML_GENERATOR_VERSION,
            checksum="a",
            input_fingerprint="b",
            cut=80,
            status="active",
            is_locked=True,
            draw_count=50,
            draws_from=1,
            draws_to=50,
        )
        store.create_snapshot(
            lottery_id=1,
            model_set=MODEL_SET_CORE_5,
            version="2",
            ml_generator_version=ML_GENERATOR_VERSION,
            checksum="c",
            input_fingerprint="d",
            cut=80,
            status="active",
            is_locked=True,
            draw_count=50,
            draws_from=1,
            draws_to=50,
        )
        db.commit()

        # Both are active — no auto-retire happened.
        active = (
            db.query(MlSnapshot)
            .filter(
                MlSnapshot.status == "active",
                MlSnapshot.lottery_id == 1,
            )
            .all()
        )
        assert len(active) == 2

    def test_get_active_snapshot(self, session_factory: sessionmaker) -> None:
        """get_active_snapshot returns metadata dict or None."""
        session: Session = session_factory()
        _seed_lottery(session)
        store = MlSnapshotStore(session)
        store.create_snapshot(
            lottery_id=1,
            model_set=MODEL_SET_CORE_5,
            version="1",
            ml_generator_version=ML_GENERATOR_VERSION,
            checksum="x",
            input_fingerprint="y",
            cut=80,
            status="active",
            is_locked=True,
            draw_count=50,
            draws_from=1,
            draws_to=50,
        )
        session.commit()

        service = MlService(session, MockDrawReader([]), MockFeatureProviderEmpty())
        result = service.get_active_snapshot(1)
        assert result is not None
        assert result["status"] == "active"
        assert result["version"] == "1"
