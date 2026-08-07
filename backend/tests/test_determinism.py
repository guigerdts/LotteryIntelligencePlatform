"""GF1 authoritative determinism: two independent generations are byte-identical (P2-07).

The Feature Engine determinism contract (FES-05): same {draws checksum, feature
versions/params} + same ``FEATURE_GENERATOR_VERSION`` MUST yield byte-identical
persisted ``feature_values`` — checksum, input_fingerprint, and every persisted row.
Runs two fully independent, identically-seeded DBs (separate files/sessions) and
asserts all three identities at the service layer, mirroring the statistics G9 test.

P3-08 adds the surface-level e2e of GF1: a CLI run and an API run over two
identically-seeded DBs produce identical checksums, row counts, row content,
insertion order, and canonical content hash (design §5: ORDER BY draw_number, id on
reads; canonical json.dumps — the surface must reproduce the service determinism).
"""

from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stdout
from datetime import date
from pathlib import Path

from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session, sessionmaker

import backend.app.cli as cli_module
from alembic import command
from backend.app.core.db import build_engine
from backend.app.main import create_app
from backend.app.models.feature_snapshot import FeatureSnapshot
from backend.app.models.feature_value import FeatureValue
from backend.app.repositories.base import get_db
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
    """Create a GF1 lottery row; return its id (determinism seed)."""
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
    """Seed ``count`` deterministic draws for the lottery; commit each."""
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
    """Persisted rows in canonical ``(feature_id, version, draw_number, value)`` form."""
    rows = db.execute(
        select(FeatureValue)
        .where(FeatureValue.snapshot_id == snapshot_id)
        .order_by(FeatureValue.feature_id, FeatureValue.draw_number)
    ).scalars()
    return [
        (row.feature_id, str(row.feature_version), row.draw_number, str(row.value)) for row in rows
    ]


def _run_generation(tmp_path: Path, tag: str) -> tuple[Session, object]:
    """Seed a fresh DB and run one full generation; return the db and snapshot."""
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


# --- P3-08: GF1 e2e via the surface (CLI + API) ------------------------------


def _factory(tmp_path: Path, name: str) -> sessionmaker[Session]:
    """Independent migrated tmp SQLite DB; return a session factory on it."""
    db_path = tmp_path / f"{name}.db"
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "head")
    engine = build_engine(f"sqlite:///{db_path}")
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def _seed_full(db: Session, code: str = "GF1") -> int:
    """Seed a lottery and its draws, committing; return the lottery id."""
    lottery_id = _seed_lottery(db, code=code)
    _seed_draws(db, lottery_id)
    db.commit()
    return lottery_id


def _payload_ordered(db: Session, snapshot_id: int) -> list[tuple]:
    """Persisted rows in canonical read order ``(feature_id, draw_number)``."""
    rows = db.execute(
        select(FeatureValue)
        .where(FeatureValue.snapshot_id == snapshot_id)
        .order_by(FeatureValue.feature_id, FeatureValue.draw_number)
    ).scalars()
    return [
        (row.feature_id, str(row.feature_version), row.draw_number, str(row.value)) for row in rows
    ]


def _insertion_order(db: Session, snapshot_id: int) -> list[tuple]:
    """Physical insertion order (rowid): proves bulk_insert wrote rows identically."""
    return [
        tuple(row)
        for row in db.execute(
            text(
                "SELECT feature_id, draw_number FROM feature_values"
                " WHERE snapshot_id = :sid ORDER BY rowid"
            ),
            {"sid": snapshot_id},
        ).all()
    ]


def _content_hash(db: Session, snapshot_id: int) -> str:
    """Canonical hash over the header (minus id/version/timestamps) + ordered payload."""
    header = db.get(FeatureSnapshot, snapshot_id)
    lines = [
        repr(
            tuple(
                getattr(header, col.name)
                for col in FeatureSnapshot.__table__.columns
                if col.name not in {"id", "version", "status", "created_at", "updated_at"}
            )
        )
    ]
    lines += [repr(row) for row in _payload_ordered(db, snapshot_id)]
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def _run_cli(argv: list[str], factory: sessionmaker) -> str:
    """Run the CLI against ``factory``-bound sessions; return captured stdout."""
    original = cli_module.SessionLocal
    cli_module.SessionLocal = factory
    buf = io.StringIO()
    try:
        with redirect_stdout(buf):
            rc = cli_module.main(argv)
    finally:
        cli_module.SessionLocal = original
    assert rc == 0, f"CLI {argv} failed (rc={rc})"
    return buf.getvalue()


def _client_on(factory: sessionmaker) -> TestClient:
    """A TestClient whose ``get_db`` dependency targets ``factory``'s tmp DB."""
    app = create_app()

    def _override():
        """Yield a session from ``factory`` per request (get_db replacement)."""
        session = factory()
        try:
            yield session
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override
    return TestClient(app)


def test_gf1_e2e_cli_and_api_generations_are_byte_identical(tmp_path: Path) -> None:
    """GF1 e2e (P3-08): CLI and API runs on twin DBs -> identical feature sets."""
    factory_cli = _factory(tmp_path, "gf1_cli")
    factory_api = _factory(tmp_path, "gf1_api")
    with factory_cli() as seed:
        _seed_full(seed, code="GF1C")
    with factory_api() as seed:
        _seed_full(seed, code="GF1A")

    # Leg A: the CLI surface.
    cli_out = json.loads(_run_cli(["feature-engine", "generate", "--lottery", "GF1C"], factory_cli))
    # Leg B: the API surface.
    with _client_on(factory_api) as client:
        api_resp = client.post("/api/v1/feature-engine/generate", json={"lottery_code": "GF1A"})
        assert api_resp.status_code == 201
        api_data = api_resp.json()["data"]

    with factory_cli() as cli_db, factory_api() as api_db:
        cli_sid = cli_out["snapshot_id"]
        api_sid = api_data["snapshot_id"]
        # (1) checksum and (2) row count are identical.
        assert cli_out["checksum"] == api_data["checksum"]
        assert cli_out["draw_count"] == api_data["draw_count"]
        cli_rows = _payload_ordered(cli_db, cli_sid)
        api_rows = _payload_ordered(api_db, api_sid)
        assert len(cli_rows) == len(api_rows)
        # (3) content and (4) insertion order are identical.
        assert cli_rows == api_rows
        assert _insertion_order(cli_db, cli_sid) == _insertion_order(api_db, api_sid)
        # (5) final snapshot content hash identical (volatile fields excluded).
        assert _content_hash(cli_db, cli_sid) == _content_hash(api_db, api_sid)
