@echo off
rem Live moment after 13:00: share the staff app that SUBMIT.bat just built on the validation pictures.
rem Run SUBMIT.bat on the validation images first; this file then serves submission\dashboard and opens a QR code.
rem Phones must be on the same Wi-Fi. Nothing is uploaded. Close this window to stop.
setlocal
cd /d "%~dp0"
title fresh. - live demo on the validation pictures (close this window to stop)
if not exist ".venv\Scripts\python.exe" (
  echo ERROR: .venv\Scripts\python.exe not found next to this file.
  pause
  exit /b 2
)
if not exist "submission\dashboard\index.html" (
  echo.
  echo The staff app for the validation pictures is not there yet.
  echo Run SUBMIT.bat on the validation images first, then double-click LIVE_DEMO.bat again.
  echo.
  pause
  exit /b 1
)
for %%F in ("submission\dashboard\index.html") do echo Staff app built at %%~tF - check this is the validation run, not a rehearsal.
.venv\Scripts\python -u tools\share_app.py --dir submission\dashboard
pause
