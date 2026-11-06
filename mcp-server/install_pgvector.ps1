# ============================================================================
#  install_pgvector.ps1
#  Memasang pgvector 0.8.7 ke PostgreSQL 18 (D:\PostgreSQL\18) di Windows.
#  WAJIB dijalankan sebagai ADMINISTRATOR (folder PostgreSQL butuh hak admin).
#
#  Cara pakai:
#    1. Klik kanan PowerShell -> "Run as administrator"
#    2. Jalankan:
#       powershell -ExecutionPolicy Bypass -File "D:\BINUS SEMESTER 7\Calpadia Sistem Integrasi\sourcecode\Research_Fintracks_MCP\mcp-server\install_pgvector.ps1"
# ============================================================================

$ErrorActionPreference = "Stop"

$PgRoot   = "D:\PostgreSQL\18"
$Service  = "postgresql-x64-18"
$Extract  = "$env:TEMP\pgvector_pg18\extracted"

Write-Host "=== pgvector installer untuk PostgreSQL 18 ===" -ForegroundColor Cyan

# --- 0. Pastikan admin ---
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "GAGAL: Jalankan skrip ini sebagai Administrator." -ForegroundColor Red
    exit 1
}

# --- 1. Pastikan file hasil ekstrak ada ---
if (-not (Test-Path "$Extract\lib\vector.dll")) {
    Write-Host "GAGAL: File pgvector hasil ekstrak tidak ditemukan di $Extract" -ForegroundColor Red
    Write-Host "Pastikan proses download/ekstrak sudah dilakukan." -ForegroundColor Red
    exit 1
}

# --- 2. Pastikan folder tujuan ada ---
foreach ($d in @("$PgRoot\lib", "$PgRoot\share\extension")) {
    if (-not (Test-Path $d)) { Write-Host "GAGAL: Folder tujuan tidak ada: $d" -ForegroundColor Red; exit 1 }
}

# --- 3. Salin file ---
Write-Host "Menyalin vector.dll ke $PgRoot\lib ..." -ForegroundColor Yellow
Copy-Item "$Extract\lib\vector.dll" "$PgRoot\lib\" -Force

Write-Host "Menyalin file extension (.control + .sql) ke $PgRoot\share\extension ..." -ForegroundColor Yellow
Copy-Item "$Extract\share\extension\*" "$PgRoot\share\extension\" -Force

if (Test-Path "$Extract\include\server\extension\vector") {
    $incDst = "$PgRoot\include\server\extension\vector"
    New-Item -ItemType Directory -Force -Path $incDst | Out-Null
    Copy-Item "$Extract\include\server\extension\vector\*" $incDst -Force
    Write-Host "Menyalin header include (opsional) selesai." -ForegroundColor Yellow
}

# --- 4. Restart service PostgreSQL agar library baru terbaca ---
Write-Host "Me-restart service $Service ..." -ForegroundColor Yellow
Restart-Service $Service -Force
Start-Sleep -Seconds 4
Write-Host "Service status: $((Get-Service $Service).Status)" -ForegroundColor Green

# --- 5. Jalankan CREATE EXTENSION via psql ---
$psql = "$PgRoot\bin\psql.exe"
$env:PGPASSWORD = "Admin123"
Write-Host "Menjalankan CREATE EXTENSION vector pada database fintracks ..." -ForegroundColor Yellow
& $psql -U postgres -h localhost -d fintracks -c "CREATE EXTENSION IF NOT EXISTS vector;"
& $psql -U postgres -h localhost -d fintracks -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"

Write-Host ""
Write-Host "=== SELESAI ===" -ForegroundColor Cyan
Write-Host "Jika baris di atas menampilkan 'vector | 0.8.7' (atau versi lain), pgvector sudah aktif." -ForegroundColor Green
