"""S4 parity tests: serial == parallel ML training byte-identical (GF-1, MLE-04/05).

Verifies that ``ProcessPoolExecutor`` number-level parallelization produces
identical ``TrainResult`` bytes (checksum, fingerprint, quantized per-number
metrics, models) for the same inputs (T-S4-03).  The module-level
``_fit_number`` worker resolves the estimator from the canonical registry by
name with ``random_state=0`` and no shuffle, so every number is a pure
deterministic function of its inputs.
"""

from __future__ import annotations

import ast
import pickle
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Final

from backend.app.ml.engine import MlEngine, _fit_number
from backend.app.ml.features import ML_FEATURE_ORDER

_NUMBERS: Final[tuple[int, ...]] = (4, 5, 6)
_CUT = 8

_ENGINE_SRC = (
    Path(__file__).resolve().parents[2] / "src" / "backend" / "app" / "ml" / "engine.py"
)

_FORBIDDEN_IMPORT_PREFIXES = (
    "sqlalchemy",
    "backend.app.core.db",
    "backend.app.services.bt_service",
    "backend.app.services.ml_service",
    "backend.app.services.probability_service",
)


def _top_level_imports(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    """Return only module-level import nodes (not inside functions/classes)."""
    return [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]


def _records(n_draws: int = 12) -> list[SimpleNamespace]:
    return [
        SimpleNamespace(draw_number=n, numbers=(_NUMBERS[n % 3],)) for n in range(1, n_draws + 1)
    ]


def _feature_rows(records: list[SimpleNamespace]) -> list[object]:
    from backend.app.ml.feature_reader import FeatureValueRow

    return [
        FeatureValueRow(fid, draw.draw_number, float(draw.draw_number + j))
        for draw in records
        for j, fid in enumerate(ML_FEATURE_ORDER)
    ]


def _train(*, parallel: bool):
    return MlEngine().train(
        family="random_forest",
        lottery_id=7,
        records=_records(),
        snapshot_id=1,
        cut=_CUT,
        feature_rows=_feature_rows(_records()),
        parallel=parallel,
    )


class TestMlParallelParity:
    """GF-1 hard gate: serial and parallel TrainResult must be byte-identical."""

    def test_serial_parallel_byte_identical(self) -> None:
        serial = _train(parallel=False)
        parallel = _train(parallel=True)

        assert serial.fingerprint == parallel.fingerprint
        assert serial.checksum == parallel.checksum
        assert serial.metrics == parallel.metrics
        assert serial.quantized == parallel.quantized
        assert set(serial.models) == set(parallel.models)
        for number in serial.models:
            # Models are fitted from the same data; their fitted params are equal.
            assert serial.models[number].__class__ is parallel.models[number].__class__
            assert (
                serial.models[number].get_params() == parallel.models[number].get_params()
            )
        assert serial.train_draws == parallel.train_draws
        assert serial.eval_draws == parallel.eval_draws

    def test_quantized_decimals_match(self) -> None:
        serial = _train(parallel=False)
        parallel = _train(parallel=True)
        for number in _NUMBERS:
            for name in ("accuracy", "precision", "recall", "f1", "roc_auc"):
                a = serial.quantized[number][name]
                b = parallel.quantized[number][name]
                assert isinstance(a, Decimal) and isinstance(b, Decimal)
                assert a == b
                assert a.as_tuple().exponent == -8

    def test_fit_number_pickle_roundtrip(self) -> None:
        """Module-level worker is picklable (pool requirement)."""
        loaded = pickle.loads(pickle.dumps(_fit_number))
        assert loaded is _fit_number

    def test_no_db_in_worker_structural(self) -> None:
        """The engine module must not import SQLAlchemy/DB at module level (PFM-04)."""
        tree = ast.parse(_ENGINE_SRC.read_text(encoding="utf-8"))
        for node in _top_level_imports(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix in _FORBIDDEN_IMPORT_PREFIXES:
                        assert not alias.name.startswith(prefix), (
                            f"Module-level import of {prefix}: {alias.name}"
                        )
            if isinstance(node, ast.ImportFrom) and node.module:
                for prefix in _FORBIDDEN_IMPORT_PREFIXES:
                    assert not node.module.startswith(prefix), (
                        f"Module-level import of {prefix}: {node.module}"
                    )