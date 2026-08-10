"""Unit tests for dl.version — DL_GENERATOR_VERSION identity (DLE-08)."""

from __future__ import annotations


def test_dl_generator_version_is_string() -> None:
    """DL_GENERATOR_VERSION is a non-empty string identity (DLE-08 / D-A6)."""
    from backend.app.dl.version import DL_GENERATOR_VERSION

    assert isinstance(DL_GENERATOR_VERSION, str)
    assert DL_GENERATOR_VERSION  # non-empty


def test_dl_generator_version_semver() -> None:
    """DL_GENERATOR_VERSION follows semver-like format."""
    from backend.app.dl.version import DL_GENERATOR_VERSION

    parts = DL_GENERATOR_VERSION.split(".")
    assert len(parts) >= 2, "version must have at least major.minor"
    assert all(p.isdigit() for p in parts[:2]), "major.minor must be numeric"
