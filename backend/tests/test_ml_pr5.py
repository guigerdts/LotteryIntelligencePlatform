"""PR5 gates for Fase 7 ML: API endpoints + CLI subcommands.

Tests the ML router endpoints (POST /ml/train, GET /ml/models, GET /ml/metrics)
and verifies CLI subcommands parse correctly. Uses the conftest fixtures for DB
migration and test client.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from backend.app.main import create_app
from backend.app.repositories.base import get_db

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_F4_FEATURES = [
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


def _seed_lottery(session: Session, lottery_id: int = 1) -> None:
    """Insert a minimal lottery row."""
    session.execute(
        sa.text(
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


def _seed_draws(session: Session, lottery_id: int, count: int = 12) -> None:
    """Insert minimal draw rows with numbers."""

    for i in range(1, count + 1):
        session.execute(
            sa.text(
                "INSERT INTO draw (lottery_id, draw_number, draw_date, is_deleted, created_at) "
                "VALUES (:lid, :dn, :dd, 0, datetime('now'))"
            ),
            {"lid": lottery_id, "dn": i, "dd": f"2024-01-{i:02d}"},
        )
        draw_id = session.execute(sa.text("SELECT last_insert_rowid()")).scalar()
        for n in range(1, 7):
                session.execute(
                    sa.text(
                        "INSERT INTO draw_numbers (draw_id, number, position) "
                        "VALUES (:did, :num, :pos)"
                    ),
                {"did": draw_id, "num": n + (i % 10), "pos": n},
            )
    session.flush()


def _seed_f4_snapshot(session: Session, lottery_id: int) -> None:
    """Insert a feature snapshot + values for all 10 features across 12 draws."""

    session.execute(
        sa.text(
            "INSERT INTO feature_snapshots "
            "(lottery_id, feature_set, version, feature_engine_version, "
            "checksum, input_fingerprint, draws_from, draws_to, "
            "draw_count, status, is_locked, created_at, updated_at) "
            "VALUES (:lid, 'core', '1', '1.0.0', 'abc', 'test_fp', "
            "1, 12, 12, 'active', 1, datetime('now'), datetime('now'))"
        ),
        {"lid": lottery_id},
    )
    snap_id = session.execute(sa.text("SELECT last_insert_rowid()")).scalar()

    for draw_num in range(1, 13):
        for j, fid in enumerate(_F4_FEATURES):
            session.execute(
                sa.text(
                    "INSERT INTO feature_values "
                    "(snapshot_id, feature_id, feature_version, "
                    "draw_number, value) "
                    "VALUES (:sid, :fid, '1', :dn, :val)"
                ),
                {
                    "sid": snap_id,
                    "fid": fid,
                    "dn": draw_num,
                    "val": float(j * 0.1 + draw_num * 0.01),
                },
            )
    session.flush()


# ---------------------------------------------------------------------------
# API Tests
# ---------------------------------------------------------------------------


class TestMlApi:
    """ML API endpoint gates."""

    def test_train_endpoint(self, migrated_db, session_factory: sessionmaker) -> None:
        """POST /ml/train returns 200 with training results."""
        session: Session = session_factory()
        _seed_lottery(session)
        _seed_draws(session, 1)
        _seed_f4_snapshot(session, 1)
        session.commit()

        app = create_app()

        def override():
            s = session_factory()
            try:
                yield s
            except Exception:
                s.rollback()
                raise
            finally:
                s.close()

        app.dependency_overrides[get_db] = override

        with TestClient(app) as client:
            resp = client.post("/api/v1/ml/train", params={"lottery_id": 1})
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert data["lottery_id"] == 1
            assert len(data["results"]) == 5  # all core-5 families
            for r in data["results"]:
                assert r["status"] in ("active", "failed")

    def test_train_with_family(self, migrated_db, session_factory: sessionmaker) -> None:
        """POST /ml/train with family trains one model."""
        session: Session = session_factory()
        _seed_lottery(session)
        _seed_draws(session, 1)
        _seed_f4_snapshot(session, 1)
        session.commit()

        app = create_app()

        def override():
            s = session_factory()
            try:
                yield s
            except Exception:
                s.rollback()
                raise
            finally:
                s.close()

        app.dependency_overrides[get_db] = override

        with TestClient(app) as client:
            resp = client.post(
                "/api/v1/ml/train",
                params={"lottery_id": 1, "family": "random_forest"},
            )
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert len(data["results"]) == 1
            assert data["results"][0]["family"] == "random_forest"

    def test_models_404(self, migrated_db, session_factory: sessionmaker) -> None:
        """GET /ml/models for unknown lottery returns 404.

        Uses the migrated session DB via dependency override, like the other
        tests in this class — never the dev ``lottery.db`` (absent in CI).
        """
        app = create_app()

        def override():
            s = session_factory()
            try:
                yield s
            except Exception:
                s.rollback()
                raise
            finally:
                s.close()

        app.dependency_overrides[get_db] = override

        with TestClient(app) as client:
            resp = client.get("/api/v1/ml/models", params={"lottery_id": 999})
            assert resp.status_code == 404

    def test_metrics_endpoint(self, migrated_db, session_factory: sessionmaker) -> None:
        """GET /ml/metrics returns metric rows (empty if no active snapshot)."""
        session: Session = session_factory()
        _seed_lottery(session)
        session.commit()

        app = create_app()

        def override():
            s = session_factory()
            try:
                yield s
            except Exception:
                s.rollback()
                raise
            finally:
                s.close()

        app.dependency_overrides[get_db] = override

        with TestClient(app) as client:
            resp = client.get("/api/v1/ml/metrics", params={"lottery_id": 1})
            assert resp.status_code == 200
            data = resp.json()["data"]
            assert isinstance(data, list)
            assert len(data) == 0  # no active snapshot → empty


# ---------------------------------------------------------------------------
# CLI Tests
# ---------------------------------------------------------------------------


class TestMlCli:
    """ML CLI subcommand gates."""

    def test_cli_ml_help(self) -> None:
        """``lip ml --help`` exits cleanly."""
        from backend.app.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["ml", "--help"])
        assert exc_info.value.code == 0

    def test_cli_ml_train_help(self) -> None:
        """``lip ml train --help`` exits cleanly."""
        from backend.app.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["ml", "train", "--help"])
        assert exc_info.value.code == 0

    def test_cli_ml_models_help(self) -> None:
        """``lip ml models --help`` exits cleanly."""
        from backend.app.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["ml", "models", "--help"])
        assert exc_info.value.code == 0

    def test_cli_ml_metrics_help(self) -> None:
        """``lip ml metrics --help`` exits cleanly."""
        from backend.app.cli import main

        with pytest.raises(SystemExit) as exc_info:
            main(["ml", "metrics", "--help"])
        assert exc_info.value.code == 0
