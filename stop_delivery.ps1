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
        [int]$TimeoutMilliseconds = 5000
    )

    if (-not $ProcessIds -or $ProcessIds.Count -eq 0) {
        return $true
    }
    $deadline = [DateTime]::UtcNow.AddMilliseconds($TimeoutMilliseconds)
    do {
        $remaining = @($ProcessIds | Where-Object { Get-Process -Id $_ -ErrorAction SilentlyContinue })
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
$rootIds = @([int]$state.api_pid, [int]$state.web_pid)
if ($state.PSObject.Properties.Name -contains "recovery_pids") {
    $rootIds += @($state.recovery_pids | ForEach-Object { [int]$_ })
}
$rootIds = @($rootIds | Where-Object { $_ -gt 0 } | Select-Object -Unique)
$ownedRootIds = @()
foreach ($id in $rootIds) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId=$id" -ErrorAction SilentlyContinue
    if (-not $process) {
        continue
    }
    $commandLine = [string]$process.CommandLine
    $creationDate = ([DateTime]$process.CreationDate).ToUniversalTime()
    if ($commandLine -notlike "*$projectRoot*" -or $creationDate -lt $createdAt) {
        Write-Error "PID $id is not owned by this delivery instance; refusing to stop."
        exit 1
    }
    $ownedRootIds += $id
}

$ids = Get-DescendantProcessIds -RootIds $ownedRootIds | Sort-Object -Descending
foreach ($id in $ids) {
    if (Get-Process -Id $id -ErrorAction SilentlyContinue) {
        Stop-Process -Id $id -Force -ErrorAction SilentlyContinue
    }
}
if (-not (Wait-DeliveryProcessesExit -ProcessIds $ids)) {
    Write-Error "Timed out waiting for delivery processes to exit; state was preserved: $statePath"
    exit 1
}
Remove-Item -LiteralPath $statePath -Force
Write-Host "Delivery services stopped."
