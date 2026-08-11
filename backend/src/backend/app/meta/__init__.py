"""Meta Learning module — deterministic model ranking and selection.

Evaluates, ranks, and selects the best-performing models across engines
(ML/DL/OPT/BT) per lottery context. Consumes persisted engine outputs,
produces deterministic ranked selections for F13 consumption.
"""

from __future__ import annotations
