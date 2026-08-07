"""GF1 authoritative determinism: two independent generations are byte-identical (P2-07).

The Feature Engine determinism contract (FES-05): same {draws checksum, feature
versions/params} + same ``FEATURE_GENERATOR_VERSION`` MUST yield byte-identical
persisted ``feature_values`` — checksum, input_fingerprint, and every persisted row.
Runs two fully independent, identically-seeded DBs (separate files/sessions) and
asserts all three identities at the service layer, mirroring the statistics G9 test.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from alembic.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from alembic import command
from backend.app.core.db import build_engine
from backend.app.models.feature_value import FeatureValue
from backend.app.services.draw_service import DrawService
from backend.app.services.feature_engine_service import FeatureEngineService
from backend.app.services.lottery_service import LotteryService

# <repo>/backend/tests -> <repo>/backend/alembic.ini
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def _fresh_db(tmp_path: Path, name: str) -> Session:
    """Build an independent tmp migrated SQLite DB and return a session on it."""
    db_path = tmp_path / f"{name}.db"
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db_path}")
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    session._output_engine = engine  # keep alive until test ends
    return session


def _seed_lottery(db: Session, code: str = "GF1") -> int:
    return (
        LotteryService(db)
        .create(
            {
                "code": code,
                "name": "GF1 Primitiva",
                "country": "AR",
                "min_number": 1,
                "max_number": 45,
                "numbers_to_select": 5,
                "super_number_min": 1,
                "super_number_max": 3,
            }
        )
        .id
    )


def _seed_draws(db: Session, lottery_id: int, count: int = 9) -> None:
    for number in range(1, count + 1):
        numbers = [((number * 3 + offset) % 45) or 45 for offset in range(5)]
        DrawService(db).create_draw_bundle(
            lottery_id=lottery_id,
            draw_number=number,
            draw_date=date(2024, 2, number),
            numbers=numbers,
            super_number=None,
            jackpot=None,
            winners=None,
        )
        db.commit()


def _values(db: Session, snapshot_id: int) -> list[tuple]:
    rows = db.execute(
        select(FeatureValue)
        .where(FeatureValue.snapshot_id == snapshot_id)
        .order_by(FeatureValue.feature_id, FeatureValue.draw_number)
    ).scalars()
    return [
        (row.feature_id, str(row.feature_version), row.draw_number, str(row.value)) for row in rows
    ]


def _run_generation(tmp_path: Path, tag: str) -> tuple[Session, object]:
    db = _fresh_db(tmp_path, tag)
    lottery_id = _seed_lottery(db)
    _seed_draws(db, lottery_id)
    snapshot = FeatureEngineService(db).generate(lottery_id=lottery_id, scope="full")
    return db, snapshot


def test_gf1_two_independent_generations_byte_identical(tmp_path: Path) -> None:
    """GF1: two independent DBs -> identical checksum, fingerprint, and content."""
    first_db, first = _run_generation(tmp_path, "gf1_a")
    second_db, second = _run_generation(tmp_path, "gf1_b")

    try:
        # identical header fingerprints and output checksum.
        assert first.input_fingerprint == second.input_fingerprint
        assert first.checksum == second.checksum
        assert first.feature_engine_version == second.feature_engine_version

        # identical persisted content (row-for-row) in insertion order.
        assert _values(first_db, first.id) == _values(second_db, second.id)
    finally:
        first_db.close()
        second_db.close()
