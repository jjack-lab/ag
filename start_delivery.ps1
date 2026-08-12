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

function Stop-WithDiagnostic {
    param([string]$Message)
    Write-Error $Message
    exit 1
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

$apiProcess = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @($apiPath) `
    -WorkingDirectory $projectRoot `
    -WindowStyle Hidden `
    -PassThru

$webProcess = Start-Process `
    -FilePath $webVite `
    -ArgumentList @("--host", "127.0.0.1") `
    -WorkingDirectory $webRoot `
    -WindowStyle Hidden `
    -PassThru

$state = @{
    api_pid = $apiProcess.Id
    web_pid = $webProcess.Id
    created_at = (Get-Date).ToString("o")
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

if (-not ($apiReady -and $webReady)) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $stopScriptPath
    Stop-WithDiagnostic "API or Web failed to become ready."
}

Write-Host "API ready. PID: $($apiProcess.Id), URL: http://127.0.0.1:8000"
Write-Host "Web ready. PID: $($webProcess.Id), URL: http://127.0.0.1:5173"
Write-Host "Stop command: powershell -NoProfile -ExecutionPolicy Bypass -File $stopScriptPath"
