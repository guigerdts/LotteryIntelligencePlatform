"""Unit tests for dl.providers — Provider Protocols (DLE-13)."""

from __future__ import annotations

from collections.abc import Iterator

from backend.app.dl.providers import (
    DrawHistoryProvider,
    DrawRow,
    FeatureRow,
    FeatureSnapshotProvider,
)


def test_draw_row_frozen() -> None:
    """DrawRow is immutable (frozen dataclass)."""
    row = DrawRow(draw_number=1, numbers=(1, 2, 3))
    assert row.draw_number == 1
    assert row.numbers == (1, 2, 3)
    with pytest.raises(AttributeError):
        row.draw_number = 2  # type: ignore[misc]


def test_feature_row_frozen() -> None:
    """FeatureRow is immutable (frozen dataclass)."""
    row = FeatureRow(feature_id="f1", draw_number=1, value=0.5)
    assert row.feature_id == "f1"
    assert row.draw_number == 1
    assert row.value == 0.5
    with pytest.raises(AttributeError):
        row.value = 0.9  # type: ignore[misc]


def test_draw_history_provider_is_protocol() -> None:
    """DrawHistoryProvider is a Protocol (DLE-13)."""
    from typing import Protocol

    assert issubclass(DrawHistoryProvider, Protocol)


def test_feature_snapshot_provider_is_protocol() -> None:
    """FeatureSnapshotProvider is a Protocol (DLE-13)."""
    from typing import Protocol

    assert issubclass(FeatureSnapshotProvider, Protocol)


def test_mock_provider_satisfies_protocol() -> None:
    """A mock implementing the Protocol接口 passes static check."""

    class _MockDrawProvider:
        def iter_draws(
            self, lottery_id: int, *, after_draw_number: int | None = None
        ) -> Iterator[DrawRow]:
            return iter([DrawRow(draw_number=1, numbers=(1, 2, 3))])

    class _MockFeatureProvider:
        def active_snapshot_id(self, lottery_id: int) -> int | None:
            return 1

        def feature_rows(self, snapshot_id: int) -> Iterator[FeatureRow]:
            return iter([FeatureRow(feature_id="f1", draw_number=1, value=0.5)])

    draw_prov: DrawHistoryProvider = _MockDrawProvider()
    feat_prov: FeatureSnapshotProvider = _MockFeatureProvider()
    assert draw_prov.iter_draws(1) is not None
    assert feat_prov.active_snapshot_id(1) == 1


def test_no_ml_imports() -> None:
    """dl/providers.py has zero imports from ml/ (DLE-13)."""
    import importlib

    from backend.app.dl import providers

    # The module itself should not import from backend.app.ml
    mod = importlib.import_module(providers.__name__)
    for attr in vars(mod).values():
        mod_name = getattr(attr, "__module__", None)
        if isinstance(mod_name, str):
            assert not mod_name.startswith("backend.app.ml"), (
                f"dl/providers.py references ml module {mod_name!r}"
            )


# Needed for frozen dataclass tests
import pytest  # noqa: E402
