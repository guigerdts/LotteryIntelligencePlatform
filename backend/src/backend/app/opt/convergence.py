"""Convergence tracker for optimization runs (OE-13).

Records the evaluation-by-evaluation fitness trajectory during optimization.
The history is stored in ``opt_results.convergence_history`` as JSON.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ConvergenceEntry:
    """One evaluation in the convergence history.

    ``eval_num`` is the evaluation number (1-indexed); ``best_fitness`` is the
    best-so-far fitness as a quantized Decimal; ``timestamp`` is epoch seconds.
    """

    eval_num: int
    best_fitness: Decimal
    timestamp: float


class ConvergenceTracker:
    """Append-only convergence history tracker.

    Records fitness after each evaluation; the history is monotonically
    increasing in ``eval_num``.
    """

    def __init__(self) -> None:
        self._history: list[ConvergenceEntry] = []
        self._start_time: float = time.time()

    def record(self, eval_num: int, fitness: Decimal) -> None:
        """Record one evaluation's best fitness."""
        self._history.append(
            ConvergenceEntry(
                eval_num=eval_num,
                best_fitness=fitness,
                timestamp=time.time(),
            )
        )

    @property
    def history(self) -> list[ConvergenceEntry]:
        """Return the convergence history (read-only copy)."""
        return list(self._history)

    @property
    def best_fitness(self) -> Decimal | None:
        """Return the best fitness seen so far, or None if no evaluations."""
        if not self._history:
            return None
        return max(entry.best_fitness for entry in self._history)

    @property
    def n_evaluations(self) -> int:
        """Return the number of evaluations recorded."""
        return len(self._history)

    def to_json(self) -> list[dict[str, object]]:
        """Convert to a JSON-serializable list."""
        return [
            {
                "eval_num": entry.eval_num,
                "fitness": str(entry.best_fitness),
                "timestamp": entry.timestamp,
            }
            for entry in self._history
        ]

    @classmethod
    def from_json(cls, data: list[dict[str, object]]) -> ConvergenceTracker:
        """Reconstruct a tracker from JSON data."""
        tracker = cls()
        for entry in data:
            tracker._history.append(
                ConvergenceEntry(
                    eval_num=int(entry["eval_num"]),
                    best_fitness=Decimal(str(entry["fitness"])),
                    timestamp=float(entry["timestamp"]),
                )
            )
        return tracker


__all__ = ["ConvergenceEntry", "ConvergenceTracker"]
