#!/usr/bin/env bash
# start.sh — Start the CrewAI API server
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"

# Activate venv if present
if [ -f "$DIR/.venv/bin/activate" ]; then
    source "$DIR/.venv/bin/activate"
fi

cd "$DIR"
exec uvicorn api:app --host 0.0.0.0 --port 8000 --log-level info
