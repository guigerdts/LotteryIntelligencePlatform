"""E2E determinism: two identical seeded DBs produce byte-identical ML output.

T-23: same inputs ⇒ identical quantized fingerprint + checksum + metric rows.
"""

from __future__ import annotations

from decimal import Decimal

import sqlalchemy as sa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

_F4_FEATURES = [
    "consecutive_count",
    "gap_from_previous",
    "hot_cold_ratio",
    "frequency_percentile",
    "position_weighted_freq",
    "sum_spread",
    "modular_pattern",
    "pair_density",
    "odd_even_ratio",
    "repeated_from_previous",
]


def _seed_db(session: Session, lottery_id: int) -> None:
    """Seed lottery + draws + F4 features."""
    session.execute(
        sa.text(
            "INSERT INTO lottery (id, code, name, country, "
            "min_number, max_number, numbers_to_select, created_at) "
            "VALUES (:id, :code, :name, :country, 1, 50, 6, "
            "datetime('now'))"
        ),
        {
            "id": lottery_id,
            "code": f"L{lottery_id}",
            "name": f"Lot {lottery_id}",
            "country": "AR",
        },
    )
    for i in range(1, 13):
        session.execute(
            sa.text(
                "INSERT INTO draw (lottery_id, draw_number, draw_date, "
                "is_deleted, created_at) "
                "VALUES (:lid, :dn, :dd, 0, datetime('now'))"
            ),
            {"lid": lottery_id, "dn": i, "dd": f"2024-01-{i:02d}"},
        )
        draw_id = session.execute(
            sa.text("SELECT last_insert_rowid()")
        ).scalar()
        for n in range(1, 7):
            session.execute(
                sa.text(
                    "INSERT INTO draw_numbers (draw_id, number, position) "
                    "VALUES (:did, :num, :pos)"
                ),
                {"did": draw_id, "num": n + (i % 10), "pos": n},
            )
    session.execute(
        sa.text(
            "INSERT INTO feature_snapshots "
            "(lottery_id, feature_set, version, feature_engine_version, "
            "checksum, input_fingerprint, draws_from, draws_to, "
            "draw_count, status, is_locked, created_at, updated_at) "
            "VALUES (:lid, 'core', '1', '1.0.0', 'abc', 'fp', "
            "1, 12, 12, 'active', 1, datetime('now'), datetime('now'))"
        ),
        {"lid": lottery_id},
    )
    snap_id = session.execute(
        sa.text("SELECT last_insert_rowid()")
    ).scalar()
    for draw_num in range(1, 13):
        for fid in _F4_FEATURES:
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
                    "val": float(Decimal(str(0.01 * draw_num))),
                },
            )
    session.flush()


def test_determinism_two_runs(
    session_factory: sessionmaker, client: TestClient
) -> None:
    """Two train runs on the same DB produce identical checksums."""
    db = session_factory()
    try:
        _seed_db(db, 1)
        db.commit()
    finally:
        db.close()

    def _train() -> dict:
        resp = client.post(
            "/api/v1/ml/train",
            params={"lottery_id": 1},
        )
        assert resp.status_code in (200, 201), resp.text
        return resp.json()

    result1 = _train()
    result2 = _train()

    # Compare data only — timestamp naturally differs between runs
    assert result1["data"] == result2["data"], (
        f"Data differs: {result1['data']} vs {result2['data']}"
    )
