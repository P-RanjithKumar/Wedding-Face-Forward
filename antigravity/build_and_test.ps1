<#
.SYNOPSIS
    Test AURA, build the app, check the built app, and make the installer.

.DESCRIPTION
    Steps (stops at the first failure and says where to look):
      1. Prerequisites  - Python packages, Inno Setup, Google sign-in client file
      2. Tests          - backend unit tests + the checks in dev_checks\ (about 4 min)
      3. Build          - PyInstaller -> dist\AURA\AURA.exe (about 20 min)
      4. Built-app check- runs the built AURA.exe as a fresh install, offline (about 3 min)
      5. Installer      - Inno Setup -> Output\AURA_Setup_<version>.exe (about 5 min)

    Safe to run while the installed AURA is open: tests use their own ports and
    temporary folders (%TEMP%\aura_checks), never your real photos or settings.
    Logs of every step: logs\build\<date-time>\ (inside this folder).

.EXAMPLE
    .\build_and_test.ps1                 # everything (about 30 min)
.EXAMPLE
    .\build_and_test.ps1 -TestsOnly      # only step 1 and 2 (about 4 min)
.EXAMPLE
    .\build_and_test.ps1 -SkipTests      # steps 1, 3, 4, 5
.EXAMPLE
    .\build_and_test.ps1 -Clean          # build from scratch (slower, use after changing Python packages)
.EXAMPLE
    .\build_and_test.ps1 -FullCheck      # also test the WhatsApp browser download (~150 MB)
#>
param(
    [switch]$TestsOnly,
    [switch]$SkipTests,
    [switch]$Clean,
    [switch]$FullCheck
)

$ErrorActionPreference = 'Stop'
$Root = $PSScriptRoot
Set-Location $Root
$Stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm'
$LogDir = Join-Path $Root "logs\build\$Stamp"
$Work = Join-Path $env:TEMP 'aura_checks'
New-Item -ItemType Directory -Force -Path $LogDir, $Work | Out-Null
$Started = Get-Date
$Results = New-Object System.Collections.Generic.List[string]

$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'

function Write-Step($text) { Write-Host ""; Write-Host "=== $text" -ForegroundColor Cyan }
function Write-Ok($text)   { Write-Host "  OK    $text" -ForegroundColor Green; $Results.Add("OK    $text") }
function Write-Bad($text)  { Write-Host "  FAIL  $text" -ForegroundColor Red; $Results.Add("FAIL  $text") }
function Write-Info($text) { Write-Host "        $text" -ForegroundColor Gray }

function Stop-WithFailure($what, $log) {
    Write-Host ""
    Write-Host "STOPPED: $what failed." -ForegroundColor Red
    if ($log) {
        Write-Host "Last lines of $log :" -ForegroundColor Yellow
        Get-Content $log -Tail 25 -ErrorAction SilentlyContinue | ForEach-Object { Write-Host "    $_" }
    }
    Write-Host ""
    Write-Host "All logs: $LogDir" -ForegroundColor Yellow
    exit 1
}

# Run a program, send all its output to a log file (optionally also to the screen).
# Uses cmd so Python's error output does not turn into PowerShell errors.
function Invoke-Logged {
    param([string]$Log, [string[]]$Command, [hashtable]$Env = @{}, [switch]$Show)
    $line = ($Command | ForEach-Object { if ($_ -match '[\s&()]') { '"' + $_ + '"' } else { $_ } }) -join ' '
    $saved = @{}
    foreach ($k in $Env.Keys) { $saved[$k] = [Environment]::GetEnvironmentVariable($k); Set-Item "env:$k" $Env[$k] }
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($Show) {
            cmd /s /c " $line 2>&1 " | Tee-Object -FilePath $Log | ForEach-Object { Write-Host "        $_" }
        } else {
            cmd /s /c " $line > `"$Log`" 2>&1 "
        }
        return $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $prev
        foreach ($k in $saved.Keys) {
            if ($null -eq $saved[$k]) { Remove-Item "env:$k" -ErrorAction SilentlyContinue } else { Set-Item "env:$k" $saved[$k] }
        }
    }
}

function Test-Check {
    # A dev_checks script passes when it exits with 0 AND prints "ALL CHECKS PASSED"
    param([string]$Name, [string]$Script, [string[]]$ScriptArgs, [hashtable]$Env = @{})
    $log = Join-Path $LogDir "$Name.log"
    $t = Get-Date
    $code = Invoke-Logged -Log $log -Command (@('python', $Script) + $ScriptArgs) -Env $Env
    $secs = [int]((Get-Date) - $t).TotalSeconds
    $passed = ($code -eq 0) -and (Select-String -Path $log -Pattern 'ALL CHECKS PASSED' -SimpleMatch -Quiet)
    if ($passed) { Write-Ok "$Name ($secs s)" } else { Write-Bad "$Name ($secs s)"; Stop-WithFailure $Name $log }
}

Write-Host "AURA build and test   $(Get-Date -Format 'yyyy-MM-dd HH:mm')" -ForegroundColor White
Write-Host "Logs: $LogDir"

# ─────────────────────────────────────────────────────────────────────────────
Write-Step "1. Prerequisites"
$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { Write-Bad "Python not found on PATH"; Stop-WithFailure "Prerequisites" $null }
Write-Ok "Python: $($py.Source)"

$probe = Join-Path $LogDir 'prereq.log'
$probePy = Join-Path $LogDir 'prereq_check.py'
@'
import importlib.util, os, sys
need = ["PyInstaller", "PySide6", "insightface", "onnxruntime", "fastapi", "uvicorn", "segno", "playwright", "pytest", "PIL", "cv2", "numpy"]
missing = [m for m in need if importlib.util.find_spec(m) is None]
import onnxruntime as ort
import insightface
print("ORT", ort.__version__, ",".join(ort.get_available_providers()))
print("PHOTO", os.path.join(os.path.dirname(insightface.__file__), "data", "images", "t1.jpg"))
print("MISSING", ",".join(missing))
sys.exit(1 if missing else 0)
'@ | Out-File $probePy -Encoding utf8
$code = Invoke-Logged -Log $probe -Command @('python', $probePy)
$probeText = Get-Content $probe
if ($code -ne 0) { Write-Bad "Python packages missing: $(($probeText | Select-String '^MISSING').Line)"; Write-Info "Install with: python -m pip install -r backend\requirements.txt pyinstaller pyside6 playwright pytest"; Stop-WithFailure "Prerequisites" $probe }
$ortLine = ($probeText | Select-String '^ORT').Line
$Photo = (($probeText | Select-String '^PHOTO').Line).Substring(6)
if ($ortLine -notmatch 'DmlExecutionProvider') {
    Write-Bad "onnxruntime-directml is not installed (GPU support would be missing): $ortLine"
    Write-Info "Fix: python -m pip uninstall -y onnxruntime onnxruntime-gpu; python -m pip install onnxruntime-directml==1.24.1"
    Stop-WithFailure "Prerequisites" $probe
}
Write-Ok "Python packages ($ortLine)"
if (-not (Test-Path $Photo)) { Write-Bad "Test photo not found: $Photo"; Stop-WithFailure "Prerequisites" $null }

$Iscc = @("$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
        Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $TestsOnly) {
    if (-not $Iscc) { Write-Bad "Inno Setup 6 not found (needed for the installer)"; Write-Info "Download from https://jrsoftware.org/isdl.php"; Stop-WithFailure "Prerequisites" $null }
    Write-Ok "Inno Setup: $Iscc"
}

$secrets = if ($env:AURA_SECRETS_DIR) { $env:AURA_SECRETS_DIR } else { Join-Path $env:USERPROFILE 'AURA-secrets' }
$client = @((Join-Path $secrets 'credentials.json'), (Join-Path $Root 'credentials.json')) | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $client) { Write-Bad "credentials.json (Google sign-in client) not found in $secrets"; Stop-WithFailure "Prerequisites" $null }
Write-Ok "Google sign-in client: $client"

# ─────────────────────────────────────────────────────────────────────────────
if (-not $SkipTests) {
    Write-Step "2. Tests (about 4 minutes)"
    $log = Join-Path $LogDir 'unit_tests.log'
    $t = Get-Date
    # pytest runs from backend\ (the tests import "app")
    Push-Location (Join-Path $Root 'backend')
    try { $code = Invoke-Logged -Log $log -Command @('python', '-m', 'pytest', '-q', 'tests', '-p', 'no:cacheprovider') } finally { Pop-Location }
    $summary = (Get-Content $log | Select-Object -Last 1)
    if ($code -eq 0) { Write-Ok "Backend unit tests: $summary ($([int]((Get-Date) - $t).TotalSeconds) s)" } else { Write-Bad "Backend unit tests: $summary"; Stop-WithFailure "Backend unit tests" $log }

    $qt = @{ 'QT_QPA_PLATFORM' = 'offscreen'; 'QT_QPA_FONTDIR' = 'C:\Windows\Fonts' }
    Test-Check 'first_launch_and_secrets' 'dev_checks\test_step2.py'       @($Root, $Work)
    Test-Check 'guest_server_security'    'dev_checks\test_step3.py'       @($Root, $Work)
    Test-Check 'guest_page_phone_flow'    'dev_checks\test_step3b.py'      @($Root, $Work)
    Test-Check 'clustering_and_merge'     'dev_checks\test_step4.py'       @($Root, $Work)
    Test-Check 'ports_crashes_cleanup'    'dev_checks\test_reliability.py' @($Root, $Work) $qt
    Test-Check 'share_links_and_gallery'  'dev_checks\test_share.py'       @($Root, $Work) $qt
    Test-Check 'gpu_cpu_choice'           'dev_checks\test_compute.py'     @($Root, $Photo, $Work)
}
if ($TestsOnly) {
    Write-Host ""
    Write-Host "ALL TESTS PASSED in $([int]((Get-Date) - $Started).TotalMinutes) min. Logs: $LogDir" -ForegroundColor Green
    exit 0
}

# ─────────────────────────────────────────────────────────────────────────────
Write-Step "3. Build the app (about 20 minutes)"
Write-Info "Live log: $(Join-Path $LogDir 'pyinstaller.log')"
$log = Join-Path $LogDir 'pyinstaller.log'
$t = Get-Date
$buildCmd = @('python', '-m', 'PyInstaller', 'aura.spec', '--noconfirm')
if ($Clean) { $buildCmd += '--clean' }
$code = Invoke-Logged -Log $log -Command $buildCmd
$exe = Join-Path $Root 'dist\AURA\AURA.exe'
if ($code -ne 0 -or -not (Test-Path $exe) -or (Select-String -Path $log -Pattern 'BUILD STOPPED' -SimpleMatch -Quiet)) {
    Write-Bad "PyInstaller build"; Stop-WithFailure "Build" $log
}
Write-Ok "Built dist\AURA\AURA.exe ($([int]((Get-Date) - $t).TotalMinutes) min)"

# ─────────────────────────────────────────────────────────────────────────────
Write-Step "4. Check the built app (about 3 minutes; an AURA window opens for 30 s, leave it)"
$smokeEnv = @{}
if (-not $FullCheck) { $smokeEnv['SMOKE_SKIP_CHROMIUM'] = '1' }
Test-Check 'built_app_check' 'dev_checks\smoke_frozen.py' @($Root, $Work, $Photo) $smokeEnv
Select-String -Path (Join-Path $LogDir 'built_app_check.log') -Pattern 'speed test ran' -SimpleMatch | ForEach-Object { Write-Info ($_.Line.Trim()) }

# ─────────────────────────────────────────────────────────────────────────────
Write-Step "5. Make the installer (about 5 minutes)"
# Writing straight into Output\ often fails ("EndUpdateResource ... antivirus"),
# so compile into a temp folder and move the file afterwards.
$out = Join-Path $Work 'installer'
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
$log = Join-Path $LogDir 'installer.log'
$code = 1
foreach ($try in 1, 2) {
    $code = Invoke-Logged -Log $log -Command @($Iscc, "/O$out", 'aura.iss')
    if ($code -eq 0) { break }
    Write-Info "Installer attempt $try failed, retrying..."
}
$setup = Get-ChildItem $out -Filter 'AURA_Setup_*.exe' -ErrorAction SilentlyContinue | Select-Object -First 1
if ($code -ne 0 -or -not $setup) { Write-Bad "Inno Setup"; Stop-WithFailure "Installer" $log }
$dest = Join-Path $Root "Output\$($setup.Name)"
New-Item -ItemType Directory -Force -Path (Join-Path $Root 'Output') | Out-Null
Move-Item $setup.FullName $dest -Force
$hash = (Get-FileHash $dest -Algorithm SHA256).Hash.Substring(0, 16).ToLower()
$size = [math]::Round((Get-Item $dest).Length / 1MB)
Write-Ok "Installer: $dest ($size MB, sha256 $hash)"

# ─────────────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host " ALL DONE in $([int]((Get-Date) - $Started).TotalMinutes) min" -ForegroundColor Green
Write-Host " Installer: $dest" -ForegroundColor Green
Write-Host " Logs:      $LogDir" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
$Results | Out-File (Join-Path $LogDir 'summary.txt') -Encoding utf8
exit 0
