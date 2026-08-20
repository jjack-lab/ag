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
        $lines = @(Get-Content -LiteralPath $Path -Encoding UTF8 -Tail 40 -ErrorAction Stop)
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

function Stop-StartedProcessTrees {
    param(
        [object[]]$ProcessRecords,
        [string]$ProjectRoot,
        [int]$TimeoutMilliseconds = 5000
    )

    $errors = @()
    $survivors = @()
    $targets = @()
    if (-not $ProcessRecords -or $ProcessRecords.Count -eq 0) {
        return [pscustomobject]@{
            success = $true
            survivor_ids = @()
            errors = @()
        }
    }

    try {
        $snapshot = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    } catch {
        $rootIds = @($ProcessRecords | ForEach-Object { [int]$_.id } | Where-Object { $_ -gt 0 })
        $errors += "Unable to enumerate delivery process identities: $($_.Exception.Message)"
        return [pscustomobject]@{
            success = $false
            survivor_ids = $rootIds
            errors = $errors
        }
    }

    $pending = [System.Collections.Generic.Queue[object]]::new()
    foreach ($record in $ProcessRecords) {
        $id = [int]$record.id
        if ($id -le 0) {
            continue
        }
        $live = Get-Process -Id $id -ErrorAction SilentlyContinue
        if (-not $live) {
            continue
        }
        $snapshotProcess = $snapshot | Where-Object { [int]$_.ProcessId -eq $id } | Select-Object -First 1
        $expectedTicks = [long]$record.start_time_ticks
        $actualTicks = [long]$live.StartTime.ToUniversalTime().Ticks
        if (
            -not $snapshotProcess -or
            $actualTicks -ne $expectedTicks -or
            [string]$snapshotProcess.CommandLine -notlike "*$ProjectRoot*"
        ) {
            $errors += "Process identity mismatch for PID $id; refusing rollback termination."
            $survivors += $id
            continue
        }
        $target = [pscustomobject]@{
            id = $id
            parent_id = [int]$snapshotProcess.ParentProcessId
            creation_date = [DateTime]$snapshotProcess.CreationDate
            depth = 0
            record = $record
        }
        $targets += $target
        $pending.Enqueue($target)
    }

    while ($pending.Count -gt 0) {
        $parent = $pending.Dequeue()
        foreach ($child in $snapshot | Where-Object { [int]$_.ParentProcessId -eq [int]$parent.id }) {
            $childId = [int]$child.ProcessId
            if ($targets.id -contains $childId) {
                continue
            }
            $target = [pscustomobject]@{
                id = $childId
                parent_id = [int]$child.ParentProcessId
                creation_date = [DateTime]$child.CreationDate
                depth = [int]$parent.depth + 1
                record = $null
            }
            $targets += $target
            $pending.Enqueue($target)
        }
    }

    $waitIds = @()
    foreach ($target in $targets | Sort-Object depth -Descending) {
        $id = [int]$target.id
        $live = Get-Process -Id $id -ErrorAction SilentlyContinue
        if (-not $live) {
            continue
        }
        $identityMatches = $true
        if ($target.record) {
            $identityMatches = (
                [long]$live.StartTime.ToUniversalTime().Ticks -eq
                [long]$target.record.start_time_ticks
            )
        } else {
            $snapshotStart = ([DateTime]$target.creation_date).ToUniversalTime()
            $liveStart = $live.StartTime.ToUniversalTime()
            $identityMatches = [Math]::Abs(($liveStart - $snapshotStart).TotalSeconds) -le 2
        }
        if (-not $identityMatches) {
            $errors += "Process identity mismatch for PID $id; refusing rollback termination."
            $survivors += $id
            continue
        }
        $waitIds += $id
        try {
            Stop-Process -Id $id -Force -ErrorAction Stop
        } catch {
            $errors += "Unable to stop rollback PID ${id}: $($_.Exception.Message)"
        }
    }

    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    do {
        $remaining = @($waitIds | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
        if ($remaining.Count -eq 0) {
            break
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)

    $remaining = @($waitIds | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
    if ($remaining.Count -gt 0) {
        $errors += "Timed out waiting for rollback PIDs to exit: $($remaining -join ', ')"
        $survivors += $remaining
    }
    $survivors = @($survivors | Select-Object -Unique)
    return [pscustomobject]@{
        success = ($errors.Count -eq 0 -and $survivors.Count -eq 0)
        survivor_ids = $survivors
        errors = $errors
    }
}

function Invoke-DeliveryStartupRollback {
    param(
        [string]$OriginalError,
        [object[]]$ProcessRecords,
        [string]$ProjectRoot,
        [string]$ProcessStatePath,
        [string]$CreatedAt,
        [bool]$StateWriteAttempted,
        [int]$TimeoutMilliseconds = 5000
    )

    $rollbackParams = @{
        ProcessRecords = $ProcessRecords
        ProjectRoot = $ProjectRoot
        TimeoutMilliseconds = $TimeoutMilliseconds
    }
    $rollback = Stop-StartedProcessTrees @rollbackParams
    $survivors = @($rollback.survivor_ids)
    $rollbackErrors = @($rollback.errors)
    $stateError = $null

    if ($survivors.Count -eq 0) {
        try {
            if ($StateWriteAttempted -and (Test-Path -LiteralPath $ProcessStatePath -PathType Leaf)) {
                Remove-Item -LiteralPath $ProcessStatePath -Force -ErrorAction Stop
            }
        } catch {
            $stateError = "Unable to remove failed-attempt state: $($_.Exception.Message)"
        }
    } else {
        $apiPid = 0
        $webPid = 0
        foreach ($record in $ProcessRecords) {
            $id = [int]$record.id
            if ($survivors -notcontains $id) {
                continue
            }
            if ([string]$record.role -eq "api") {
                $apiPid = $id
            } elseif ([string]$record.role -eq "web") {
                $webPid = $id
            }
        }
        $recoveryState = @{
            project_root = $ProjectRoot
            api_pid = $apiPid
            web_pid = $webPid
            recovery_pids = $survivors
            created_at = $CreatedAt
        } | ConvertTo-Json
        try {
            $stateDir = Split-Path -Parent $ProcessStatePath
            New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
            [System.IO.File]::WriteAllText(
                $ProcessStatePath,
                $recoveryState,
                [System.Text.UTF8Encoding]::new($false)
            )
        } catch {
            $stateError = "Recovery state write failed: $($_.Exception.Message)"
        }
    }

    $parts = @("Delivery process startup failed: $OriginalError")
    if ($rollbackErrors.Count -gt 0) {
        $parts += "Rollback errors: $($rollbackErrors -join '; ')"
    }
    if ($survivors.Count -gt 0) {
        $parts += "Survivor PIDs: $($survivors -join ', ')"
        if (-not $stateError) {
            $parts += "Recovery state preserved: $ProcessStatePath"
        }
    }
    if ($stateError) {
        $parts += $stateError
    }
    return [pscustomobject]@{
        success = ($rollback.success -and -not $stateError)
        survivor_ids = $survivors
        errors = @($rollbackErrors + @($stateError) | Where-Object { $_ })
        message = ($parts -join ". ")
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
$startedProcesses = @()
$stateWriteAttempted = $false
try {
$apiProcess = Start-Process `
    -FilePath $pythonPath `
    -ArgumentList @($apiPath) `
    -WorkingDirectory $projectRoot `
    -RedirectStandardOutput $apiStdoutLog `
    -RedirectStandardError $apiStderrLog `
    -WindowStyle Hidden `
    -PassThru

$apiProcessRecord = [pscustomobject]@{
    id = $apiProcess.Id
    role = "api"
    start_time_ticks = $apiProcess.StartTime.ToUniversalTime().Ticks
    process = $apiProcess
}
$startedProcesses += $apiProcessRecord

$webProcess = Start-Process `
    -FilePath $webVite `
    -ArgumentList @("--host", "127.0.0.1") `
    -WorkingDirectory $webRoot `
    -RedirectStandardOutput $webStdoutLog `
    -RedirectStandardError $webStderrLog `
    -WindowStyle Hidden `
    -PassThru

$webProcessRecord = [pscustomobject]@{
    id = $webProcess.Id
    role = "web"
    start_time_ticks = $webProcess.StartTime.ToUniversalTime().Ticks
    process = $webProcess
}
$startedProcesses += $webProcessRecord

$state = @{
    project_root = $projectRoot
    api_pid = $apiProcess.Id
    web_pid = $webProcess.Id
    created_at = $createdAt
} | ConvertTo-Json
$stateDir = Split-Path -Parent $processStatePath
New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
$stateWriteAttempted = $true
[System.IO.File]::WriteAllText(
    $processStatePath,
    $state,
    [System.Text.UTF8Encoding]::new($false)
)

} catch {
    $startupError = $_.Exception.Message
    $rollbackParams = @{
        OriginalError = $startupError
        ProcessRecords = $startedProcesses
        ProjectRoot = $projectRoot
        ProcessStatePath = $processStatePath
        CreatedAt = $createdAt
        StateWriteAttempted = $stateWriteAttempted
    }
    $rollback = Invoke-DeliveryStartupRollback @rollbackParams
    Stop-WithDiagnostic $rollback.message
}

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
