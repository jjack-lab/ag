param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelPath = Join-Path $projectRoot "models\detection\yolo11s-waid.pt"
$apiPath = Join-Path $projectRoot "run_api.py"
$webRoot = Join-Path $projectRoot "web"
$webPackage = Join-Path $webRoot "package.json"
$webVite = Join-Path $webRoot "node_modules\.bin\vite.cmd"
$preflightPath = Join-Path $projectRoot "scripts\preflight.py"
$processStatePath = Join-Path $projectRoot "data\delivery-processes.json"
$stopScriptPath = Join-Path $projectRoot "stop_delivery.ps1"
$logRoot = Join-Path $projectRoot "data\logs"
$apiStdoutLog = Join-Path $logRoot "api.stdout.log"
$apiStderrLog = Join-Path $logRoot "api.stderr.log"
$webStdoutLog = Join-Path $logRoot "web.stdout.log"
$webStderrLog = Join-Path $logRoot "web.stderr.log"

function Stop-WithDiagnostic {
    param([string]$Message)
    Write-Error $Message
    exit 1
}

function Show-DeliveryLogTail {
    param(
        [string]$Label,
        [string]$Path
    )

    try {
        if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
            return
        }
        $lines = @(Get-Content -LiteralPath $Path -Tail 40 -ErrorAction Stop)
        if ($lines.Count -eq 0) {
            return
        }
        Write-Host "----- $Label ($Path) -----"
        foreach ($line in $lines) {
            Write-Host $line
        }
    } catch {
        $warningMessage = "Unable to read delivery log: $Path ($($_.Exception.Message))"
        try {
            Write-Warning $warningMessage -WarningAction Continue
        } catch {
        }
    }
}

$pythonCandidates = @()
if ($env:AGRINEBULA_PYTHON) {
    $pythonCandidates += $env:AGRINEBULA_PYTHON
}
$pythonCandidates += (Join-Path $projectRoot ".venv\Scripts\python.exe")
$pathPython = Get-Command python.exe -ErrorAction SilentlyContinue
if ($pathPython) {
    $pythonCandidates += $pathPython.Source
}
$pythonPath = $pythonCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
    Select-Object -First 1

if (-not $pythonPath) {
    Stop-WithDiagnostic "Python was not found. Set AGRINEBULA_PYTHON to python.exe."
}
if (-not (Test-Path -LiteralPath $modelPath -PathType Leaf)) {
    Stop-WithDiagnostic "Delivery model was not found: $modelPath"
}
if (-not (Test-Path -LiteralPath $apiPath -PathType Leaf)) {
    Stop-WithDiagnostic "API entry point was not found: $apiPath"
}
if (-not (Test-Path -LiteralPath $webPackage -PathType Leaf)) {
    Stop-WithDiagnostic "Web package was not found: $webPackage"
}
if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    Stop-WithDiagnostic "npm.cmd was not found. Install Node.js first."
}
if (-not (Test-Path -LiteralPath $webVite -PathType Leaf)) {
    Stop-WithDiagnostic "Web dependencies are missing. Run npm ci in: $webRoot"
}
if (-not (Test-Path -LiteralPath $preflightPath -PathType Leaf)) {
    Stop-WithDiagnostic "Python preflight is missing: $preflightPath"
}

Write-Host "Running Python dependency and model preflight..."
& $pythonPath $preflightPath
if ($LASTEXITCODE -ne 0) {
    Stop-WithDiagnostic "Python dependency or model preflight failed."
}

Write-Host "Project: $projectRoot"
Write-Host "Python: $pythonPath"
Write-Host "Detector: $modelPath"
Write-Host "API: $apiPath"
Write-Host "Web: $webRoot"

if ($CheckOnly) {
    Write-Host "Delivery preflight passed."
    exit 0
}

if (Test-Path -LiteralPath $processStatePath -PathType Leaf) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stopScriptPath
    if ($LASTEXITCODE -ne 0) {
        Stop-WithDiagnostic "Existing delivery process state could not be cleaned safely."
    }
}

$occupied = @(Get-NetTCPConnection -LocalPort 8000,5173 -State Listen -ErrorAction SilentlyContinue)
if ($occupied.Count -gt 0) {
    $details = ($occupied | ForEach-Object { "$($_.LocalPort):PID $($_.OwningProcess)" }) -join ", "
    Stop-WithDiagnostic "Refusing to start because delivery ports are occupied: $details"
}

try {
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllText($apiStdoutLog, "", $utf8NoBom)
    [System.IO.File]::WriteAllText($apiStderrLog, "", $utf8NoBom)
    [System.IO.File]::WriteAllText($webStdoutLog, "", $utf8NoBom)
    [System.IO.File]::WriteAllText($webStderrLog, "", $utf8NoBom)
} catch {
    Stop-WithDiagnostic "Unable to initialize delivery logs: $logRoot ($($_.Exception.Message))"
}

$createdAt = (Get-Date).ToUniversalTime().ToString("o")
$apiProcess = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @($apiPath) `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $apiStdoutLog `
    -RedirectStandardError $apiStderrLog `
    -WindowStyle Hidden `
    -PassThru

$webProcess = Start-Process `
    -FilePath $webVite `
    -ArgumentList @("--host", "127.0.0.1") `
    -WorkingDirectory $webRoot `
    -RedirectStandardOutput $webStdoutLog `
    -RedirectStandardError $webStderrLog `
    -WindowStyle Hidden `
    -PassThru

$state = @{
    project_root = $projectRoot
    api_pid = $apiProcess.Id
    web_pid = $webProcess.Id
    created_at = $createdAt
} | ConvertTo-Json
$stateDir = Split-Path -Parent $processStatePath
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
[System.IO.File]::WriteAllText(
    $processStatePath,
    $state,
    [System.Text.UTF8Encoding]::new($false)
)

$apiReady = $false
$webReady = $false
for ($attempt = 0; $attempt -lt 30; $attempt++) {
    $apiProcess.Refresh()
    $webProcess.Refresh()
    if ($apiProcess.HasExited -or $webProcess.HasExited) {
        break
    }
    try {
        $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2
        $apiReady = $health.status -eq "ok"
    } catch {
        $apiReady = $false
    }
    try {
        $webResponse = Invoke-WebRequest -UseBasicParsing -Uri "http://127.0.0.1:5173" -TimeoutSec 2
        $webReady = $webResponse.StatusCode -eq 200
    } catch {
        $webReady = $false
    }
    if ($apiReady -and $webReady) {
        break
    }
    Start-Sleep -Milliseconds 500
}

$apiProcess.Refresh()
$webProcess.Refresh()
if ($apiProcess.HasExited -or $webProcess.HasExited -or -not ($apiReady -and $webReady)) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stopScriptPath
    Show-DeliveryLogTail "API stdout" $apiStdoutLog
    Show-DeliveryLogTail "API stderr" $apiStderrLog
    Show-DeliveryLogTail "Web stdout" $webStdoutLog
    Show-DeliveryLogTail "Web stderr" $webStderrLog
    Stop-WithDiagnostic "API or Web failed to become ready from this start attempt."
}

Write-Host "API ready. PID: $($apiProcess.Id), URL: http://127.0.0.1:8000"
Write-Host "Web ready. PID: $($webProcess.Id), URL: http://127.0.0.1:5173"
Write-Host "Logs: $logRoot"
Write-Host "Stop command: powershell -NoProfile -ExecutionPolicy Bypass -File $stopScriptPath"
