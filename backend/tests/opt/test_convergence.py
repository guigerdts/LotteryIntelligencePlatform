"""Tests for opt/convergence — convergence history tracker (OE-13)."""

from __future__ import annotations

from decimal import Decimal

from backend.app.opt.convergence import ConvergenceTracker


def test_tracker_empty() -> None:
    """New tracker has no history."""
    tracker = ConvergenceTracker()
    assert tracker.n_evaluations == 0
    assert tracker.best_fitness is None
    assert tracker.history == []


def test_tracker_record() -> None:
    """Recording evaluations builds history."""
    tracker = ConvergenceTracker()
    tracker.record(1, Decimal("0.80000000"))
    tracker.record(2, Decimal("0.85000000"))
    assert tracker.n_evaluations == 2
    assert tracker.best_fitness == Decimal("0.85000000")


def test_tracker_best_fitness() -> None:
    """best_fitness returns the maximum fitness seen."""
    tracker = ConvergenceTracker()
    tracker.record(1, Decimal("0.70000000"))
    tracker.record(2, Decimal("0.90000000"))
    tracker.record(3, Decimal("0.80000000"))
    assert tracker.best_fitness == Decimal("0.90000000")


def test_tracker_history_immutable() -> None:
    """history property returns a copy, not the internal list."""
    tracker = ConvergenceTracker()
    tracker.record(1, Decimal("0.80000000"))
    h1 = tracker.history
    h2 = tracker.history
    assert h1 is not h2
    assert h1 == h2


def test_tracker_to_json() -> None:
    """to_json() returns JSON-serializable list."""
    tracker = ConvergenceTracker()
    tracker.record(1, Decimal("0.80000000"))
    tracker.record(2, Decimal("0.85000000"))
    data = tracker.to_json()
    assert len(data) == 2
    assert data[0]["eval_num"] == 1
    assert data[0]["fitness"] == "0.80000000"
    assert isinstance(data[0]["timestamp"], float)


def test_tracker_from_json() -> None:
    """from_json() reconstructs tracker faithfully."""
    original = ConvergenceTracker()
    original.record(1, Decimal("0.80000000"))
    original.record(2, Decimal("0.85000000"))
    data = original.to_json()
    restored = ConvergenceTracker.from_json(data)
    assert restored.n_evaluations == 2
    assert restored.best_fitness == Decimal("0.85000000")
    assert restored.to_json() == data


def test_tracker_monotonic_eval_nums() -> None:
    """Eval numbers are monotonically increasing."""
    tracker = ConvergenceTracker()
    for i in range(1, 11):
        tracker.record(i, Decimal(str(0.8 + i * 0.01)))
    eval_nums = [e.eval_num for e in tracker.history]
    assert eval_nums == list(range(1, 11))
