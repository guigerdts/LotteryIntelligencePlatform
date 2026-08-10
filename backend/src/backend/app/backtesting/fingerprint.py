"""SHA-256 fingerprint computation for backtest snapshots (BTE-06, BTE-18).

The fingerprint encodes strategy identity, backtest configuration, dataset
fingerprint, seed, benchmark type, and generator version.  Any change to
these inputs produces a different fingerprint, ensuring idempotent
re-execution detection (BTE-10).
"""

from __future__ import annotations

import hashlib
import json

from backend.app.backtesting.types import BacktestConfig
from backend.app.backtesting.version import BACKTEST_GENERATOR_VERSION


def compute_bt_fingerprint(
    *,
    strategy_id: str,
    config: BacktestConfig,
    data_hash: str,
    benchmark_type: str,
) -> str:
    """Return a hex-encoded SHA-256 fingerprint for a backtest run.

    Inputs mixed into the digest (BTE-06, BTE-18):
    - ``strategy_id`` — identity of the strategy under test.
    - Walk-forward config fields that affect reproducibility:
      train_years, eval_count, step_count, min_train_draws, seed.
    - ``data_hash`` — SHA-256 of the dataset checksum.
    - ``benchmark_type`` — which benchmarks are active.
    - ``BACKTEST_GENERATOR_VERSION`` — generator version constant.

    The payload is JSON-serialised with ``sort_keys=True`` so that
    identical logical inputs always yield the same digest.
    """
    payload = json.dumps(
        {
            "strategy_id": strategy_id,
            "config": {
                "train_years": config.train_years,
                "eval_count": config.eval_count,
                "step_count": config.step_count,
                "min_train_draws": config.min_train_draws,
                "seed": config.seed,
            },
            "data_hash": data_hash,
            "benchmark_type": benchmark_type,
            "version": BACKTEST_GENERATOR_VERSION,
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()
