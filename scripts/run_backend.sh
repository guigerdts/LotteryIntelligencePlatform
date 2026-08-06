#!/usr/bin/env bash
# Start the backend dev server with hot reload.
#
# Runs uvicorn against the FastAPI app factory from the repository root. The
# --app-dir flag points at backend/src (src-layout), mirroring how pytest and
# the installed package resolve the `backend.app` import path.
set -euo pipefail

cd "$(dirname "$0")/.."

exec uv run --directory backend \
  uvicorn backend.app.main:create_app \
  --app-dir backend/src \
  --reload