@echo off
rem LABEL-FREE FALLBACK (use only if AI-made annotations are not allowed). Validation day: double-click, or drag the validation FOLDER / .zip (or the image files) onto this file.
rem Result: submission_label_free\predictions.json (hand this in) and submission_label_free\dashboard\index.html (staff app).
rem Extra options can follow the paths, e.g.  SUBMIT_LABEL_FREE.bat "D:\val.zip" --no-detect
rem Exit code, as for python -m sensei submit: 0 check passed, 1 check failed, 2 input error.
rem Set SENSEI_NOPAUSE=1 to skip the final pause when calling this file from a script.
setlocal
set "CODE=2"
cd /d "%~dp0"
title fresh. - validation run (LABEL-FREE fallback model)
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe not found next to this file.
  goto done
)
if "%~1"=="" goto ask

rem Collect the arguments; a trailing backslash (from dragging "C:\folder\") is removed.
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
.venv\Scripts\python -m sensei submit --model models/real_v1 --out submission_label_free --images %ARGS%
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" (echo FAILED - read the messages above. Exit code: %CODE%) else (echo Finished OK.)

:done
echo.
if not defined SENSEI_NOPAUSE pause
exit /b %CODE%
