@echo off
cd /d "%~dp0"
if not exist "venv\Scripts\python.exe" (
    echo Virtual environment not found. First install dependencies using README.md.
    pause
    exit /b 1
)
call "venv\Scripts\activate.bat"
python web_run.py
pause
