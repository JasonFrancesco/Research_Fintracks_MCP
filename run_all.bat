@echo off
title FinTracks App Launcher
echo ==================================================
echo         FinTracks - Web App & FastMCP Launcher
echo ==================================================
echo.
echo 1. Menjalankan MCP Server (Port 8001)...
start "FinTracks MCP Server" cmd /k "cd mcp-server && python server.py"

echo 2. Menjalankan Backend FastAPI (Port 8000)...
start "FinTracks Backend FastAPI" cmd /k "cd backend && python run.py"

echo 3. Menjalankan Frontend React (Port 5173)...
start "FinTracks Frontend React" cmd /k "cd frontend && npm run dev"

echo.
echo ==================================================
echo Semua layanan telah diluncurkan di jendela terpisah!
echo - Frontend React: http://localhost:5173
echo - Backend FastAPI: http://localhost:8000
echo - FastMCP Server: http://localhost:8001
echo ==================================================
pause

