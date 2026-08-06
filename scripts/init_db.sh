#!/usr/bin/env bash
# Create an empty SQLite database file at the repo-root `database/lip.db`.
#
# Delegates to the application's `init_db()` (core/db.py) so the file path and
# engine construction stay single-sourced. No schema is created — Alembic
# migrations own the schema (REQ-09); `Base.metadata.create_all` is never used.
set -euo pipefail

cd "$(dirname "$0")/.."

exec uv run --directory backend python -c \
  "from backend.app.core.db import init_db; init_db()"