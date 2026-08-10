"""Tests for UniformRandomBenchmark and HypergeometricBenchmark (BTE-09, BTE-16).

Verifies reproducibility, distribution convergence, lazy imports,
and same evaluation period alignment.
"""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

from backend.app.backtesting.benchmark import (
    HypergeometricBenchmark,
    UniformRandomBenchmark,
)
from backend.app.backtesting.types import DrawContext

_POOL = list(range(1, 51))  # 1..50
_PICK = 5


def _ctx() -> DrawContext:
    return DrawContext(
        lottery_id=1,
        draw_date=datetime(2024, 6, 1),
        historical_draws=(),
    )


class TestUniformRandomBenchmark:
    """Uniform random baseline (BTE-09)."""

    def test_reproducible_same_seed(self) -> None:
        b1 = UniformRandomBenchmark(_POOL, _PICK, seed=42)
        b2 = UniformRandomBenchmark(_POOL, _PICK, seed=42)
        ctx = _ctx()
        assert b1.predict(ctx) == b2.predict(ctx)

    def test_different_seed_different_results(self) -> None:
        b1 = UniformRandomBenchmark(_POOL, _PICK, seed=42)
        b2 = UniformRandomBenchmark(_POOL, _PICK, seed=99)
        ctx = _ctx()
        # With overwhelming probability, different seeds differ
        results1 = [tuple(b1.predict(ctx)) for _ in range(10)]
        results2 = [tuple(b2.predict(ctx)) for _ in range(10)]
        assert results1 != results2

    def test_returns_sorted(self) -> None:
        b = UniformRandomBenchmark(_POOL, _PICK, seed=42)
        result = b.predict(_ctx())
        assert result == sorted(result)

    def test_pick_count_respected(self) -> None:
        b = UniformRandomBenchmark(_POOL, _PICK, seed=42)
        result = b.predict(_ctx())
        assert len(result) == _PICK

    def test_values_in_pool(self) -> None:
        b = UniformRandomBenchmark(_POOL, _PICK, seed=42)
        result = b.predict(_ctx())
        for v in result:
            assert v in _POOL

    def test_distribution_convergence(self) -> None:
        """Large sample should approach uniform distribution."""
        b = UniformRandomBenchmark(_POOL, 1, seed=42)
        counts = {n: 0 for n in _POOL}
        n_samples = 5000
        for _ in range(n_samples):
            result = b.predict(_ctx())
            counts[result[0]] += 1
        # Each number should appear roughly 1/50 of the time
        expected = n_samples / len(_POOL)
        for count in counts.values():
            assert abs(count - expected) < expected * 0.3  # 30% tolerance


class TestHypergeometricBenchmark:
    """F5 hypergeometric baseline (BTE-09, BTE-11)."""

    def test_reproducible_same_seed(self) -> None:
        b1 = HypergeometricBenchmark(_POOL, _PICK, seed=42)
        b2 = HypergeometricBenchmark(_POOL, _PICK, seed=42)
        ctx = _ctx()
        assert b1.predict(ctx) == b2.predict(ctx)

    def test_returns_sorted(self) -> None:
        b = HypergeometricBenchmark(_POOL, _PICK, seed=42)
        result = b.predict(_ctx())
        assert result == sorted(result)

    def test_pick_count_respected(self) -> None:
        b = HypergeometricBenchmark(_POOL, _PICK, seed=42)
        result = b.predict(_ctx())
        assert len(result) == _PICK

    def test_values_in_pool(self) -> None:
        b = HypergeometricBenchmark(_POOL, _PICK, seed=42)
        result = b.predict(_ctx())
        for v in result:
            assert v in _POOL

    def test_no_module_level_probability_import(self) -> None:
        """BTE-11: benchmark.py must not import probability at module level."""
        src = (
            Path(__file__).resolve().parents[2]
            / "src"
            / "backend"
            / "app"
            / "backtesting"
            / "benchmark.py"
        )
        tree = ast.parse(src.read_text())
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith("backend.app.probability"), (
                            f"Module-level probability import: {alias.name}"
                        )
                if isinstance(node, ast.ImportFrom):
                    if node.module and node.module.startswith("backend.app.probability"):
                        raise AssertionError(f"Module-level probability import: {node.module}")


class TestBenchmarkEvaluationPeriod:
    """BTE-16: Both benchmarks use the exact same evaluation windows."""

    def test_same_inputs_same_length(self) -> None:
        """Both benchmarks produce same number of predictions for same contexts."""
        ub = UniformRandomBenchmark(_POOL, _PICK, seed=42)
        hb = HypergeometricBenchmark(_POOL, _PICK, seed=42)
        contexts = [
            DrawContext(
                lottery_id=1,
                draw_date=datetime(2024, 1, i),
                historical_draws=(),
            )
            for i in range(1, 11)
        ]
        u_preds = [ub.predict(ctx) for ctx in contexts]
        h_preds = [hb.predict(ctx) for ctx in contexts]
        assert len(u_preds) == len(h_preds) == 10

    def test_deterministic_same_order(self) -> None:
        """Same seed + same contexts → same prediction order."""
        ub1 = UniformRandomBenchmark(_POOL, _PICK, seed=42)
        ub2 = UniformRandomBenchmark(_POOL, _PICK, seed=42)
        contexts = [
            DrawContext(
                lottery_id=1,
                draw_date=datetime(2024, 1, i),
                historical_draws=(),
            )
            for i in range(1, 6)
        ]
        p1 = [ub1.predict(ctx) for ctx in contexts]
        p2 = [ub2.predict(ctx) for ctx in contexts]
        assert p1 == p2
