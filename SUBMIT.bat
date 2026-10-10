@echo off
rem Validation day: double-click, or drag the validation FOLDER / .zip (or the image files) onto this file.
rem Result: submission\predictions.json (hand this in) and submission\dashboard\index.html (staff app).
rem Extra options can follow the paths, e.g.  SUBMIT.bat "D:\val.zip" --no-detect
setlocal
cd /d "%~dp0"
title Sensei - validation run
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe not found next to this file.
  goto done
)
if "%~1"=="" goto ask

set "ARGS="
:next
if "%~1"=="" goto run
set "A=%~1"
if "%A:~-1%"=="\" if not "%A:~3,1%"=="" set "A=%A:~0,-1%"
set ARGS=%ARGS% "%A%"
shift
goto next

:ask
echo Drag the validation folder or .zip into this window (or type its path), then press Enter.
set "IMG="
set /p "IMG=Path: "
if not defined IMG (
  echo No path given.
  goto done
)
set "IMG=%IMG:"=%"
if "%IMG:~-1%"=="\" if not "%IMG:~3,1%"=="" set "IMG=%IMG:~0,-1%"
set ARGS="%IMG%"

:run
.venv\Scripts\python -m sensei submit --images %ARGS%
echo.
if errorlevel 1 (echo FAILED - read the messages above. Exit code: %ERRORLEVEL%) else (echo Finished OK.)

:done
echo.
if not defined SENSEI_NOPAUSE pause
