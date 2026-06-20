#!/bin/bash
# ============================================
# AI Route Planner — 停止所有开发服务
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Stopping AI Route Planner services..."

# Stop processes by PID files
if [ -f "$PROJECT_DIR/.run/backend.pid" ]; then
    kill "$(cat "$PROJECT_DIR/.run/backend.pid")" 2>/dev/null && echo "  Backend stopped"
    rm "$PROJECT_DIR/.run/backend.pid"
fi

if [ -f "$PROJECT_DIR/.run/metro.pid" ]; then
    kill "$(cat "$PROJECT_DIR/.run/metro.pid")" 2>/dev/null && echo "  Metro stopped"
    rm "$PROJECT_DIR/.run/metro.pid"
fi

# Stop docker containers
cd "$PROJECT_DIR"
docker compose down 2>/dev/null && echo "  Docker containers stopped"

rm -rf "$PROJECT_DIR/.run"
echo "All services stopped."
