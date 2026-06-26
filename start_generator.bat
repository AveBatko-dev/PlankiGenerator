@echo off
setlocal

chcp 65001 >nul
cd /d "%~dp0"

set "PYTHON_EXE=%~dp0python\python.exe"
set "PYTHONDONTWRITEBYTECODE=1"
set "REQUEST_FILE=%~dp0generation_request.json"
set "REQUEST_EXAMPLE=%~dp0generation_request.example.json"

if not exist "%PYTHON_EXE%" (
    echo Local Python runtime was not found:
    echo "%PYTHON_EXE%"
    echo.
    echo The archive must contain the "python" folder next to this bat file.
    echo.
    pause
    exit /b 1
)

echo Starting Planki Generator console...
echo.

if not exist "%REQUEST_FILE%" (
    if exist "%REQUEST_EXAMPLE%" (
        copy "%REQUEST_EXAMPLE%" "%REQUEST_FILE%" >nul
        echo Created file:
        echo "%REQUEST_FILE%"
        echo.
        echo Edit this file: set template_code and parameters.
        echo Then run this bat file again.
        echo.
        pause
        exit /b 0
    )

    echo Generation file was not found:
    echo "%REQUEST_FILE%"
    echo.
    pause
    exit /b 1
)

"%PYTHON_EXE%" -B "%~dp0generator_cli.py" --file "%REQUEST_FILE%" %*

echo.
echo Program finished.
pause
