@echo off
REM Jalankan frontend (Vite dev server). Dari folder root: run_frontend.bat
cd /d "%~dp0frontend"
npm run dev
