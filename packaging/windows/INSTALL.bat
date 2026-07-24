@echo off
setlocal
cd /d "%~dp0"

REM Keep this wrapper ASCII-only. User-facing messages belong in install.ps1.
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
  echo.
  echo Installation failed. Review the PowerShell error above.
  pause
  exit /b %EXIT_CODE%
)

echo.
echo Installation completed. Run RUN.bat to start the application.
pause
exit /b 0
