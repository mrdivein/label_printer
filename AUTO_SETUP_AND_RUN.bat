@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title ECG Label Tool - Auto Setup

echo ==========================================
echo ECG LABEL TOOL - AUTO SETUP
echo ==========================================
echo.

set "PY="

REM --------------------------------------------------
REM 1. Check py launcher first
REM --------------------------------------------------
where py >nul 2>&1
if not errorlevel 1 (
    py -3.12 --version >nul 2>&1
    if not errorlevel 1 (
        set "PY=py -3.12"
        goto :PYTHON_OK
    )

    py --version >nul 2>&1
    if not errorlevel 1 (
        set "PY=py"
        goto :PYTHON_OK
    )
)

REM --------------------------------------------------
REM 2. Check real python.exe, but reject Microsoft Store alias
REM --------------------------------------------------
python --version >nul 2>&1
if not errorlevel 1 (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        echo %%P | findstr /I "WindowsApps" >nul
        if errorlevel 1 (
            set "PY=python"
            goto :PYTHON_OK
        )
    )
)

REM --------------------------------------------------
REM 3. No real Python: install with winget
REM --------------------------------------------------
echo Python that chua duoc cai.
echo Dang cai Python 3.12 x64 bang winget...
echo.

where winget >nul 2>&1
if errorlevel 1 (
    goto :NO_WINGET
)

winget install --id Python.Python.3.12 -e --source winget --scope user --accept-package-agreements --accept-source-agreements

if errorlevel 1 (
    echo.
    echo Winget khong cai duoc Python.
    goto :MANUAL
)

REM --------------------------------------------------
REM 4. Locate newly installed Python directly
REM --------------------------------------------------
set "PYEXE=%LocalAppData%\Programs\Python\Python312\python.exe"

if exist "%PYEXE%" (
    set "PY=%PYEXE%"
    goto :PYTHON_OK
)

REM Try launcher after install
py -3.12 --version >nul 2>&1
if not errorlevel 1 (
    set "PY=py -3.12"
    goto :PYTHON_OK
)

echo.
echo Python da cai nhung Windows chua refresh PATH.
echo Dong cua so nay, sau do double-click lai AUTO_SETUP_AND_RUN.bat.
pause
exit /b 1

:PYTHON_OK
echo Python hop le:
%PY% --version
if errorlevel 1 (
    echo Python path khong hop le.
    goto :MANUAL
)
echo.

REM --------------------------------------------------
REM 5. Create isolated environment
REM --------------------------------------------------
if not exist ".venv\Scripts\python.exe" (
    echo Dang tao moi truong cho ECG Label Tool...
    %PY% -m venv ".venv"
    if errorlevel 1 (
        echo.
        echo Loi tao virtual environment.
        pause
        exit /b 1
    )
)

REM --------------------------------------------------
REM 6. Install dependencies using venv Python directly
REM --------------------------------------------------
echo Dang cai/cap nhat thu vien...
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :PIP_ERROR

".venv\Scripts\python.exe" -m pip install pillow python-barcode pywin32 reportlab openpyxl pymupdf
if errorlevel 1 goto :PIP_ERROR

echo.
echo ==========================================
echo SETUP HOAN TAT - DANG MO ECG LABEL TOOL
echo ==========================================
echo.

".venv\Scripts\python.exe" app.py
exit /b 0

:NO_WINGET
echo Khong tim thay winget.
echo.
goto :MANUAL

:PIP_ERROR
echo.
echo Loi khi cai thu vien.
echo Kiem tra Internet va chay lai file nay.
pause
exit /b 1

:MANUAL
echo.
echo Cach nhanh nhat:
echo 1. Mo https://www.python.org/downloads/windows/
echo 2. Cai Python 3.12 x64
echo 3. Tick "Add python.exe to PATH"
echo 4. Chay lai AUTO_SETUP_AND_RUN.bat
echo.
pause
exit /b 1
