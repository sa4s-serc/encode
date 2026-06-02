#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${WATTWISE_PYTHON:-$ROOT_DIR/myvenv/bin/python}"
FRONTEND_DIST_INDEX="$ROOT_DIR/dashboard/frontend/dist/index.html"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Python executable not found: $PYTHON_BIN" >&2
  echo "Set WATTWISE_PYTHON or create the virtualenv first." >&2
  exit 1
fi

if [[ ! -f "$FRONTEND_DIST_INDEX" ]]; then
  echo "Frontend build not found: $FRONTEND_DIST_INDEX" >&2
  echo "Run: cd \"$ROOT_DIR/dashboard/frontend\" && npm install && npm run build" >&2
  exit 1
fi

exec "$PYTHON_BIN" -m dashboard.backend.main
