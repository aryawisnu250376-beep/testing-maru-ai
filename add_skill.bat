@echo off
setlocal
cd /d "%~dp0"

if "%~1"=="" (
    echo Pemakaian:
    echo   add_skill.bat ^<URL-GitHub-atau-owner/repo/path^> [academic^|social-media^|shared] [nama-opsional]
    echo.
    echo Contoh:
    echo   add_skill.bat https://github.com/anthropics/skills/tree/main/skills/pdf academic
    echo   add_skill.bat https://github.com/anthropics/skills/tree/main/skills/docx shared
    exit /b 1
)

set SOURCE_URL=%~1
set DIVISION=%~2
if "%DIVISION%"=="" set DIVISION=shared
set CUSTOM_NAME=%~3

if "%CUSTOM_NAME%"=="" (
    python -m maru_github_sync add-skill "%SOURCE_URL%" --division "%DIVISION%"
) else (
    python -m maru_github_sync add-skill "%SOURCE_URL%" --division "%DIVISION%" --name "%CUSTOM_NAME%"
)
endlocal
