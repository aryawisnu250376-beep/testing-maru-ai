param(
    [ValidateSet("status", "export-local", "import-local", "push", "pull", "sync")]
    [string]$Action = "sync"
)

Set-Location -Path $PSScriptRoot
Write-Host "=== MARU AI - Sinkronisasi Skill & Memori GitHub ($Action) ===" -ForegroundColor Cyan
python -m maru_github_sync $Action
if ($LASTEXITCODE -ne 0) {
    Write-Error "Sinkronisasi gagal. Pastikan MARU_GITHUB_TOKEN sudah diatur di file .env."
    exit $LASTEXITCODE
}
Write-Host "Sinkronisasi ($Action) selesai!" -ForegroundColor Green
