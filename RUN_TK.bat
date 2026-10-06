@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    call AUTO_SETUP_AND_RUN.bat
    exit /b
)
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
