@echo off
echo Menjalankan MCP Server...
if exist ..\backend\venv\Scripts\python.exe (
    ..\backend\venv\Scripts\python.exe server.py
) else (
    python server.py
)

