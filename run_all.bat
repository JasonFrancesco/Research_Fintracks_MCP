@echo off
REM =====================================================================
REM  FinTracks + Gatling - Jalankan SEMUA service sekaligus.
REM  Cukup jalankan dari folder root project:  run_all.bat
REM
REM  Memakai Python venv (bukan python global) supaya pika & dependency
REM  lain terbaca. Ini mencegah error "modul pika belum aktif".
REM =====================================================================

cd /d "%~dp0"
set PY=backend\venv\Scripts\python.exe

if not exist "%PY%" (
    echo [ERROR] venv tidak ditemukan di %PY%
    echo Jalankan dari folder root project.
    pause
    exit /b 1
)

echo ==================================================
echo  Menjalankan semua service FinTracks + Gatling
echo ==================================================

set ROOT=%~dp0
set PYFULL=%ROOT%backend\venv\Scripts\python.exe

echo [1/5] MCP Server (port 8001)...
start "MCP Server" cmd /k "cd /d "%ROOT%mcp-server" ^& "%PYFULL%" server.py"

echo [2/5] Backend FastAPI (port 8000)...
start "Backend" cmd /k "cd /d "%ROOT%backend" ^& "%PYFULL%" run.py"

echo [3/5] Worker Gatling #1...
start "Gatling Worker 1" cmd /k "cd /d "%ROOT%" ^& "%PYFULL%" worker\worker.py"

echo [4/5] Worker Gatling #2...
start "Gatling Worker 2" cmd /k "cd /d "%ROOT%" ^& "%PYFULL%" worker\worker.py"

echo [5/5] Worker Gatling #3...
start "Gatling Worker 3" cmd /k "cd /d "%ROOT%" ^& "%PYFULL%" worker\worker.py"

echo.
echo Catatan: Frontend dijalankan terpisah (lihat run_frontend.bat).
echo RabbitMQ harus sudah hidup (cek http://localhost:15672).
echo Semua service berjalan di jendela terpisah. Tutup jendela untuk menghentikan.
echo ==================================================
