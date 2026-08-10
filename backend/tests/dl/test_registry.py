"""Unit tests for dl.registry — core-3 + future-dl (DLE-07/11)."""

from __future__ import annotations

from backend.app.dl.registry import (
    CORE_3_MODELS,
    FUTURE_DL_FAMILIES,
    MODEL_SET_CORE_3,
    build_dl_registry,
)


def test_model_set_core3_value() -> None:
    """MODEL_SET_CORE_3 is 'core-3' (DLE-07)."""
    assert MODEL_SET_CORE_3 == "core-3"


def test_core3_models_exactly_mlp_lstm() -> None:
    """CORE_3_MODELS contains exactly mlp and lstm (DLE-07)."""
    assert set(CORE_3_MODELS) == {"mlp", "lstm"}
    assert len(CORE_3_MODELS) == 2


def test_core3_models_params_are_dicts() -> None:
    """Every entry in CORE_3_MODELS maps slug -> params dict."""
    for slug, params in CORE_3_MODELS.items():
        assert isinstance(params, dict), f"{slug} params must be a dict"
        assert "epochs" in params, f"{slug} must have epochs"
        assert "batch_size" in params, f"{slug} must have batch_size"
        assert "lr" in params, f"{slug} must have lr"


def test_build_registry_returns_fresh_dicts() -> None:
    """build_dl_registry returns fresh param dicts (mutation-safe)."""
    r1 = build_dl_registry()
    r2 = build_dl_registry()
    assert r1 is not r2  # different mapping objects
    assert dict(r1["mlp"]) == dict(r2["mlp"])  # same content
    # Mutating r1 does not affect r2
    r1["mlp"]["epochs"] = 999
    assert r2["mlp"]["epochs"] == 50


def test_future_dl_families_declared() -> None:
    """FUTURE_DL_FAMILIES declares transformer and tensorflow (DLE-07)."""
    assert "transformer" in FUTURE_DL_FAMILIES
    assert "tensorflow" in FUTURE_DL_FAMILIES


def test_future_dl_not_in_core3() -> None:
    """Future-dl families are NOT in CORE_3_MODELS (DLE-07)."""
    for name in FUTURE_DL_FAMILIES:
        assert name not in CORE_3_MODELS


def test_no_future_dl_imports() -> None:
    """registry.py never imports transformer/tensorflow (DLE-07)."""
    from importlib import import_module

    mod = import_module("backend.app.dl.registry")
    for attr in vars(mod).values():
        referenced = getattr(attr, "__module__", None)
        if isinstance(referenced, str):
            assert not any(f in referenced for f in FUTURE_DL_FAMILIES), (
                f"dl/registry.py references future-dl module {referenced!r}"
            )
