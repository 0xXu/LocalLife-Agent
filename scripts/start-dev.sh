#!/bin/bash
# ============================================
# AI Route Planner — 一键启动开发环境 (Windows Git Bash / macOS)
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  AI Route Planner — 启动开发环境"
echo "============================================"

# 1. Start PostgreSQL
echo "[1/3] Starting PostgreSQL..."
cd "$PROJECT_DIR"
docker compose up -d postgres
echo "  PostgreSQL started on localhost:5433"

# 2. Start Backend
echo "[2/3] Starting Backend (Spring Boot on :8080)..."
cd "$PROJECT_DIR"
mvn spring-boot:run &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# Wait for backend to be ready
echo "  Waiting for backend health check..."
for i in $(seq 1 30); do
    if curl -s http://localhost:8080/api/route/health > /dev/null 2>&1; then
        echo "  Backend is ready!"
        break
    fi
    sleep 2
done

# 3. Start Frontend (Metro bundler)
echo "[3/3] Starting Frontend (React Native Metro)..."
cd "$PROJECT_DIR/LiquidRoute"
npx react-native start &
METRO_PID=$!
echo "  Metro PID: $METRO_PID"

echo ""
echo "============================================"
echo "  All services started!"
echo "  Backend:  http://localhost:8080"
echo "  Health:   http://localhost:8080/api/route/health"
echo "  Frontend: http://localhost:8081 (Metro)"
echo ""
echo "  PIDs: Backend=$BACKEND_PID Metro=$METRO_PID"
echo "  Stop with: ./scripts/stop-dev.sh"
echo "============================================"

# Write PIDs for stop script
mkdir -p "$PROJECT_DIR/.run"
echo "$BACKEND_PID" > "$PROJECT_DIR/.run/backend.pid"
echo "$METRO_PID" > "$PROJECT_DIR/.run/metro.pid"

wait
