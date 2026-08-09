"""Temporal walk-forward splitter (MLE-03, anti-leakage, design T-12).

Splits records at ``cut`` with the design contract ``train <= cut < eval``,
never shuffling (D2). ``validate_split`` rejects a shuffled/leaked candidate whose
eval draws sit at/before ``cut`` with ``LeakageError`` (MLE-03) — a leaked split
fails fast, nothing is written. A cut that empties either side raises ``ValueError``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence


class LeakageError(Exception):
    """A split leaks future draws into evaluation (some eval draw sits <= ``cut``)."""


def _draw_number_of[T](record: T) -> int:
    """Read ``record``'s draw number from a mapping key or an attribute."""
    if isinstance(record, Mapping):
        return int(record["draw_number"])
    return int(record.draw_number)  # type: ignore[attr-defined]  # duck-typed row


def walk_forward_split[T](records: Sequence[T], cut: int) -> tuple[list[T], list[T]]:
    """Split ``records`` into ``(train, eval)``: train ``<= cut``, eval ``> cut``.

    Either side empty raises ``ValueError``: an unusable cut MUST fail fast before
    any training work begins (MLE-03).
    """
    train = [row for row in records if _draw_number_of(row) <= cut]
    eval_rows = [row for row in records if _draw_number_of(row) > cut]
    if not train or not eval_rows:
        draws = sorted({_draw_number_of(row) for row in records})
        raise ValueError(f"cut={cut} leaves an empty train or eval side (draws {draws})")
    return train, eval_rows


def validate_split(
    train_draws: Sequence[int],
    eval_draws: Sequence[int],
    cut: int,
    *,
    strict: bool = True,
) -> None:
    """Reject a leaky candidate split: any eval draw ``<= cut`` raises ``LeakageError``.

    Under ``strict=True`` a training draw ``> cut`` is rejected as well, pinning
    the full ``train <= cut < eval`` contract (MLE-03 anti-shuffle).
    """
    leaked = [draw for draw in eval_draws if draw <= cut]
    if leaked:
        raise LeakageError(f"eval draws {leaked} <= cut={cut}: leaked split rejected")
    if strict and any(draw > cut for draw in train_draws):
        raise LeakageError(f"train draws must be <= cut={cut} (strict walk-forward)")


__all__ = ["LeakageError", "walk_forward_split", "validate_split"]
