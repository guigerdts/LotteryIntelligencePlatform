"""Centralized configuration: pydantic-settings Settings singleton (single access point)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root, resolved from this file's location:
# <root>/backend/src/backend/app/config/settings.py -> parents[5] == repo root.
# Anchoring the default database location to the repo root keeps the bootstrap
# deterministic regardless of the process working directory.
_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_DATABASE_DIR = _REPO_ROOT / "database"
_DEFAULT_DATABASE_FILE = _DEFAULT_DATABASE_DIR / "lip.db"


class Settings(BaseSettings):
    """Application configuration, the single source of truth for the backend.

    Precedence is deterministic: built-in section defaults -> environment / `.env`
    overrides (prefix ``LIP_``). Secrets are provided through the environment
    only and are never hard-coded here. Infra configuration only — no business
    logic.
    """

    model_config = SettingsConfigDict(env_prefix="LIP_", env_file=".env", env_file_encoding="utf-8")

    # --- app ---
    app_name: str = "lip-backend"
    app_version: str = "0.1.0"
    debug: bool = False

    # --- api ---
    api_v1_prefix: str = "/api/v1"
    allowed_origins: list[str] = ["http://localhost:5173"]

    # --- database ---
    # Dialect is driven entirely by the URL: SQLite now, PostgreSQL later as a
    # config-only swap (no SQLite-specific behavior outside repositories/ + core/db.py).
    database_url: str = f"sqlite:///{_DEFAULT_DATABASE_FILE.as_posix()}"
    database_path: Path = _DEFAULT_DATABASE_FILE

    # --- logging ---
    logging_level: str = "INFO"

    # --- paths ---
    database_dir: Path = _DEFAULT_DATABASE_DIR


@lru_cache
def get_settings() -> Settings:
    """Return the cached settings singleton (the only access path for the app)."""
    return Settings()
