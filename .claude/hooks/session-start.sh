#!/bin/bash
set -euo pipefail

# Web-only: skip on local machines, which already have deps + Postgres.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

# Ensure uv is available (installer is idempotent; uv may already be in the image).
if ! command -v uv >/dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Install runtime + dev deps (ruff, pytest, pytest-django, factory_boy).
uv sync

# Persist session env: no Postgres in web sessions, so run checks against
# in-memory SQLite (matches the documented host-test path in CLAUDE.md).
# Also keep uv on PATH if we just installed it.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  echo 'export DATABASE_URL="sqlite://:memory:"' >> "$CLAUDE_ENV_FILE"
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$CLAUDE_ENV_FILE"
fi
