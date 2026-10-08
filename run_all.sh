#!/usr/bin/env bash

# ==============================================================================
# FinTracks App Launcher (macOS & Linux)
# Menjalankan MCP Server, Backend FastAPI, dan Frontend React secara bersamaan.
# ==============================================================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR" || exit 1

echo "=================================================="
echo "        FinTracks - Web App & FastMCP Launcher   "
echo "=================================================="

# Cari virtual environment Python
PYTHON_BIN=""
if [ -f "$PROJECT_DIR/venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/venv/bin/python"
elif [ -f "$PROJECT_DIR/backend/venv/bin/python" ]; then
    PYTHON_BIN="$PROJECT_DIR/backend/venv/bin/python"
elif command -v python3.11 &>/dev/null; then
    PYTHON_BIN="python3.11"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
else
    PYTHON_BIN="python"
fi

echo " Menggunakan Python: $($PYTHON_BIN --version 2>&1) ($PYTHON_BIN)"
echo ""

# Bersihkan background process saat script dihentikan (Ctrl + C)
cleanup() {
    echo ""
    echo "=================================================="
    echo " Menghentikan seluruh layanan FinTracks..."
    echo "=================================================="
    if [ -n "$PID_MCP" ] && kill -0 "$PID_MCP" 2>/dev/null; then
        kill "$PID_MCP" 2>/dev/null
    fi
    if [ -n "$PID_BACKEND" ] && kill -0 "$PID_BACKEND" 2>/dev/null; then
        kill "$PID_BACKEND" 2>/dev/null
    fi
    if [ -n "$PID_FRONTEND" ] && kill -0 "$PID_FRONTEND" 2>/dev/null; then
        kill "$PID_FRONTEND" 2>/dev/null
    fi
    wait 2>/dev/null
    echo " Semua layanan telah dimatikan dengan aman."
    exit 0
}

trap cleanup SIGINT SIGTERM EXIT

# 1. Jalankan FastMCP Server (Port 8001)
echo "1. Menjalankan MCP Server (Port 8001)..."
(
    cd "$PROJECT_DIR/mcp-server" || exit 1
    "$PYTHON_BIN" server.py
) &
PID_MCP=$!

# Tunggu sejenak agar MCP Server siap
sleep 1.5

# 2. Jalankan Backend FastAPI (Port 8000)
echo "2. Menjalankan Backend FastAPI (Port 8000)..."
(
    cd "$PROJECT_DIR/backend" || exit 1
    "$PYTHON_BIN" run.py
) &
PID_BACKEND=$!

# Tunggu sejenak agar Backend siap
sleep 1.5

# 3. Jalankan Frontend React (Port 5173)
echo "3. Menjalankan Frontend React (Port 5173)..."
(
    cd "$PROJECT_DIR/frontend" || exit 1
    npm run dev
) &
PID_FRONTEND=$!

echo ""
echo "=================================================="
echo " Semua layanan sedang berjalan:"
echo " • Frontend React : http://localhost:5173"
echo " • Backend FastAPI: http://localhost:8000"
echo " • FastMCP Server : http://localhost:8001/mcp"
echo "=================================================="
echo " Tekan [Ctrl + C] untuk menghentikan semua layanan."
echo "=================================================="
echo ""

# Jaga script tetap berjalan
wait
