@echo off
setlocal
cd /d "%~dp0"

set ACTION=%1
if "%ACTION%"=="" set ACTION=sync

echo =======================================================
echo   MARU AI - Sinkronisasi Skill ^& Memori ke GitHub
echo   Mode: %ACTION%
echo =======================================================

python -m maru_github_sync %ACTION%
if errorlevel 1 (
    echo.
    echo [GAGAL] Periksa variabel MARU_GITHUB_TOKEN di file .env Anda.
    exit /b 1
)

echo.
echo [SELESAI] Sinkronisasi %ACTION% berhasil dijalankan.
endlocal
