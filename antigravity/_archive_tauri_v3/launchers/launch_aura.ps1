# AURA - Dark Intelligence System Launch Tool
# This script cleans up ports and launches the backend components and frontend dashboard.

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
                $pid = $conn.OwningProcess
                if ($pid) {
                    Write-Host " - Found process on Port $port (PID: $pid). Terminating..." -ForegroundColor Gray
                    Stop-Process -Id $pid -Force -ErrorAction SilentlyContinue
                }
            }
        }
    } catch {
        # Fallback for systems where Get-NetTCPConnection might fail or require elevation
        $netstat = netstat -ano | Select-String ":$port "
        if ($netstat) {
            foreach ($line in $netstat) {
                $parts = $line.ToString().Split(" ", [System.StringSplitOptions]::RemoveEmptyEntries)
                $pid = $parts[$parts.Length - 1]
                if ($pid -match '^\d+$') {
                    Write-Host " - Found process on Port $port (PID: $pid). Terminating..." -ForegroundColor Gray
                    taskkill /F /PID $pid /T 2>$null
                }
            }
        }
    }
}

Stop-ProcessOnPort 8000
Stop-ProcessOnPort 3000

# Aggressive cleanup of Node and Python instances related to memory leaks
Write-Host " - Performing aggressive cleanup of stray Node/Python processes..." -ForegroundColor Gray
Get-Process node -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process python -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like "*backend_entry*" -or $_.CommandLine -like "*uvicorn*" } | Stop-Process -Force

# Remove Next.js dev lock if it exists
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
    exit
}

# 3. LAUNCH COMPONENTS
Write-Host "[2/3] STARTING BACKEND COMPONENTS..." -ForegroundColor Green

# Start Server (8000)
Write-Host " -> Starting FastAPI Server (Port 8000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='AURA SERVER (8000)'; python backend_entry.py --run-server" -WindowStyle Normal

# Start Worker
Write-Host " -> Starting Processing Worker..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='AURA WORKER'; python backend_entry.py --run-worker" -WindowStyle Normal

# Start WhatsApp Sender (Optional but useful)
Write-Host " -> Starting WhatsApp Tool..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='AURA WHATSAPP'; python backend_entry.py --run-whatsapp" -WindowStyle Normal

Write-Host ""
Write-Host "[3/3] STARTING FRONTEND DASHBOARD..." -ForegroundColor Green

# Start Next.js (3000)
Write-Host " -> Starting Next.js Dev Server (Port 3000)..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$Host.UI.RawUI.WindowTitle='AURA FRONTEND (3000)'; cd aura_web; npm run dev" -WindowStyle Normal

# 4. OPEN INTERFACES
Write-Host ""
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       AURA IS STARTING UP!               " -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host " Waiting for servers to initialize before opening browser..." -ForegroundColor Gray
Start-Sleep -Seconds 6

Write-Host " Launching Interfaces:" -ForegroundColor Magenta
Write-Host "  - Admin Dashboard: http://localhost:3000" -ForegroundColor Cyan
Write-Host "  - Guest Registration: http://localhost:8000" -ForegroundColor Cyan

# Open Admin Control Center
Start-Process "http://localhost:3000"
# Open Guest Registration / Find Photos
Start-Process "http://localhost:8000"

Write-Host ""
Write-Host "Done! Keep the powershell windows open to see logs." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Cyan
pause
