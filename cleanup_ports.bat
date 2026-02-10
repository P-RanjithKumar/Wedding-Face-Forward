@echo off
echo ==========================================
echo Wedding FF - System Cleanup
echo ==========================================

echo [1/3] Searching for processes on port 8000...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8000') do (
    echo Found process on port 8000 (PID: %%a). Terminating...
    taskkill /F /PID %%a /T
)

echo [2/3] Cleaning up stray Python processes...
taskkill /F /IM python.exe /T 2>nul

echo [3/3] Cleaning up stray Chromium/Playwright processes...
taskkill /F /IM chrome.exe /T 2>nul
taskkill /F /IM chromium.exe /T 2>nul

echo.
echo cleanup complete! You can now restart WeddingFFapp.py
pause
