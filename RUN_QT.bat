@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Virtual environment missing - running setup first...
    call AUTO_SETUP_AND_RUN.bat
    exit /b
)
".venv\Scripts\python.exe" -c "import PySide6" 2>nul || ".venv\Scripts\python.exe" -m pip install PySide6
".venv\Scripts\python.exe" -m labelapp
if errorlevel 1 pause
