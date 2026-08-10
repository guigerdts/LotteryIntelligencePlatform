"""Tests for StrategyProtocol and adapters (BTE-03, BTE-11).

Verifies protocol compliance, adapter isolation, and lazy import
behaviour.
"""

from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path

from backend.app.backtesting.strategy import (
    DLStrategyAdapter,
    MLStrategyAdapter,
    StrategyProtocol,
)
from backend.app.backtesting.types import DrawContext

_STRATEGY_SRC = (
    Path(__file__).resolve().parents[2] / "src" / "backend" / "app" / "backtesting" / "strategy.py"
)

_FORBIDDEN_PREFIXES = (
    "backend.app.ml",
    "backend.app.dl",
    "backend.app.opt",
    "backend.app.services",
    "backend.app.repositories",
)


def _top_level_imports(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    """Return only module-level import nodes (not inside functions/classes)."""
    return [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]


def _check_forbidden(tree: ast.Module, prefixes: tuple[str, ...]) -> None:
    """Raise AssertionError if any top-level import matches *prefixes*."""
    for node in _top_level_imports(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for prefix in prefixes:
                    assert not alias.name.startswith(prefix), (
                        f"Module-level import of {prefix}: {alias.name}"
                    )
        if isinstance(node, ast.ImportFrom):
            if node.module:
                for prefix in prefixes:
                    assert not node.module.startswith(prefix), (
                        f"Module-level import of {prefix}: {node.module}"
                    )


# ---------------------------------------------------------------------------
# Concrete strategy for protocol compliance testing
# ---------------------------------------------------------------------------


class _DummyStrategy:
    """Minimal strategy that satisfies StrategyProtocol."""

    @property
    def strategy_id(self) -> str:
        return "dummy-v1"

    def predict(self, draw_context: DrawContext) -> list[int]:
        return [1, 2, 3, 4, 5]


class TestStrategyProtocol:
    """Protocol compliance (BTE-03)."""

    def test_dummy_satisfies_protocol(self) -> None:
        assert isinstance(_DummyStrategy(), StrategyProtocol)

    def test_protocol_has_strategy_id(self) -> None:
        assert hasattr(StrategyProtocol, "strategy_id")

    def test_protocol_has_predict(self) -> None:
        assert hasattr(StrategyProtocol, "predict")

    def test_dummy_strategy_id(self) -> None:
        s = _DummyStrategy()
        assert s.strategy_id == "dummy-v1"

    def test_dummy_predict_returns_list(self) -> None:
        s = _DummyStrategy()
        ctx = DrawContext(
            lottery_id=1,
            draw_date=datetime(2024, 1, 1),
            historical_draws=(),
        )
        result = s.predict(ctx)
        assert isinstance(result, list)
        assert all(isinstance(n, int) for n in result)


class TestMLStrategyAdapter:
    """ML adapter isolation (BTE-11)."""

    def test_strategy_id_format(self) -> None:
        adapter = MLStrategyAdapter(ml_engine=None, model_set="core-5")
        assert adapter.strategy_id == "ml-core-5"

    def test_default_model_set(self) -> None:
        adapter = MLStrategyAdapter(ml_engine=None)
        assert adapter.strategy_id == "ml-core-5"

    def test_no_module_level_ml_import(self) -> None:
        """BTE-11: strategy.py must not import ml at module level."""
        tree = ast.parse(_STRATEGY_SRC.read_text())
        ml_only = ("backend.app.ml",)
        _check_forbidden(tree, ml_only)


class TestDLStrategyAdapter:
    """DL adapter isolation (BTE-11)."""

    def test_strategy_id_format(self) -> None:
        adapter = DLStrategyAdapter(dl_engine=None, model_set="core-3")
        assert adapter.strategy_id == "dl-core-3"

    def test_default_model_set(self) -> None:
        adapter = DLStrategyAdapter(dl_engine=None)
        assert adapter.strategy_id == "dl-core-3"

    def test_no_module_level_dl_import(self) -> None:
        """BTE-11: strategy.py must not import dl at module level."""
        tree = ast.parse(_STRATEGY_SRC.read_text())
        dl_only = ("backend.app.dl",)
        _check_forbidden(tree, dl_only)


class TestAdapterIsolation:
    """No module-level imports of ml/dl/opt/services/repositories (BTE-11)."""

    def test_strategy_module_isolation(self) -> None:
        """strategy.py must not import any engine or service at module level."""
        tree = ast.parse(_STRATEGY_SRC.read_text())
        _check_forbidden(tree, _FORBIDDEN_PREFIXES)
