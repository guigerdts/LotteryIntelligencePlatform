"""Cold-start guard: heavy deps must not load at import (DLE-17, PFM-06).

``backend.app.main`` must import without pulling ``torch`` or ``sklearn`` into
``sys.modules``; both stay functional at first use (DL/ML engines).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[2]


def test_main_import_does_not_load_torch_or_sklearn() -> None:
    """Fresh ``import backend.app.main`` must not load torch/sklearn (T-S6-03)."""
    code = (
        "import sys; import backend.app.main; "
        "print('torch' in sys.modules, 'sklearn' in sys.modules)"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    torch_loaded, sklearn_loaded = proc.stdout.strip().split()
    assert torch_loaded == "False", "torch loaded at cold start (DLE-17)"
    assert sklearn_loaded == "False", "sklearn loaded at cold start (DLE-17)"


def test_torch_importable_at_first_use() -> None:
    """torch still imports and configures determinism on demand."""
    from backend.app.dl.determinism import configure_deterministic_torch

    configure_deterministic_torch(seed=0)


def test_sklearn_importable_at_first_use() -> None:
    """sklearn still imports and builds the registry on demand."""
    from backend.app.ml.registry import build_ml_registry

    registry = build_ml_registry()
    assert set(registry) == {"random_forest", "extra_trees", "gradient_boosting", "svm", "knn"}
