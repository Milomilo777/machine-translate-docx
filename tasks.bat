@ECHO OFF
REM tasks.bat — Windows shim for the Makefile.
REM Native Windows command prompt doesn't have GNU make by default;
REM this batch file mirrors the same target names so users can run
REM e.g. ``tasks.bat smoke`` instead of ``make smoke``.
REM
REM Created in C4 of the 2026-05-10 architecture cleanup.

SETLOCAL
IF "%PYTHON%"=="" SET PYTHON=python
SET FIXTURE=tests\fixtures\sample_hyperlink.docx
SET TMPDIR=_real_test

IF "%1"=="" GOTO HELP
IF /I "%1"=="help" GOTO HELP
IF /I "%1"=="test" GOTO TEST
IF /I "%1"=="test-integration" GOTO TEST_INTEGRATION
IF /I "%1"=="test-all" GOTO TEST_ALL
IF /I "%1"=="smoke" GOTO SMOKE
IF /I "%1"=="live-deepl" GOTO LIVE_DEEPL
IF /I "%1"=="live-google" GOTO LIVE_GOOGLE
IF /I "%1"=="live-all" GOTO LIVE_ALL
IF /I "%1"=="clean" GOTO CLEAN

ECHO Unknown target: %1
GOTO HELP

:HELP
ECHO machine-translate-docx — local task runner (Windows)
ECHO.
ECHO   tasks.bat test              pytest unit tests
ECHO   tasks.bat test-integration  opt-in integration tests
ECHO   tasks.bat test-all          unit + integration tests
ECHO   tasks.bat smoke             DeepL en-^>fr quick run on the fixture
ECHO   tasks.bat live-deepl        DeepL en-^>fr + en-^>fa real-file runs
ECHO   tasks.bat live-google       Google en-^>fr + en-^>fa real-file runs
ECHO   tasks.bat live-all          all real-file runs
ECHO   tasks.bat clean             remove %TMPDIR%\
ECHO.
ECHO Override the interpreter:
ECHO   SET PYTHON=E:\Python311\python.exe
ECHO   tasks.bat test
GOTO END

:TEST
%PYTHON% -m pytest tests/ --ignore=tests/test_v2_e2e.py --ignore=tests/integration
GOTO END

:TEST_INTEGRATION
%PYTHON% -m pytest tests/integration --ignore=tests/test_v2_e2e.py
GOTO END

:TEST_ALL
%PYTHON% -m pytest tests/ --ignore=tests/test_v2_e2e.py
GOTO END

:SMOKE
IF NOT EXIST %TMPDIR% MKDIR %TMPDIR%
COPY /Y %FIXTURE% %TMPDIR%\smoke.docx > NUL
PUSHD %TMPDIR%
set "PYTHONPATH=..\src" && %PYTHON% -m machine_translate_docx.cli --docxfile smoke.docx --srclang en --destlang fr --engine deepl --enginemethod phrasesblock --silent --exitonsuccess
POPD
ECHO smoke: %TMPDIR%\smoke_FRE_Deepl.docx
GOTO END

:LIVE_DEEPL
IF NOT EXIST %TMPDIR% MKDIR %TMPDIR%
COPY /Y %FIXTURE% %TMPDIR%\deepl_fr.docx > NUL
PUSHD %TMPDIR%
set "PYTHONPATH=..\src" && %PYTHON% -m machine_translate_docx.cli --docxfile deepl_fr.docx --srclang en --destlang fr --engine deepl --enginemethod phrasesblock --silent --exitonsuccess
POPD
COPY /Y %FIXTURE% %TMPDIR%\deepl_fa.docx > NUL
PUSHD %TMPDIR%
set "PYTHONPATH=..\src" && %PYTHON% -m machine_translate_docx.cli --docxfile deepl_fa.docx --srclang en --destlang fa --engine deepl --enginemethod phrasesblock --silent --exitonsuccess
POPD
GOTO END

:LIVE_GOOGLE
IF NOT EXIST %TMPDIR% MKDIR %TMPDIR%
COPY /Y %FIXTURE% %TMPDIR%\google_fr.docx > NUL
PUSHD %TMPDIR%
set "PYTHONPATH=..\src" && %PYTHON% -m machine_translate_docx.cli --docxfile google_fr.docx --srclang en --destlang fr --engine google --enginemethod phrasesblock --silent --exitonsuccess
POPD
COPY /Y %FIXTURE% %TMPDIR%\google_fa.docx > NUL
PUSHD %TMPDIR%
set "PYTHONPATH=..\src" && %PYTHON% -m machine_translate_docx.cli --docxfile google_fa.docx --srclang en --destlang fa --engine google --enginemethod phrasesblock --silent --exitonsuccess
POPD
GOTO END

:LIVE_ALL
CALL %~f0 live-deepl
CALL %~f0 live-google
GOTO END

:CLEAN
IF EXIST %TMPDIR% RMDIR /S /Q %TMPDIR%
FOR /D /R %%i IN (__pycache__) DO IF EXIST "%%i" RMDIR /S /Q "%%i"
GOTO END

:END
ENDLOCAL
