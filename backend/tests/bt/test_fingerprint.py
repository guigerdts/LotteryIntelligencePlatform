"""Tests for fingerprint computation (BTE-06, BTE-18).

Verifies idempotency, input sensitivity, and that walk-forward config
parameters affect the fingerprint.
"""

from __future__ import annotations

from backend.app.backtesting.fingerprint import compute_bt_fingerprint
from backend.app.backtesting.types import BacktestConfig

_CFG = BacktestConfig()
_DATA_HASH = "a" * 64


class TestFingerprintIdempotency:
    """Same inputs always produce the same fingerprint."""

    def test_same_inputs_same_fingerprint(self) -> None:
        fp1 = compute_bt_fingerprint(
            strategy_id="ml-core-5",
            config=_CFG,
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        fp2 = compute_bt_fingerprint(
            strategy_id="ml-core-5",
            config=_CFG,
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        assert fp1 == fp2

    def test_fingerprint_is_hex_64(self) -> None:
        fp = compute_bt_fingerprint(
            strategy_id="ml-core-5",
            config=_CFG,
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        assert len(fp) == 64
        assert all(c in "0123456789abcdef" for c in fp)


class TestFingerprintInputSensitivity:
    """Any input change must produce a different fingerprint."""

    def test_strategy_id_changes_fingerprint(self) -> None:
        base = compute_bt_fingerprint(
            strategy_id="ml-core-5",
            config=_CFG,
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        changed = compute_bt_fingerprint(
            strategy_id="ml-core-10",
            config=_CFG,
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        assert base != changed

    def test_data_hash_changes_fingerprint(self) -> None:
        base = compute_bt_fingerprint(
            strategy_id="ml-core-5",
            config=_CFG,
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        changed = compute_bt_fingerprint(
            strategy_id="ml-core-5",
            config=_CFG,
            data_hash="b" * 64,
            benchmark_type="both",
        )
        assert base != changed

    def test_benchmark_type_changes_fingerprint(self) -> None:
        base = compute_bt_fingerprint(
            strategy_id="ml-core-5",
            config=_CFG,
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        changed = compute_bt_fingerprint(
            strategy_id="ml-core-5",
            config=_CFG,
            data_hash=_DATA_HASH,
            benchmark_type="uniform",
        )
        assert base != changed


class TestFingerprintConfigSensitivity:
    """Walk-forward config parameters affect the fingerprint (BTE-18)."""

    def test_train_years_affects_fingerprint(self) -> None:
        base = compute_bt_fingerprint(
            strategy_id="s",
            config=BacktestConfig(train_years=5),
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        changed = compute_bt_fingerprint(
            strategy_id="s",
            config=BacktestConfig(train_years=3),
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        assert base != changed

    def test_eval_count_affects_fingerprint(self) -> None:
        base = compute_bt_fingerprint(
            strategy_id="s",
            config=BacktestConfig(eval_count=1),
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        changed = compute_bt_fingerprint(
            strategy_id="s",
            config=BacktestConfig(eval_count=2),
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        assert base != changed

    def test_step_count_affects_fingerprint(self) -> None:
        base = compute_bt_fingerprint(
            strategy_id="s",
            config=BacktestConfig(step_count=1),
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        changed = compute_bt_fingerprint(
            strategy_id="s",
            config=BacktestConfig(step_count=2),
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        assert base != changed

    def test_min_train_draws_affects_fingerprint(self) -> None:
        base = compute_bt_fingerprint(
            strategy_id="s",
            config=BacktestConfig(min_train_draws=100),
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        changed = compute_bt_fingerprint(
            strategy_id="s",
            config=BacktestConfig(min_train_draws=50),
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        assert base != changed

    def test_seed_affects_fingerprint(self) -> None:
        base = compute_bt_fingerprint(
            strategy_id="s",
            config=BacktestConfig(seed=42),
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        changed = compute_bt_fingerprint(
            strategy_id="s",
            config=BacktestConfig(seed=123),
            data_hash=_DATA_HASH,
            benchmark_type="both",
        )
        assert base != changed
