@echo off
rem Double-click to test AURA, build it and make the installer.
rem Extra options can be passed on, e.g.:  build_and_test.bat -TestsOnly
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_and_test.ps1" %*
echo.
pause
