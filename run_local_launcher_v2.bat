@echo off
setlocal

cd /d "%~dp0"

rem ──────────────────────────────────────────────────────────────────────────
rem  Local launcher — opens the new v2 (Claude-inspired) UI by default.
rem  The legacy UI remains available at  http://127.0.0.1:3000/
rem  v2 lives at                          http://127.0.0.1:3000/v2/
rem ──────────────────────────────────────────────────────────────────────────

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
echo Opening v2 UI shortly...

rem Open the v2 URL after a short grace period so the server is ready.
rem timeout/start return immediately; the launcher itself blocks below.
start "" /b cmd /c "timeout /t 2 /nobreak >nul && start """" ""http://127.0.0.1:3000/v2/"""

rem Keep launcher in the foreground so logs show up here. --no-browser stops
rem the launcher from opening the legacy URL on its own.
"%PYTHON_EXE%" "%~dp0local_launcher.py" --no-browser

endlocal
