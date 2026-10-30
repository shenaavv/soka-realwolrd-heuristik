#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${DASHBOARD_PORT:-8080}"
echo "Starting SOKA LLFD Dashboard..."
echo "Open: http://127.0.0.1:${PORT}"
echo "Press Ctrl+C to stop the dashboard."
exec python3 "$ROOT_DIR/server.py"
