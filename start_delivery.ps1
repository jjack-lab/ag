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

function Get-DeliveryProcessIdentityState {
    param(
        [int]$Id,
        [object]$ExpectedStartTicks = $null,
        [int]$ExpectedTickPrecision = 1
    )

    $hasExpectedIdentity = $null -ne $ExpectedStartTicks
    $lastError = $null
    for ($attempt = 0; $attempt -lt 2; $attempt++) {
        try {
            $live = Get-Process -Id $Id -ErrorAction SilentlyContinue
        } catch {
            $lastError = $_.Exception.Message
            if ($attempt -eq 0) {
                continue
            }
            return [pscustomobject]@{ state = "unverifiable"; start_time_ticks = $null; error = $lastError }
        }
        if (-not $live) {
            return [pscustomobject]@{ state = "exited"; start_time_ticks = $null; error = $null }
        }
        try {
            $startTime = $live.StartTime
            if ($null -eq $startTime) {
                throw "Process StartTime was unavailable."
            }
            $ticks = [long]$startTime.ToUniversalTime().Ticks
        } catch {
            $lastError = $_.Exception.Message
            if ($attempt -eq 0) {
                continue
            }
            return [pscustomobject]@{ state = "unverifiable"; start_time_ticks = $null; error = $lastError }
        }
        if ($attempt -gt 0 -and -not $hasExpectedIdentity) {
            return [pscustomobject]@{ state = "unverifiable"; start_time_ticks = $null; error = $lastError }
        }
        if ($hasExpectedIdentity) {
            $expectedTicks = [long]$ExpectedStartTicks
            $comparableTicks = $ticks
            if ($ExpectedTickPrecision -gt 1) {
                $expectedTicks -= $expectedTicks % $ExpectedTickPrecision
                $comparableTicks -= $comparableTicks % $ExpectedTickPrecision
            }
            if ($comparableTicks -ne $expectedTicks) {
                return [pscustomobject]@{ state = "exited"; start_time_ticks = $ticks; error = $null }
            }
        }
        return [pscustomobject]@{ state = "same_identity_alive"; start_time_ticks = $ticks; error = $null }
    }
    return [pscustomobject]@{ state = "unverifiable"; start_time_ticks = $null; error = $lastError }
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
    try {
    if (-not $ProcessRecords -or $ProcessRecords.Count -eq 0) {
        return [pscustomobject]@{
            success = $true
            survivor_ids = @()
            survivor_processes = @()
            errors = @()
        }
    }

    try {
        $snapshot = @(Get-CimInstance Win32_Process -ErrorAction Stop)
    } catch {
        $rootIds = @($ProcessRecords | ForEach-Object { [int]$_.id } | Where-Object { $_ -gt 0 })
        $errors += "Unable to enumerate delivery process identities: $($_.Exception.Message)"
        $fallback = @($ProcessRecords | ForEach-Object { [pscustomobject]@{ pid = [int]$_.id; start_time_ticks = [long]$_.start_time_ticks; role = [string]$_.role } } | Where-Object { $_.pid -gt 0 })
        return [pscustomobject]@{
            success = $false
            survivor_ids = $rootIds
            survivor_processes = $fallback
            errors = $errors
        }
    }

    $pending = [System.Collections.Generic.Queue[object]]::new()
    $blockedAnchorIds = @()
    foreach ($record in $ProcessRecords) {
        $id = [int]$record.id
        if ($id -le 0) {
            continue
        }
        $snapshotProcess = $snapshot | Where-Object { [int]$_.ProcessId -eq $id } | Select-Object -First 1
        $expectedTicks = [long]$record.start_time_ticks
        $identity = Get-DeliveryProcessIdentityState -Id $id -ExpectedStartTicks $expectedTicks
        if ($identity.state -eq "exited") {
            if ($null -ne $identity.start_time_ticks) {
                $errors += "Process identity mismatch for PID $id; original instance already exited."
            }
            continue
        }
        if ($identity.state -eq "unverifiable") {
            $errors += "Unable to read process identity for PID $($id): $($identity.error)"
            $survivors += [pscustomobject]@{ pid = $id; start_time_ticks = $expectedTicks; role = [string]$record.role }
            continue
        }
        if (-not $snapshotProcess) {
            $errors += "Unable to confirm process ownership for PID $id from the CIM snapshot."
            $survivors += [pscustomobject]@{ pid = $id; start_time_ticks = $expectedTicks; role = [string]$record.role }
            continue
        }
        try {
            $commandLine = [string]$snapshotProcess.CommandLine
            $parentId = [int]$snapshotProcess.ParentProcessId
            $creationDate = [DateTime]$snapshotProcess.CreationDate
            $snapshotTicks = [long]$creationDate.ToUniversalTime().Ticks
        } catch {
            $errors += "Unable to read CIM identity for PID $($id): $($_.Exception.Message)"
            $survivors += [pscustomobject]@{ pid = $id; start_time_ticks = $expectedTicks; role = [string]$record.role }
            continue
        }
        if ($commandLine -notlike "*$ProjectRoot*") {
            $errors += "Process identity mismatch for PID $id; refusing rollback termination."
            continue
        }
        $target = [pscustomobject]@{
            id = $id
            parent_id = $parentId
            creation_date = $creationDate
            snapshot_start_time_ticks = $snapshotTicks
            start_time_ticks = $expectedTicks
            role = [string]$record.role
            anchor_id = $id
            depth = 0
            record = $record
        }
        $targets += $target
        $pending.Enqueue($target)
    }

    while ($pending.Count -gt 0) {
        $parent = $pending.Dequeue()
        foreach ($child in $snapshot) {
            try {
                $childParentProcessId = $child.ParentProcessId
                if ($null -eq $childParentProcessId) {
                    throw "Descendant CIM identity property was unavailable."
                }
                $childParentId = [int]$childParentProcessId
                if ($childParentId -ne [int]$parent.id) {
                    continue
                }
                $childProcessId = $child.ProcessId
                if ($null -eq $childProcessId) {
                    throw "Descendant CIM identity property was unavailable."
                }
                $childId = [int]$childProcessId
                $childCreationDate = [DateTime]$child.CreationDate
                $childExpectedTicks = [long]$childCreationDate.ToUniversalTime().Ticks
            } catch {
                $errors += "Unable to read descendant CIM identity: $($_.Exception.Message)"
                $blockedAnchorIds = @($blockedAnchorIds + [int]$parent.anchor_id | Select-Object -Unique)
                continue
            }
            if ($targets.id -contains $childId) {
                continue
            }
            $identity = Get-DeliveryProcessIdentityState `
                -Id $childId `
                -ExpectedStartTicks $childExpectedTicks `
                -ExpectedTickPrecision 10
            if ($identity.state -eq "exited") {
                continue
            }
            if ($identity.state -eq "unverifiable") {
                $errors += "Unable to read descendant identity for PID $($childId): $($identity.error)"
                $blockedAnchorIds = @($blockedAnchorIds + [int]$parent.anchor_id | Select-Object -Unique)
                continue
            }
            $childTicks = [long]$identity.start_time_ticks
            $target = [pscustomobject]@{
                id = $childId
                parent_id = $childParentId
                start_time_ticks = $childTicks
                snapshot_start_time_ticks = $childExpectedTicks
                role = "descendant"
                anchor_id = [int]$parent.anchor_id
                depth = [int]$parent.depth + 1
                record = $null
            }
            $targets += $target
            $pending.Enqueue($target)
        }
    }

    $waitTargets = @()
    foreach ($target in $targets | Sort-Object depth -Descending) {
        $id = [int]$target.id
        if ($blockedAnchorIds -contains [int]$target.anchor_id) {
            if ($id -eq [int]$target.anchor_id) {
                $survivors += [pscustomobject]@{ pid = $id; start_time_ticks = [long]$target.start_time_ticks; role = [string]$target.role }
            }
            continue
        }
        $identity = Get-DeliveryProcessIdentityState -Id $id -ExpectedStartTicks ([long]$target.start_time_ticks)
        if ($identity.state -eq "exited") {
            if ($null -ne $identity.start_time_ticks) {
                $errors += "Process identity mismatch for PID $id before termination; original instance already exited."
            }
            continue
        }
        if ($identity.state -eq "unverifiable") {
            $errors += "Unable to re-read process identity for PID $($id): $($identity.error)"
            $survivors += [pscustomobject]@{ pid = $id; start_time_ticks = [long]$target.start_time_ticks; role = [string]$target.role }
            continue
        }
        $waitTargets += $target
        try {
            Stop-Process -Id $id -Force -ErrorAction Stop
        } catch {
            $errors += "Unable to stop rollback PID $($id): $($_.Exception.Message)"
        }
    }

    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    $waitUnverifiable = @()
    do {
        $remaining = @()
        foreach ($target in $waitTargets) {
            $identity = Get-DeliveryProcessIdentityState -Id ([int]$target.id) -ExpectedStartTicks ([long]$target.start_time_ticks)
            if ($identity.state -eq "exited") {
                continue
            }
            if ($identity.state -eq "unverifiable") {
                $errors += "Unable to confirm rollback exit for PID $($target.id): $($identity.error)"
                $waitUnverifiable += $target
                continue
            }
            $remaining += $target
        }
        if ($waitUnverifiable.Count -gt 0) {
            break
        }
        if ($remaining.Count -eq 0) {
            break
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)

    if ($remaining.Count -gt 0 -and $waitUnverifiable.Count -eq 0) {
        $remainingIds = @($remaining | ForEach-Object { $_.id })
        $errors += "Timed out waiting for rollback PIDs to exit: $($remainingIds -join ', ')"
    }
    $remaining = @($remaining + $waitUnverifiable | Sort-Object id, start_time_ticks -Unique)
    if ($remaining.Count -gt 0) {
        $survivors += @($remaining | ForEach-Object { [pscustomobject]@{ pid = [int]$_.id; start_time_ticks = [long]$_.start_time_ticks; role = [string]$_.role } })
    }
    $survivors = @($survivors | Sort-Object pid, start_time_ticks -Unique)
    return [pscustomobject]@{
        success = ($errors.Count -eq 0 -and $survivors.Count -eq 0)
        survivor_ids = @($survivors | ForEach-Object { $_.pid })
        survivor_processes = $survivors
        errors = $errors
    }
    } catch {
        $errors += "Rollback internal failure: $($_.Exception.Message)"
        $fallback = @($ProcessRecords | ForEach-Object { [pscustomobject]@{ pid = [int]$_.id; start_time_ticks = [long]$_.start_time_ticks; role = [string]$_.role } } | Where-Object { $_.pid -gt 0 })
        return [pscustomobject]@{
            success = $false
            survivor_ids = @($fallback | ForEach-Object { $_.pid })
            survivor_processes = $fallback
            errors = $errors
        }
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

    try {
        $rollbackParams = @{
            ProcessRecords = $ProcessRecords
            ProjectRoot = $ProjectRoot
            TimeoutMilliseconds = $TimeoutMilliseconds
        }
        $rollback = Stop-StartedProcessTrees @rollbackParams
        $survivors = @($rollback.survivor_processes)
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
            foreach ($survivor in $survivors) {
                if ([string]$survivor.role -eq "api") {
                    $apiPid = [int]$survivor.pid
                } elseif ([string]$survivor.role -eq "web") {
                    $webPid = [int]$survivor.pid
                }
            }
            $recoveryState = @{
                project_root = $ProjectRoot
                api_pid = $apiPid
                web_pid = $webPid
                recovery_processes = $survivors
                created_at = $CreatedAt
            } | ConvertTo-Json -Depth 4
            try {
                $stateDir = Split-Path -Parent $ProcessStatePath
                New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
                [System.IO.File]::WriteAllText($ProcessStatePath, $recoveryState, [System.Text.UTF8Encoding]::new($false))
            } catch {
                $stateError = "Recovery state write failed: $($_.Exception.Message)"
            }
        }
        $parts = @("Delivery process startup failed: $OriginalError")
        if ($rollbackErrors.Count -gt 0) {
            $parts += "Rollback errors: $($rollbackErrors -join '; ')"
        }
        if ($survivors.Count -gt 0) {
            $parts += "Survivor PIDs: $(@($survivors | ForEach-Object { $_.pid }) -join ', ')"
            if (-not $stateError) {
                $parts += "Recovery state preserved: $ProcessStatePath"
            }
        }
        if ($stateError) {
            $parts += $stateError
        }
        return [pscustomobject]@{
            success = ($rollback.success -and -not $stateError)
            survivor_ids = @($survivors | ForEach-Object { $_.pid })
            survivor_processes = $survivors
            errors = @($rollbackErrors + @($stateError) | Where-Object { $_ })
            message = ($parts -join ". ")
        }
    } catch {
        $internalError = $_.Exception.Message
        $fallback = @($ProcessRecords | ForEach-Object { [pscustomobject]@{ pid = [int]$_.id; start_time_ticks = [long]$_.start_time_ticks; role = [string]$_.role } } | Where-Object { $_.pid -gt 0 })
        $stateError = $null
        try {
            $stateDir = Split-Path -Parent $ProcessStatePath
            New-Item -ItemType Directory -Path $stateDir -Force | Out-Null
            $recoveryState = @{ project_root = $ProjectRoot; api_pid = 0; web_pid = 0; recovery_processes = $fallback; created_at = $CreatedAt } | ConvertTo-Json -Depth 4
            [System.IO.File]::WriteAllText($ProcessStatePath, $recoveryState, [System.Text.UTF8Encoding]::new($false))
        } catch {
            $stateError = "Recovery state write failed: $($_.Exception.Message)"
        }
        $message = "Delivery process startup failed: $OriginalError. Rollback internal failure: $internalError"
        if ($fallback.Count -gt 0) {
            $message += ". Survivor PIDs: $(@($fallback | ForEach-Object { $_.pid }) -join ', ')"
        }
        if ($stateError) {
            $message += ". $stateError"
        }
        return [pscustomobject]@{
            success = $false
            survivor_ids = @($fallback | ForEach-Object { $_.pid })
            survivor_processes = $fallback
            errors = @("Rollback internal failure: $internalError", $stateError | Where-Object { $_ })
            message = $message
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
    processes = @(
        [pscustomobject]@{
            pid = $apiProcess.Id
            role = "api"
            start_time_ticks = [long]$apiProcessRecord.start_time_ticks
        }
        [pscustomobject]@{
            pid = $webProcess.Id
            role = "web"
            start_time_ticks = [long]$webProcessRecord.start_time_ticks
        }
    )
    created_at = $createdAt
} | ConvertTo-Json -Depth 4
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
    try {
        $rollback = Invoke-DeliveryStartupRollback @rollbackParams
        $rollbackDiagnostic = $rollback.message
    } catch {
        $rollbackInternalError = $_.Exception.Message
        $fallback = @($startedProcesses | ForEach-Object { [pscustomobject]@{ pid = [int]$_.id; start_time_ticks = [long]$_.start_time_ticks; role = [string]$_.role } })
        $rollbackDiagnostic = "Delivery process startup failed: $startupError. Rollback internal failure: $rollbackInternalError"
        try {
            $recoveryState = @{ project_root = $projectRoot; api_pid = 0; web_pid = 0; recovery_processes = $fallback; created_at = $createdAt } | ConvertTo-Json -Depth 4
            [System.IO.File]::WriteAllText($processStatePath, $recoveryState, [System.Text.UTF8Encoding]::new($false))
        } catch {
            $rollbackDiagnostic += ". Recovery state write failed: $($_.Exception.Message)"
        }
    }
    Stop-WithDiagnostic $rollbackDiagnostic
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
