@echo off
setlocal
cd /d "%~dp0"

REM Keep this wrapper ASCII-only. User-facing messages belong in run.ps1.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0run.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Application startup failed. Review the PowerShell error above.
  pause
  exit /b %EXIT_CODE%
)

exit /b 0
