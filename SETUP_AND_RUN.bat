@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  set PY=py
) else (
  set PY=python
)

if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
)

call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install pillow python-barcode pywin32 reportlab openpyxl pymupdf PySide6
python -m labelapp
pause
