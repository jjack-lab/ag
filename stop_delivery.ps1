$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$statePath = Join-Path $projectRoot "data\delivery-processes.json"

function Get-DescendantProcessIds {
    param([int[]]$RootIds)
    $all = @(Get-CimInstance Win32_Process)
    $pending = [System.Collections.Generic.Queue[int]]::new()
    $seen = [System.Collections.Generic.HashSet[int]]::new()
    foreach ($id in $RootIds) {
        $pending.Enqueue($id)
        [void]$seen.Add($id)
    }
    while ($pending.Count -gt 0) {
        $parent = $pending.Dequeue()
        foreach ($child in $all | Where-Object { $_.ParentProcessId -eq $parent }) {
            if ($seen.Add([int]$child.ProcessId)) {
                $pending.Enqueue([int]$child.ProcessId)
            }
        }
    }
    return @($seen)
}

function Wait-DeliveryProcessesExit {
    param(
        [int[]]$ProcessIds,
        [hashtable]$ExpectedStartTicks,
        [int]$TimeoutMilliseconds = 5000
    )

    if (-not $ProcessIds -or $ProcessIds.Count -eq 0) {
        return $true
    }
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    do {
        $remaining = @()
        foreach ($id in $ProcessIds) {
            $live = Get-Process -Id $id -ErrorAction SilentlyContinue
            if (-not $live) {
                continue
            }
            try {
                $ticks = [long]$live.StartTime.ToUniversalTime().Ticks
            } catch {
                return $false
            }
            if ($ExpectedStartTicks.ContainsKey([string]$id) -and $ticks -ne [long]$ExpectedStartTicks[[string]$id]) {
                continue
            }
            $remaining += $id
        }
        if ($remaining.Count -eq 0) {
            return $true
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)
    return $false
}

if (-not (Test-Path -LiteralPath $statePath -PathType Leaf)) {
    Write-Host "No delivery process state found."
    exit 0
}

$state = Get-Content -LiteralPath $statePath -Raw -Encoding UTF8 | ConvertFrom-Json
if ([string]$state.project_root -ne $projectRoot) {
    Write-Error "Process state belongs to another project; refusing to stop."
    exit 1
}

$createdAt = [DateTimeOffset]::Parse([string]$state.created_at).UtcDateTime.AddSeconds(-5)
$recoveryIdentityById = @{}
if ($state.PSObject.Properties.Name -contains "recovery_processes") {
    $rootIds = @()
    foreach ($identity in @($state.recovery_processes)) {
        $id = [int]$identity.pid
        if ($id -le 0) {
            continue
        }
        $rootIds += $id
        $recoveryIdentityById[[string]$id] = $identity
    }
} elseif ($state.PSObject.Properties.Name -contains "recovery_pids") {
    Write-Error "Recovery state lacks exact process identities; refusing to stop bare PIDs."
    exit 1
} else {
    $rootIds = @([int]$state.api_pid, [int]$state.web_pid)
}
$rootIds = @($rootIds | Where-Object { $_ -gt 0 } | Select-Object -Unique)
$ownedRootIds = @()
foreach ($id in $rootIds) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
    if (-not $process) {
        continue
    }
    try {
        $commandLine = [string]$process.CommandLine
        $creationDate = ([DateTime]$process.CreationDate).ToUniversalTime()
        if ($recoveryIdentityById.ContainsKey([string]$id)) {
            $live = Get-Process -Id $id -ErrorAction Stop
            $actualTicks = [long]$live.StartTime.ToUniversalTime().Ticks
            $expectedTicks = [long]$recoveryIdentityById[[string]$id].start_time_ticks
            if ($actualTicks -ne $expectedTicks) {
                Write-Error "PID $id no longer matches the recovery identity; refusing to stop."
                exit 1
            }
        }
    } catch {
        Write-Error "Unable to verify process identity for PID $($id); state was preserved: $($_.Exception.Message)"
        exit 1
    }
    if ($commandLine -notlike "*$projectRoot*" -or $creationDate -lt $createdAt) {
        Write-Error "PID $id is not owned by this delivery instance; refusing to stop."
        exit 1
    }
    $ownedRootIds += $id
}

$ids = Get-DescendantProcessIds -RootIds $ownedRootIds | Sort-Object -Descending
$waitIdentityById = @{}
foreach ($id in $ids) {
    $live = Get-Process -Id $id -ErrorAction SilentlyContinue
    if (-not $live) {
        continue
    }
    try {
        $waitIdentityById[[string]$id] = [long]$live.StartTime.ToUniversalTime().Ticks
    } catch {
        Write-Error "Unable to capture process identity for PID $($id); state was preserved: $($_.Exception.Message)"
        exit 1
    }
}
foreach ($id in $ids) {
    $live = Get-Process -Id $id -ErrorAction SilentlyContinue
    if (-not $live) {
        continue
    }
    try {
        $actualTicks = [long]$live.StartTime.ToUniversalTime().Ticks
    } catch {
        Write-Error "Unable to re-check process identity for PID $($id); state was preserved: $($_.Exception.Message)"
        exit 1
    }
    if ($actualTicks -ne [long]$waitIdentityById[[string]$id]) {
        continue
    }
    Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
}
if (-not (Wait-DeliveryProcessesExit -ProcessIds $ids -ExpectedStartTicks $waitIdentityById)) {
    Write-Error "Timed out waiting for delivery processes to exit; state was preserved: $statePath"
    exit 1
}
Remove-Item -LiteralPath $statePath -Force
Write-Host "Delivery services stopped."
