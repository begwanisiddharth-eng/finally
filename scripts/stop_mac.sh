#!/usr/bin/env bash
# FinAlly stop script (macOS / Linux)
# Stops the FastAPI process listening on port 8000.
# Leaves db/finally.db untouched.

set -uo pipefail

PIDS="$(lsof -ti tcp:8000 2>/dev/null || true)"
if [ -z "$PIDS" ]; then
    echo "[FinAlly] No process listening on port 8000."
    exit 0
fi

for pid in $PIDS; do
    echo "[FinAlly] Stopping process $pid ..."
    kill "$pid" 2>/dev/null || true
done
echo "[FinAlly] Stopped."
