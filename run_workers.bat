@echo off
REM Menjalankan 3 worker Gatling paralel (opsi A: maksimal 3 job bersamaan).
REM Tiap worker = 1 proses yang mengambil 1 job dari antrian RabbitMQ.
REM Dengan 3 worker, maksimal 3 job dieksekusi serentak.
REM
REM Jalankan dari folder root project: run_workers.bat

set PYTHON=backend\venv\Scripts\python.exe

if not exist "%PYTHON%" (
    echo [ERROR] Python venv tidak ditemukan di %PYTHON%
    echo Pastikan dijalankan dari folder root project.
    pause
    exit /b 1
)

echo Menjalankan 3 worker Gatling paralel...
start "Gatling Worker 1" cmd /k "%PYTHON% worker\worker.py"
start "Gatling Worker 2" cmd /k "%PYTHON% worker\worker.py"
start "Gatling Worker 3" cmd /k "%PYTHON% worker\worker.py"
echo 3 worker telah diluncurkan di jendela terpisah.
echo Tutup jendela-jendela worker untuk menghentikannya.
