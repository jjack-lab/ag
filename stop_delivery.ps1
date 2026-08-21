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

function Get-DeliveryProcessIdentityState {
    param(
        [int]$Id,
        [object]$ExpectedStartTicks = $null
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
        if ($hasExpectedIdentity -and $ticks -ne [long]$ExpectedStartTicks) {
            return [pscustomobject]@{ state = "exited"; start_time_ticks = $ticks; error = $null }
        }
        return [pscustomobject]@{ state = "same_identity_alive"; start_time_ticks = $ticks; error = $null }
    }
    return [pscustomobject]@{ state = "unverifiable"; start_time_ticks = $null; error = $lastError }
}

function Wait-DeliveryProcessesExit {
    param(
        [int[]]$ProcessIds,
        [hashtable]$ExpectedStartTicks,
        [int]$TimeoutMilliseconds = 5000
    )

    if (-not $ProcessIds -or $ProcessIds.Count -eq 0) {
        return [pscustomobject]@{ success = $true; unverifiable_ids = @(); remaining_ids = @() }
    }
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    do {
        $remaining = @()
        foreach ($id in $ProcessIds) {
            if (-not $ExpectedStartTicks.ContainsKey([string]$id)) {
                continue
            }
            $identity = Get-DeliveryProcessIdentityState -Id $id -ExpectedStartTicks ([long]$ExpectedStartTicks[[string]$id])
            if ($identity.state -eq "exited") {
                continue
            }
            if ($identity.state -eq "unverifiable") {
                return [pscustomobject]@{
                    success = $false
                    unverifiable_ids = @($id)
                    remaining_ids = @()
                    error = $identity.error
                }
            }
            $remaining += $id
        }
        if ($remaining.Count -eq 0) {
            return [pscustomobject]@{ success = $true; unverifiable_ids = @(); remaining_ids = @() }
        }
        Start-Sleep -Milliseconds 100
    } while ([DateTime]::UtcNow -lt $deadline)
    return [pscustomobject]@{ success = $false; unverifiable_ids = @(); remaining_ids = $remaining }
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
    } catch {
        Write-Error "Unable to verify process identity for PID $($id); state was preserved: $($_.Exception.Message)"
        exit 1
    }
    if ($recoveryIdentityById.ContainsKey([string]$id)) {
        $expectedTicks = [long]$recoveryIdentityById[[string]$id].start_time_ticks
        $identity = Get-DeliveryProcessIdentityState -Id $id -ExpectedStartTicks $expectedTicks
        if ($identity.state -eq "exited") {
            continue
        }
        if ($identity.state -eq "unverifiable") {
            Write-Error "Unable to verify process identity for PID $($id); state was preserved: $($identity.error)"
            exit 1
        }
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
    if ($recoveryIdentityById.ContainsKey([string]$id)) {
        $expectedTicks = [long]$recoveryIdentityById[[string]$id].start_time_ticks
        $identity = Get-DeliveryProcessIdentityState -Id $id -ExpectedStartTicks $expectedTicks
    } else {
        $identity = Get-DeliveryProcessIdentityState -Id $id
    }
    if ($identity.state -eq "exited") {
        continue
    }
    if ($identity.state -eq "unverifiable") {
        Write-Error "Unable to capture process identity for PID $($id); state was preserved: $($identity.error)"
        exit 1
    }
    $waitIdentityById[[string]$id] = [long]$identity.start_time_ticks
}
foreach ($id in $ids) {
    if (-not $waitIdentityById.ContainsKey([string]$id)) {
        continue
    }
    $identity = Get-DeliveryProcessIdentityState -Id $id -ExpectedStartTicks ([long]$waitIdentityById[[string]$id])
    if ($identity.state -eq "exited") {
        continue
    }
    if ($identity.state -eq "unverifiable") {
        Write-Error "Unable to re-check process identity for PID $($id); state was preserved: $($identity.error)"
        exit 1
    }
    Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
}
$waitResult = Wait-DeliveryProcessesExit -ProcessIds $ids -ExpectedStartTicks $waitIdentityById
if (-not $waitResult.success) {
    if (@($waitResult.unverifiable_ids).Count -gt 0) {
        Write-Error "Unable to verify delivery process exit for PIDs $(@($waitResult.unverifiable_ids) -join ', '); state was preserved: $statePath ($($waitResult.error))"
        exit 1
    }
    Write-Error "Timed out waiting for delivery processes to exit; state was preserved: $statePath"
    exit 1
}
Remove-Item -LiteralPath $statePath -Force
Write-Host "Delivery services stopped."
