"""Feature Engine pure-orchestrator determinism + future scheduling tests (FES-08, GF1).

The engine runs the registry's runnable features in topological order over a pure
``draw`` input and produces a deterministic ``feature_values`` sequence plus an input
fingerprint. GF2(b)/FES-08: a ``future-statistics`` feature stays declared but never
scheduled (produces no value). P1-01 determinism: same input yields identical output.
"""

from __future__ import annotations

from backend.app.feature_engineering.context import DrawRow, LotteryRules
from backend.app.feature_engineering.engine import ExecutionResult, FeatureEngine
from backend.app.feature_engineering.registry import FUTURE, FeatureDefinition, FeatureRegistry


def _def(
    feature_id: str,
    *,
    dependencies: tuple[str, ...] = (),
    source: str = "core",
) -> FeatureDefinition:
    return FeatureDefinition(
        id=feature_id,
        name=feature_id,
        category="core",
        description=f"{feature_id} feature",
        source=source,
        inputs=("draws",),
        algorithm=f"features/{feature_id}",
        params={},
        dependencies=dependencies,
        complexity="O(1)",
        version="1.0.0",
        status="active",
        history=(),
    )


def _draw(draw_number: int, numbers: tuple[int, ...]) -> DrawRow:
    return DrawRow(draw_number=draw_number, numbers=numbers)


def _sum_compute(ctx) -> int:
    return sum(ctx.draw.numbers)


def _flag_compute(ctx) -> int:
    """A dependent feature that folds its own deterministic value from the draw."""
    return 2 * sum(ctx.draw.numbers)


def test_engine_executes_single_base_feature_into_values() -> None:
    """A draw-sum feature sums the draw numbers into a per-draw value."""
    reg = FeatureRegistry()
    reg.register(_def("draw_sum"), _sum_compute)

    result = FeatureEngine(reg).execute(
        draws=[_draw(1, (1, 4, 7)), _draw(2, (5, 3, 8))],
        rules=LotteryRules(min_number=1, max_number=45, numbers_to_select=3),
    )
    assert isinstance(result, ExecutionResult)
    assert result.draw_numbers == (1, 2)
    # draw_sum computed for each draw in draw_number order.
    assert result.values["draw_sum"] == {1: 12, 2: 16}


def test_engine_future_statistics_feature_never_scheduled() -> None:
    """FE-08: a future-statistics feature is declared but produces NO persisted value."""
    reg = FeatureRegistry()
    reg.register(_def("draw_sum"), _sum_compute)
    reg.register(_def("correlation", source=FUTURE), _flag_compute)

    result = FeatureEngine(reg).execute(
        draws=[_draw(1, (1, 2, 3))],
        rules=LotteryRules(min_number=1, max_number=45, numbers_to_select=3),
    )
    assert set(result.values) == {"draw_sum"}
    assert "correlation" not in result.values


def test_engine_is_deterministic_same_input_same_values() -> None:
    """Same input yield bit-identical feature_values (GF1 engine-level)."""
    reg = FeatureRegistry()
    reg.register(_def("draw_sum"), _sum_compute)
    draws = [_draw(3, (10, 20, 30)), _draw(4, (1, 2))]
    rules = LotteryRules(min_number=1, max_number=45, numbers_to_select=3)
    first = FeatureEngine(reg).execute(draws, rules)
    second = FeatureEngine(reg).execute(draws, rules)
    assert first.values == second.values
    assert first.fingerprint == second.fingerprint


def test_engine_skips_feature_with_unresolvable_dependency() -> None:
    """A feature whose dependency is not runnable is skipped, never guessed."""
    reg = FeatureRegistry()
    reg.register(_def("needs_stats", dependencies=("stats",)), _flag_compute)
    result = FeatureEngine(reg).execute(
        draws=[_draw(1, (1, 2, 3))],
        rules=LotteryRules(min_number=1, max_number=45, numbers_to_select=3),
    )
    assert result.values == {}


def test_determinism_with_multiple_features_and_dependencies() -> None:
    """Meta-features fold deterministically across two runs (FES-05/GF1)."""
    reg = FeatureRegistry()
    reg.register(_def("draw_sum"), _sum_compute)
    reg.register(_def("draw_sum_flag", dependencies=("draw_sum",)), _flag_compute)
    draws = [_draw(4, (7, 8, 9)), _draw(8, (11, 12, 13))]
    rules = LotteryRules(min_number=1, max_number=45, numbers_to_select=3)
    a = FeatureEngine(reg).execute(draws, rules)
    b = FeatureEngine(reg).execute(draws, rules)
    assert a.values == b.values
    assert a.fingerprint == b.fingerprint
