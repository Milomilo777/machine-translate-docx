@echo off
setlocal

cd /d "%~dp0"

rem Preferred interpreter — all dependencies are installed here
set "PYTHON_EXE=E:\Python311\python.exe"

if not exist "%PYTHON_EXE%" (
    echo Preferred Python not found at %PYTHON_EXE%, falling back to PATH...
    set "PYTHON_EXE="
    for /f "delims=" %%I in ('where python 2^>nul') do (
        if not defined PYTHON_EXE set "PYTHON_EXE=%%~fI"
    )
)

if not defined PYTHON_EXE (
    echo Python was not found.
    pause
    exit /b 1
)

echo Using Python: %PYTHON_EXE%
"%PYTHON_EXE%" "%~dp0local_launcher.py"

endlocal
