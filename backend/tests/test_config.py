"""Config tests: settings singleton honours deterministic LIP_ precedence."""

from __future__ import annotations

from backend.app.config.settings import Settings


def test_default_app_name_when_unset(monkeypatch) -> None:
    """Without LIP_APP_NAME the built-in default applies."""
    monkeypatch.delenv("LIP_APP_NAME", raising=False)
    settings = Settings()
    assert settings.app_name == "lip-backend"


def test_app_name_env_override(monkeypatch) -> None:
    """LIP_APP_NAME overrides the built-in default."""
    monkeypatch.setenv("LIP_APP_NAME", "lip-test-backend")
    settings = Settings()
    assert settings.app_name == "lip-test-backend"
