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
        Stop-Process -Id $id -Force
    }
}
Remove-Item -LiteralPath $statePath -Force
Write-Host "Delivery services stopped."
