# Satu perintah untuk Windows (PowerShell): .\scripts\start.ps1
# Menjalankan dashboard + worker. 9Router/Hermes/Ootto dijalankan terpisah.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Host ".env dibuat dari contoh. Isi STUDIO_PASSWORD (min 16 karakter)." }
python -m pip install -r requirements.txt
python -m src.cli doctor
python -m src.dashboard --host 0.0.0.0 --port 8080
