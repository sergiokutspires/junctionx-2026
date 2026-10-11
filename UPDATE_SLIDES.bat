@echo off
rem After SUBMIT.bat: double-click to put the validation results on the pitch slide "Your validation pictures."
rem Reads submission\predictions.json, screenshots the staff app, rebuilds pitch\slides_standalone.html
rem and pitch\slides_backup.pdf. Optional: drag another submission folder onto this file.
rem Set SENSEI_NOPAUSE=1 to skip the final pause when calling this file from a script.
setlocal
set "CODE=2"
cd /d "%~dp0"
title fresh. - update the validation slide
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe not found next to this file.
  goto done
)
set "SUB=submission"
if not "%~1"=="" set "SUB=%~1"
if "%SUB:~-1%"=="\" if not "%SUB:~3,1%"=="" set "SUB=%SUB:~0,-1%"
.venv\Scripts\python tools\validation_slide.py --submission "%SUB%"
set "CODE=%ERRORLEVEL%"
echo.
if not "%CODE%"=="0" (echo FAILED - read the messages above. Exit code: %CODE%) else (
  echo Finished OK.
  echo Slides:     %~dp0pitch\slides.html  ^(slide 7^)
  echo Room PDF:   %~dp0pitch\slides_backup.pdf
)

:done
echo.
if not defined SENSEI_NOPAUSE pause
exit /b %CODE%
