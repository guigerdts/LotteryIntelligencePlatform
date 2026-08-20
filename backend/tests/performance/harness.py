"""Custom backend performance harness (F17 TEST-006, ADR-6).

Repeated-sample measurement of realistic-but-lightweight ops with
mean/median/p95/std and IQR-based outliers per op, scored pass/fail against a
configured baseline +/- tolerance. Intentionally NOT pytest-benchmark (TEST-006
scenario 2). Ops (configured in ``config.yaml``, run in order):

- ``cold_start`` — fresh-interpreter import of ``backend.app.main`` +
  ``create_app()`` (real app import graph; DLE-17 keeps torch/sklearn lazy).
- ``cached_statistics_get`` — a ``GET /api/v1/statistics/PBA/frequencies`` served
  from the in-process LRU response cache (PFM-05) through the TestClient.
- ``parallel_bt_train`` — a small synthetic backtest via
  ``POST /api/v1/backtesting/run`` exercising the bounded ``ProcessPoolExecutor``
  path (4 walk-forward windows, 2 workers).

The app runs against a throwaway SQLite file migrated by alembic to head (same
approach as ``tests/conftest.py``); the dev ``database/lip.db`` is never opened.
Exit contract: 0 when every op measured and the report was written (perf
regressions are data, not workflow failures — this is NOT a PR gate); non-zero
on harness failure (config, setup, op error, or unwritable report). The run is
single-process, memory-bounded, and deterministic (fixed seeds, fixtures).
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import statistics
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import yaml

# <repo>/backend (this file lives at tests/performance/harness.py)
BACKEND_DIR = Path(__file__).resolve().parents[2]
ALEMBIC_INI = BACKEND_DIR / "alembic.ini"
LOG_FORMAT = "%(asctime)s|%(levelname)s|%(name)s|%(message)s"

logger = logging.getLogger("performance.harness")


class HarnessError(Exception):
    """A real harness failure (config, setup, or op error) — exit non-zero."""


def _configure_logging() -> None:
    """Set up the project log format on stdout (idempotent, non-forcing)."""
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT, stream=sys.stdout)


def _percentile(sorted_samples: list[float], p: float) -> float:
    """Linear-interpolated percentile over sorted samples (numpy-style, stdlib-only)."""
    if not sorted_samples:
        raise HarnessError("cannot compute percentile of an empty sample set")
    if len(sorted_samples) == 1:
        return sorted_samples[0]
    pos = p * (len(sorted_samples) - 1)
    lo, hi = int(pos), min(int(pos) + 1, len(sorted_samples) - 1)
    frac = pos - lo
    return sorted_samples[lo] + frac * (sorted_samples[hi] - sorted_samples[lo])


def _summarize(samples: list[float]) -> dict[str, Any]:
    """Compute mean/median/p95/std and IQR-fence outliers (Tukey fences)."""
    ordered = sorted(samples)
    q1, q3 = _percentile(ordered, 0.25), _percentile(ordered, 0.75)
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return {
        "mean": statistics.fmean(samples),
        "median": statistics.median(samples),
        "p95": _percentile(ordered, 0.95),
        "std": statistics.stdev(samples) if len(samples) > 1 else 0.0,
        "outliers": [x for x in samples if x < lo or x > hi],
    }


class AppContext:
    """One throwaway migrated SQLite DB and the app whose engine targets it."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="lip-perf-")
        self.db_path = Path(self._tmp.name) / "perf.db"

    def build_app(self) -> Any:
        """Migrate the tmp DB and return the app bound to it (env-first import)."""
        url = f"sqlite:///{self.db_path}"
        os.environ["LIP_DATABASE_URL"] = url
        sys.path.insert(0, str(BACKEND_DIR / "src"))
        from alembic.config import Config

        from alembic import command

        cfg = Config(str(ALEMBIC_INI))
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")  # same migration approach as tests/conftest.py

        # Imported after LIP_DATABASE_URL is set (app engine is built at import).
        from backend.app.main import create_app

        return create_app()

    def cleanup(self) -> None:
        """Remove the tmp DB directory (no dev lottery.db is ever touched)."""
        self._tmp.cleanup()


def _op_cold_start(ctx: AppContext, _cfg: dict[str, Any]) -> Callable[[], float]:
    """Fresh-interpreter import + create_app; every sample is a real cold start."""
    code = (
        f"import sys; sys.path.insert(0, {str(BACKEND_DIR / 'src')!r});"
        "import time;"
        "t0 = time.perf_counter();"
        "import backend.app.main;"
        "from backend.app.main import create_app;"
        "create_app();"
        "print(time.perf_counter() - t0)"
    )
    env = os.environ.copy()
    env["LIP_DATABASE_URL"] = f"sqlite:///{ctx.db_path}"

    def measure() -> float:
        proc = subprocess.run(
            [sys.executable, "-c", code],
            cwd=str(BACKEND_DIR),
            capture_output=True,
            text=True,
            timeout=300,
            env=env,
            check=False,
        )
        if proc.returncode != 0:
            raise HarnessError(f"cold-start subprocess failed: {proc.stderr[-500:]}")
        return float(proc.stdout.strip())

    return measure


def _seed_lottery_with_draws(session: Any, code: str, count: int, max_number: int) -> int:
    """Create a lottery plus ``count`` deterministic draws (harness fixture data)."""
    from backend.app.services.draw_service import DrawService
    from backend.app.services.lottery_service import LotteryService

    lottery = LotteryService(session).create(
        {
            "code": code,
            "name": f"Perf lottery {code}",
            "country": "AR",
            "min_number": 1,
            "max_number": max_number,
            "numbers_to_select": 4 if max_number == 9 else 5,
            "super_number_min": 1,
            "super_number_max": 3 if max_number == 9 else 16,
        }
    )
    for n in range(1, count + 1):
        numbers = [(x + (n - 1)) % max_number or max_number for x in range(1, 5)]
        if n % 2 == 0:
            numbers = numbers[1:] + numbers[:1]
        DrawService(session).create_draw_bundle(
            lottery_id=lottery.id,
            draw_number=n,
            draw_date=date(2024, 1, 1) + timedelta(days=n),
            numbers=numbers,
            super_number=((n - 1) % 3) + 1,
            jackpot=None if n % 2 == 0 else n * 1000,
            winners=None if n % 3 == 0 else n,
        )
    session.commit()
    return lottery.id


def _op_cached_statistics_get(ctx: AppContext, _cfg: dict[str, Any]) -> Callable[[], float]:
    """Generate a snapshot once, then measure cache-served frequency GETs."""
    app = ctx.build_app()  # sets LIP_DATABASE_URL before any app import
    from fastapi.testclient import TestClient

    from backend.app.repositories.base import SessionLocal
    from backend.app.services.statistics_service import StatisticsService

    with SessionLocal() as session:
        lottery_id = _seed_lottery_with_draws(session, "PBA", count=50, max_number=9)
        StatisticsService(session).generate(lottery_id=lottery_id, metric_set="core", scope="full")
        session.commit()
    client = TestClient(app)
    client.__enter__()  # lifespan boot (init_db targets the tmp DB only)

    def measure() -> float:
        t0 = time.perf_counter()
        resp = client.get("/api/v1/statistics/PBA/frequencies")
        dt = time.perf_counter() - t0
        if resp.status_code != 200:
            raise HarnessError(f"statistics GET failed: HTTP {resp.status_code}")
        return dt

    return measure


def _op_parallel_bt_train(ctx: AppContext, _cfg: dict[str, Any]) -> Callable[[], float]:
    """Seed a synthetic lottery/draws once, then measure parallel backtest runs."""
    app = ctx.build_app()  # sets LIP_DATABASE_URL before any app import
    from fastapi.testclient import TestClient

    from backend.app.models.draw import Draw as DrawModel
    from backend.app.models.draw_number import DrawNumber
    from backend.app.models.lottery import Lottery
    from backend.app.models.super_number import SuperNumber
    from backend.app.repositories.base import SessionLocal

    with SessionLocal() as session:
        lottery = Lottery(
            code="PBB",
            name="Perf lottery PBB",
            country="CO",
            min_number=1,
            max_number=50,
            numbers_to_select=5,
            super_number_min=1,
            super_number_max=16,
        )
        session.add(lottery)
        session.flush()
        base = date(2015, 1, 1)
        for i in range(120):  # 104 train + 4 windows x 1 eval + slack
            draw = DrawModel(
                lottery_id=lottery.id,
                draw_number=i + 1,
                draw_date=base + timedelta(weeks=i),
                is_deleted=False,
            )
            session.add(draw)
            session.flush()
            for n in range(1, 6):
                session.add(DrawNumber(draw_id=draw.id, position=n, number=n))
            session.add(SuperNumber(draw_id=draw.id, value=10))
        session.commit()
        lottery_id = lottery.id
    client = TestClient(app)
    client.__enter__()

    def measure() -> float:
        t0 = time.perf_counter()
        resp = client.post(
            "/api/v1/backtesting/run",
            json={
                "lottery_id": lottery_id,
                "strategy_id": "ml-core-5",
                "train_years": 2,
                "eval_count": 1,
                "step_count": 4,  # 4 windows -> bounded ProcessPoolExecutor path
                "min_train_draws": 100,
                "seed": 42,
            },
        )
        dt = time.perf_counter() - t0
        if resp.status_code != 200:
            raise HarnessError(f"backtest run failed: HTTP {resp.status_code}")
        return dt

    return measure


_OPS: dict[str, Callable[[AppContext, dict[str, Any]], Callable[[], float]]] = {
    "cold_start": _op_cold_start,
    "cached_statistics_get": _op_cached_statistics_get,
    "parallel_bt_train": _op_parallel_bt_train,
}


def run_harness(config: dict[str, Any], ctx: AppContext) -> dict[str, Any]:
    """Warm up each op, take ``runs`` samples, and score against baseline."""
    runs, warmup, tolerance = int(config["runs"]), int(config["warmup"]), float(config["tolerance"])
    results, failures = [], []
    for name, op_cfg in config["ops"].items():
        baseline, unit = float(op_cfg["baseline"]), str(op_cfg["unit"])
        try:
            measure = _OPS[name](ctx, op_cfg)
            for _ in range(warmup):
                measure()
            samples = [measure() for _ in range(runs)]
            stats = _summarize(samples)
            ok = baseline * (1 - tolerance) <= stats["mean"] <= baseline * (1 + tolerance)
            results.append(
                {
                    "op": name,
                    "unit": unit,
                    "samples": samples,
                    "mean": stats["mean"],
                    "median": stats["median"],
                    "p95": stats["p95"],
                    "std": stats["std"],
                    "outliers": stats["outliers"],
                    "baseline": baseline,
                    "tolerance": tolerance,
                    "pass": ok,
                }
            )
            logger.info(
                "op=%s measured: mean=%.4f%s pass=%s outliers=%d",
                name,
                stats["mean"],
                unit,
                ok,
                len(stats["outliers"]),
            )
        except Exception as exc:  # noqa: BLE001 - report the failure, keep going
            failures.append({"op": name, "error": f"{type(exc).__name__}: {exc}"})
            logger.error("op=%s failed: %s", name, exc)
    return {
        "harness": "backend/tests/performance/harness.py (TEST-006, ADR-6)",
        "generated_at": datetime.now(UTC).isoformat(),
        "config": {"runs": runs, "warmup": warmup, "tolerance": tolerance},
        "results": results,
        "failures": failures,
    }


def _load_config(path: Path) -> dict[str, Any]:
    """Load and validate the harness YAML configuration."""
    if not path.is_file():
        raise HarnessError(f"config not found: {path}")
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict) or "ops" not in config:
        raise HarnessError(f"invalid config {path}: missing 'ops' mapping")
    unknown = sorted(set(config["ops"]) - set(_OPS))
    if unknown:
        raise HarnessError(f"unknown ops in config: {', '.join(unknown)}")
    if int(config["runs"]) < 1 or int(config["warmup"]) < 0 or float(config["tolerance"]) <= 0:
        raise HarnessError("config requires runs>=1, warmup>=0, tolerance>0")
    return config


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: ``python tests/performance/harness.py --config <path>``."""
    _configure_logging()
    parser = argparse.ArgumentParser(description="F17 TEST-006 custom performance harness")
    parser.add_argument("--config", required=True, help="path to the YAML config")
    parser.add_argument(
        "--output", help="report JSON path (default: <config dir>/report-<ts>.json)"
    )
    args = parser.parse_args(argv)

    try:
        config = _load_config(Path(args.config))
        ctx = AppContext()
        report = run_harness(config, ctx)
        ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        default_out = Path(args.config).resolve().parent / f"report-{ts}.json"
        out = Path(args.output) if args.output else default_out
        out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        ctx.cleanup()
    except Exception as exc:  # noqa: BLE001 - harness-level failure -> non-zero
        logger.error("harness failed: %s", exc)
        return 1

    logger.info(
        "report written: %s (ops=%d, failures=%d)",
        out,
        len(report["results"]),
        len(report["failures"]),
    )
    return 0 if not report["failures"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
