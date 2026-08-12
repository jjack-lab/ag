param(
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelPath = Join-Path $projectRoot "models\detection\yolo11s-waid.pt"
$apiPath = Join-Path $projectRoot "run_api.py"
$webRoot = Join-Path $projectRoot "web"
$webPackage = Join-Path $webRoot "package.json"

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

$npmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if (-not $npmCommand) {
    Stop-WithDiagnostic "npm.cmd was not found. Install Node.js first."
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
    -FilePath $npmCommand.Source `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1") `
    -WorkingDirectory $webRoot `
    -WindowStyle Hidden `
    -PassThru

Write-Host "API started. PID: $($apiProcess.Id), URL: http://127.0.0.1:8000"
Write-Host "Web started. PID: $($webProcess.Id), URL: http://127.0.0.1:5173"
Write-Host "Stop command: Stop-Process -Id $($apiProcess.Id),$($webProcess.Id)"
