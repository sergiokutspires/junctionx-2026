@echo off
rem Show the staff app on phones: serves it from this laptop and opens a QR code to scan.
rem Phones must be on the same Wi-Fi. Nothing is uploaded. Close this window to stop.
rem Optional: SHARE_APP.bat --dir outputs\rehearsal_0850\dashboard
cd /d "%~dp0"
title Fresh Eyes - sharing the staff app (close this window to stop)
.venv\Scripts\python -u tools\share_app.py %*
pause
