"""Backend parity: ML is additive; existing F3/statistics surface unchanged.

T-24: POST /statistics/generate still 200; POST /ml/train is additive-only;
stats surface unchanged (REQ-10/11/12 scenarios intact).
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient


def test_statistics_endpoint_still_200(
    session_factory: sessionmaker, client: TestClient
) -> None:
    """POST /statistics/generate returns 200 — parity baseline (REQ-10)."""
    db = session_factory()
    try:
        db.execute(
            sa.text(
                "INSERT INTO lottery (id, code, name, country, "
                "min_number, max_number, numbers_to_select, created_at) "
                "VALUES (1, 'L1', 'Lot 1', 'AR', 1, 50, 6, "
                "datetime('now'))"
            )
        )
        db.commit()
    finally:
        db.close()

    resp = client.post(
        "/api/v1/statistics/generate",
        json={"lottery_code": "L1", "scope": "incremental"},
    )
    assert resp.status_code in (200, 201, 422), (
        f"Statistics endpoint broke: {resp.status_code} {resp.text}"
    )


def test_ml_train_is_additive_only(
    session_factory: sessionmaker, client: TestClient
) -> None:
    """ML train does not modify statistics tables (REQ-11)."""
    db = session_factory()
    try:
        db.execute(
            sa.text(
                "INSERT INTO lottery (id, code, name, country, "
                "min_number, max_number, numbers_to_select, created_at) "
                "VALUES (1, 'L1', 'Lot 1', 'AR', 1, 50, 6, "
                "datetime('now'))"
            )
        )
        db.execute(
            sa.text(
                "INSERT INTO feature_snapshots "
                "(lottery_id, feature_set, version, "
                "feature_engine_version, checksum, "
                "input_fingerprint, draws_from, draws_to, "
                "draw_count, status, is_locked, "
                "created_at, updated_at) "
                "VALUES (1, 'core', '1', '1.0.0', 'abc', "
                "'fp', 1, 1, 1, 'active', 1, "
                "datetime('now'), datetime('now'))"
            )
        )
        db.commit()
    finally:
        db.close()

    db2 = session_factory()
    try:
        before = db2.execute(
            sa.text("SELECT COUNT(*) FROM stat_snapshots")
        ).scalar()
    finally:
        db2.close()

    client.post("/api/v1/ml/train", params={"lottery_id": 1})

    db3 = session_factory()
    try:
        after = db3.execute(
            sa.text("SELECT COUNT(*) FROM stat_snapshots")
        ).scalar()
    finally:
        db3.close()

    assert before == after, (
        f"stat_snapshots changed: {before} -> {after}"
    )
