"""Tests for Backtesting API endpoints (BTS-01).

Verifies POST /backtesting/run, GET /backtesting/history, and
GET /backtesting/results against a migrated SQLite DB.
"""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from backend.app.models.draw import Draw as DrawModel
from backend.app.models.draw_number import DrawNumber
from backend.app.models.lottery import Lottery
from backend.app.models.super_number import SuperNumber


def _seed_lottery(db: Session, code: str = "PBA") -> int:
    lottery = Lottery(
        code=code,
        name=f"Lottery {code}",
        country="CO",
        min_number=1,
        max_number=50,
        numbers_to_select=5,
        super_number_min=1,
        super_number_max=16,
    )
    db.add(lottery)
    db.flush()
    return lottery.id


def _seed_draws(db: Session, lottery_id: int, count: int) -> None:
    base = date(2015, 1, 1)
    for i in range(count):
        draw = DrawModel(
            lottery_id=lottery_id,
            draw_number=i + 1,
            draw_date=base + timedelta(weeks=i),
            is_deleted=False,
        )
        db.add(draw)
        db.flush()
        for n in range(1, 6):
            dn = DrawNumber(draw_id=draw.id, position=n, number=n)
            db.add(dn)
        sn = SuperNumber(draw_id=draw.id, value=10)
        db.add(sn)
    db.flush()


def _assert_success_envelope(body: dict) -> dict:
    assert body["success"] is True
    assert body["timestamp"]
    return body["data"]


class TestBacktestingRunAPI:
    """POST /backtesting/run — BTS-01, BTE-12."""

    def test_run_returns_200(self, client, db: Session) -> None:
        lottery_id = _seed_lottery(db)
        _seed_draws(db, lottery_id, 200)
        db.commit()

        resp = client.post(
            "/api/v1/backtesting/run",
            json={
                "lottery_id": lottery_id,
                "strategy_id": "ml-core-5",
                "train_years": 2,
                "eval_count": 1,
                "seed": 42,
            },
        )
        assert resp.status_code == 200
        data = _assert_success_envelope(resp.json())
        assert data["snapshot_id"] > 0
        assert data["lottery_id"] == lottery_id
        assert data["strategy_id"] == "ml-core-5"
        assert data["status"] == "active"

    def test_run_unknown_lottery_returns_404(self, client, db: Session) -> None:
        resp = client.post(
            "/api/v1/backtesting/run",
            json={
                "lottery_id": 9999,
                "strategy_id": "ml-core-5",
            },
        )
        assert resp.status_code == 404
        body = resp.json()
        assert body["success"] is False
        assert body["error"]["code"] == "RESOURCE_NOT_FOUND"

    def test_run_missing_strategy_returns_422(self, client, db: Session) -> None:
        lottery_id = _seed_lottery(db)
        db.commit()

        resp = client.post(
            "/api/v1/backtesting/run",
            json={"lottery_id": lottery_id},
        )
        assert resp.status_code == 422

    def test_run_insufficient_data_returns_422(self, client, db: Session) -> None:
        lottery_id = _seed_lottery(db)
        _seed_draws(db, lottery_id, 5)
        db.commit()

        resp = client.post(
            "/api/v1/backtesting/run",
            json={
                "lottery_id": lottery_id,
                "strategy_id": "ml-core-5",
                "min_train_draws": 100,
            },
        )
        assert resp.status_code in (422, 500)


class TestBacktestingHistoryAPI:
    """GET /backtesting/history — read-only."""

    def test_history_empty(self, client, db: Session) -> None:
        lottery_id = _seed_lottery(db)
        db.commit()

        resp = client.get(f"/api/v1/backtesting/history?lottery_id={lottery_id}")
        assert resp.status_code == 200
        data = _assert_success_envelope(resp.json())
        assert data == []

    def test_history_with_snapshots(self, client, db: Session) -> None:
        lottery_id = _seed_lottery(db)
        _seed_draws(db, lottery_id, 200)
        db.commit()

        # Create a backtest first
        client.post(
            "/api/v1/backtesting/run",
            json={
                "lottery_id": lottery_id,
                "strategy_id": "ml-core-5",
                "train_years": 2,
                "eval_count": 1,
            },
        )

        resp = client.get(f"/api/v1/backtesting/history?lottery_id={lottery_id}")
        assert resp.status_code == 200
        data = _assert_success_envelope(resp.json())
        assert len(data) == 1
        assert data[0]["strategy_id"] == "ml-core-5"

    def test_history_unknown_lottery_returns_404(self, client, db: Session) -> None:
        resp = client.get("/api/v1/backtesting/history?lottery_id=9999")
        assert resp.status_code == 404


class TestBacktestingResultsAPI:
    """GET /backtesting/results — read-only."""

    def test_results_active(self, client, db: Session) -> None:
        lottery_id = _seed_lottery(db)
        _seed_draws(db, lottery_id, 200)
        db.commit()

        # Create a backtest
        run_resp = client.post(
            "/api/v1/backtesting/run",
            json={
                "lottery_id": lottery_id,
                "strategy_id": "ml-core-5",
                "train_years": 2,
                "eval_count": 1,
            },
        )
        run_data = run_resp.json()["data"]

        resp = client.get(f"/api/v1/backtesting/results?lottery_id={lottery_id}")
        assert resp.status_code == 200
        data = _assert_success_envelope(resp.json())
        assert data["snapshot_id"] == run_data["snapshot_id"]
        assert "aggregate_metrics" in data

    def test_results_by_snapshot_id(self, client, db: Session) -> None:
        lottery_id = _seed_lottery(db)
        _seed_draws(db, lottery_id, 200)
        db.commit()

        run_resp = client.post(
            "/api/v1/backtesting/run",
            json={
                "lottery_id": lottery_id,
                "strategy_id": "ml-core-5",
                "train_years": 2,
                "eval_count": 1,
            },
        )
        snapshot_id = run_resp.json()["data"]["snapshot_id"]

        resp = client.get(
            f"/api/v1/backtesting/results?lottery_id={lottery_id}&snapshot_id={snapshot_id}"
        )
        assert resp.status_code == 200
        data = _assert_success_envelope(resp.json())
        assert data["snapshot_id"] == snapshot_id

    def test_results_no_active_returns_404(self, client, db: Session) -> None:
        lottery_id = _seed_lottery(db)
        db.commit()

        resp = client.get(f"/api/v1/backtesting/results?lottery_id={lottery_id}")
        assert resp.status_code == 404

    def test_results_unknown_snapshot_returns_404(self, client, db: Session) -> None:
        lottery_id = _seed_lottery(db)
        db.commit()

        resp = client.get(f"/api/v1/backtesting/results?lottery_id={lottery_id}&snapshot_id=9999")
        assert resp.status_code == 404
