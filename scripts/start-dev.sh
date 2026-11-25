#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [ ! -x "$ROOT_DIR/backend/.venv/bin/python" ]; then
  echo "Backend virtualenv missing. Follow README.md setup steps first."
  exit 1
fi

if [ ! -f "$ROOT_DIR/backend/.env" ] && [ -f "$ROOT_DIR/backend/.env.example" ]; then
  cp "$ROOT_DIR/backend/.env.example" "$ROOT_DIR/backend/.env"
fi
if [ ! -f "$ROOT_DIR/frontend/.env" ] && [ -f "$ROOT_DIR/frontend/.env.example" ]; then
  cp "$ROOT_DIR/frontend/.env.example" "$ROOT_DIR/frontend/.env"
fi

(
  cd "$ROOT_DIR/backend"
  .venv/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
) &
BACKEND_PID=$!

(
  cd "$ROOT_DIR/frontend"
  npm run dev
) &
FRONTEND_PID=$!

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null || true" EXIT
wait
