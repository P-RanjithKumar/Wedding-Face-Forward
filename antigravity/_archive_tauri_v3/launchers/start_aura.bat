<# :
@echo off
setlocal
cd /d %~dp0
:: Check for powershell
where powershell >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] PowerShell is not found in your PATH.
    pause
    exit /b 1
)
:: Run this file as a PowerShell script
powershell -NoProfile -ExecutionPolicy Bypass -Command "iex ((Get-Content '%~f0') -join \"`n\")"
exit /b
#>

# ==========================================
#          AURA - DARK intelligence
#        System Launch & Cleanup Tool
# ==========================================

$Host.UI.RawUI.WindowTitle = "AURA System Launch"
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "          AURA - DARK intelligence        " -ForegroundColor Cyan
Write-Host "        System Launch & Cleanup Tool      " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 1. CLEAN UP PORTS
Write-Host "[1/3] CLEANING UP PORTS 8000 AND 3000..." -ForegroundColor Yellow

function Stop-ProcessOnPort($port) {
    try {
        $connection = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($connection) {
            foreach ($conn in $connection) {
                $procId = $conn.OwningProcess
                if ($procId) {
                    Write-Host " - Found process on Port $port (PID: $procId). Terminating..." -ForegroundColor Gray
                    Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
                }
            }
        }
    } catch {
        $netstat = netstat -ano | Select-String ":$port "
        if ($netstat) {
            foreach ($line in $netstat) {
                $parts = $line.ToString().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
                $procId = $parts[$parts.Length - 1]
                if ($procId -match '^\d+$') {
                    Write-Host " - Found process on Port $port (PID: $procId). Terminating..." -ForegroundColor Gray
                    taskkill /F /PID $procId /T 2>$null
                }
            }
        }
    }
}

Stop-ProcessOnPort 8000
Stop-ProcessOnPort 3000

# Aggressive cleanup
Write-Host " - Performing aggressive cleanup of stray Node/Python processes..." -ForegroundColor Gray
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process python -ErrorAction SilentlyContinue | Where-Object { 
    $_.CommandLine -like "*backend_entry*" -or $_.CommandLine -like "*uvicorn*" -or $_.CommandLine -like "*aura_web*" 
} | Stop-Process -Force

# Remove Next.js dev lock
$lockFile = "aura_web\.next\dev\lock"
if (Test-Path $lockFile) {
    Remove-Item -Path $lockFile -Force -ErrorAction SilentlyContinue
}

Write-Host "`n[OK] PORTS CLEANED SUCCESSFULLY!" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# 2. PROMPT FOR LAUNCH
$choice = Read-Host "Do you want to launch the AURA app? (y/n)"
Write-Host ""

if ($choice.ToLower() -ne "y") {
    Write-Host "==========================================" -ForegroundColor Yellow
    Write-Host "   STOPPED. Only port cleanup was done.  " -ForegroundColor Yellow
    Write-Host "==========================================" -ForegroundColor Yellow
    Write-Host "Press any key to exit..."
    [void][System.Console]::ReadKey($true)
    exit
}

# 3. LAUNCH COMPONENTS
Write-Host "[2/3] STARTING BACKEND COMPONENTS..." -ForegroundColor Green

# Start Server (8000)
Write-Host " -> Starting FastAPI Server (Port 8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='AURA SERVER (8000)'; python backend_entry.py --run-server"

# Start Worker
if (Test-Path "backend_entry.py") {
    Write-Host " -> Starting Processing Worker..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='AURA WORKER'; python backend_entry.py --run-worker"
}

# Start WhatsApp Sender
if (Test-Path "backend_entry.py") {
    Write-Host " -> Starting WhatsApp Tool..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='AURA WHATSAPP'; python backend_entry.py --run-whatsapp"
}

Write-Host ""
Write-Host "[3/3] STARTING FRONTEND DASHBOARD..." -ForegroundColor Green

# Start Next.js (3000)
if (Test-Path "aura_web") {
    Write-Host " -> Starting Next.js Dev Server (Port 3000)..." -ForegroundColor Cyan
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='AURA FRONTEND (3000)'; cd aura_web; npm run dev"
} else {
    Write-Host " [WARNING] aura_web directory not found!" -ForegroundColor Red
}

# 4. OPEN INTERFACES
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       AURA IS STARTING UP!               " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Waiting 8 seconds for servers to initialize..." -ForegroundColor Gray
Start-Sleep -Seconds 8

Write-Host " Launching Interfaces:" -ForegroundColor Magenta
Write-Host "  - Admin Dashboard: http://localhost:3000" -ForegroundColor Cyan
Write-Host "  - Guest Registration: http://localhost:8000" -ForegroundColor Cyan

# Open browser
Start-Process "http://localhost:3000"

Write-Host ""
Write-Host "Done! Keep the powershell windows open to see logs." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Press any key to close this controller..."
[void][System.Console]::ReadKey($true)
