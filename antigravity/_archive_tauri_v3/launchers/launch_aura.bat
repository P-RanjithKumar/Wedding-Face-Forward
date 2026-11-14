@echo off
setlocal
:: Change to the current script directory
cd /d %~dp0

echo ==========================================
echo          AURA - DARK intelligence
echo        System Launch & Cleanup Tool
echo ==========================================
echo.

:: Check for powershell
where powershell >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: PowerShell is not found in your PATH. 
    echo Please make sure Windows PowerShell is installed.
    pause
    exit /b 1
)

:: Run the PowerShell script with Bypass execution policy
powershell -NoProfile -ExecutionPolicy Bypass -File "launch_aura.ps1"

echo.
echo Process completed. You can close this window.
pause
