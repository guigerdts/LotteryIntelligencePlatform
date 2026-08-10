"""StrategyProtocol and engine adapters (BTE-03, BTE-11).

Defines the generic ``StrategyProtocol`` that any backtest-compatible
strategy must satisfy, plus adapter classes that bridge ML/DL engines
into this protocol using lazy imports (BTE-11).
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from backend.app.backtesting.types import DrawContext


@runtime_checkable
class StrategyProtocol(Protocol):
    """Generic strategy contract for backtesting (BTE-03).

    Any class implementing ``strategy_id`` and ``predict`` can be
    consumed by the backtest engine.  The engine does **not** import
    ML/DL modules at module level (BTE-11); adapters handle the bridge.
    """

    @property
    def strategy_id(self) -> str:
        """Unique strategy identifier (e.g. ``ml-core-5``)."""
        ...

    def predict(self, draw_context: DrawContext) -> list[int]:
        """Return a sorted list of predicted numbers for *draw_context*."""
        ...


class MLStrategyAdapter:
    """Adapts an ML engine instance to ``StrategyProtocol`` (BTE-03, BTE-11).

    The ``ml.engine`` module is imported **lazily** inside ``predict``
    to avoid module-level coupling between ``backtesting`` and ``ml``.
    """

    def __init__(self, ml_engine: Any, *, model_set: str = "core-5") -> None:
        self._engine = ml_engine
        self._model_set = model_set

    @property
    def strategy_id(self) -> str:
        return f"ml-{self._model_set}"

    def predict(self, draw_context: DrawContext) -> list[int]:
        """Delegate to ``ml.engine.predict`` via lazy import (BTE-11)."""
        from backend.app.ml.engine import predict as ml_predict  # noqa: PLC0415

        return ml_predict(self._engine, draw_context)


class DLStrategyAdapter:
    """Adapts a DL engine instance to ``StrategyProtocol`` (BTE-03, BTE-11).

    The ``dl.engine`` module is imported **lazily** inside ``predict``
    to avoid module-level coupling between ``backtesting`` and ``dl``.
    """

    def __init__(self, dl_engine: Any, *, model_set: str = "core-3") -> None:
        self._engine = dl_engine
        self._model_set = model_set

    @property
    def strategy_id(self) -> str:
        return f"dl-{self._model_set}"

    def predict(self, draw_context: DrawContext) -> list[int]:
        """Delegate to ``dl.engine.predict`` via lazy import (BTE-11)."""
        from backend.app.dl.engine import predict as dl_predict  # noqa: PLC0415

        return dl_predict(self._engine, draw_context)
