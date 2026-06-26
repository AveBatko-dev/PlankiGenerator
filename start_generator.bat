@echo off
setlocal

chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
set "PYTHONDONTWRITEBYTECODE=1"

if not exist "%PYTHON_EXE%" (
    echo Virtual environment was not found:
    echo "%PYTHON_EXE%"
    echo.
    echo Create it and install dependencies:
    echo python -m venv venv
    echo venv\Scripts\python.exe -m pip install -r requirements.txt
    echo.
    pause
    exit /b 1
)

echo Starting Planki Generator console...
echo.

"%PYTHON_EXE%" "%~dp0generator_cli.py" %*

echo.
echo Program finished.
pause
