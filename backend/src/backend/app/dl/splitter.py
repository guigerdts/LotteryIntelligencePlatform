"""Window-aware walk-forward splitter (DLE-05, anti-leakage).

Splits windows at ``cut`` with the contract ``train.last_draw <= cut``,
``eval.first_draw > cut``.  Windows that straddle the cut (some draws
before, some after) are rejected with ``LeakageError``.  Shuffled order
(eval window before train) is also rejected (DLE-05).
"""

from __future__ import annotations

from collections.abc import Sequence

from backend.app.dl.window import Window


class LeakageError(Exception):
    """A split leaks future draws into evaluation (window straddles cut)."""


def split_windows(
    windows: Sequence[Window],
    cut: int,
) -> tuple[list[Window], list[Window]]:
    """Split ``windows`` into ``(train, eval)`` at ``cut``.

    A window belongs to **train** if its ``draw_number <= cut``.
    A window belongs to **eval** if its ``draw_number > cut``.

    Any window that straddles the cut (its draw range spans the cut) is
    rejected with ``LeakageError`` before any split occurs.

    Parameters
    ----------
    windows:
        Windows in chronological order.
    cut:
        Walk-forward split boundary (draw number).

    Returns
    -------
    tuple[list[Window], list[Window]]
        ``(train_windows, eval_windows)``.

    Raises
    ------
    LeakageError
        If any window straddles the cut or shuffle is detected.
    ValueError
        If the cut leaves an empty train or eval side.
    """
    # Detect straddle: a window straddles if its draw range spans the cut.
    # A window straddles when first_draw < cut AND last_draw > cut — meaning
    # some draws are strictly before cut and some strictly after cut.
    # Windows ending exactly at cut go to train; windows starting exactly at
    # cut+1 go to eval.  Neither is a straddle.
    for w in windows:
        first_draw = w.draw_number - w.W + 1
        if first_draw < cut and w.draw_number > cut:
            raise LeakageError(
                f"Window ending at draw {w.draw_number} (first={first_draw}) "
                f"straddles cut={cut}: rejected"
            )

    # Anti-shuffle: the windows list must be in chronological order.
    for i in range(1, len(windows)):
        if windows[i].draw_number <= windows[i - 1].draw_number:
            raise LeakageError(
                f"Shuffled split: window at index {i} "
                f"(draw {windows[i].draw_number}) is not after "
                f"window at index {i - 1} "
                f"(draw {windows[i - 1].draw_number})"
            )

    train = [w for w in windows if w.draw_number <= cut]
    eval_ = [w for w in windows if w.draw_number > cut]

    if not train or not eval_:
        draw_numbers = [w.draw_number for w in windows]
        raise ValueError(
            f"cut={cut} leaves an empty train or eval side (draw_numbers={draw_numbers})"
        )

    return train, eval_


def validate_windows(
    windows: Sequence[Window],
    cut: int,
    *,
    strict: bool = True,
) -> None:
    """Validate that no window leaks across ``cut`` (DLE-05).

    Under ``strict=True`` (default), any window whose draw range spans
    ``cut`` is rejected with ``LeakageError``.
    """
    for w in windows:
        first_draw = w.draw_number - w.W + 1
        if first_draw < cut and w.draw_number > cut:
            raise LeakageError(
                f"Window ending at draw {w.draw_number} (first={first_draw}) "
                f"straddles cut={cut}: leaked split rejected"
            )
    if strict:
        for w in windows:
            if w.draw_number <= cut:
                first_draw = w.draw_number - w.W + 1
                if first_draw > cut:
                    raise LeakageError(
                        f"Train window ending at {w.draw_number} "
                        f"has first_draw={first_draw} > cut={cut}: "
                        f"strict walk-forward violation"
                    )


__all__ = ["LeakageError", "split_windows", "validate_windows"]
