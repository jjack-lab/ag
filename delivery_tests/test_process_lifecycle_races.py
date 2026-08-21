import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _ps_quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def _extract_powershell_function(path, name):
    script = path.read_text(encoding="utf-8")
    start = script.index(f"function {name}")
    opening = script.index("{", start)
    depth = 0
    for index in range(opening, len(script)):
        if script[index] == "{":
            depth += 1
        elif script[index] == "}":
            depth -= 1
            if depth == 0:
                return script[start : index + 1]
    raise AssertionError(f"Unclosed PowerShell function: {name}")


def _run_powershell_harness(tmp_path, script):
    harness = tmp_path / "harness.ps1"
    harness.write_text(script, encoding="utf-8")
    return subprocess.run(
        ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_stop_script_waits_for_owned_controlled_process(tmp_path):
    project = tmp_path / "delivery-harness"
    data_dir = project / "data"
    data_dir.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "stop_delivery.ps1", project / "stop_delivery.ps1")
    sleeper = project / "owned-sleeper.ps1"
    sleeper.write_text("Start-Sleep -Seconds 60\n", encoding="utf-8")

    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-File",
            str(sleeper),
        ],
        creationflags=creation_flags,
    )
    try:
        state_path = data_dir / "delivery-processes.json"
        state = {
            "project_root": str(project),
            "api_pid": process.pid,
            "web_pid": process.pid,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        state_path.write_text(json.dumps(state), encoding="utf-8")

        harness = f"""
$ErrorActionPreference = "Stop"
$script:controlledPid = {process.pid}
$script:stopRequested = $false
$script:raceInjected = $false
function Get-Process {{
    [CmdletBinding()]
    param([int]$Id)
    $live = Microsoft.PowerShell.Management\\Get-Process -Id $Id -ErrorAction SilentlyContinue
    if ($Id -eq $script:controlledPid -and $script:stopRequested -and -not $script:raceInjected -and $live) {{
        $script:raceInjected = $true
        $proxy = [pscustomobject]@{{ Id = $Id }}
        $proxy | Add-Member -MemberType ScriptProperty -Name StartTime -Value {{
            Microsoft.PowerShell.Management\\Stop-Process -Id $script:controlledPid -Force -ErrorAction SilentlyContinue
            Microsoft.PowerShell.Management\\Wait-Process -Id $script:controlledPid -Timeout 5 -ErrorAction SilentlyContinue
            throw "controlled stop exit race"
        }}
        return $proxy
    }}
    return $live
}}
function Stop-Process {{
    [CmdletBinding()]
    param([int]$Id, [switch]$Force)
    if ($Id -eq $script:controlledPid) {{
        $script:stopRequested = $true
        return
    }}
    Microsoft.PowerShell.Management\\Stop-Process -Id $Id -Force:$Force -ErrorAction SilentlyContinue
}}
. {_ps_quote(project / "stop_delivery.ps1")}
[pscustomobject]@{{
    race_injected = $script:raceInjected
    state_exists = Test-Path -LiteralPath {_ps_quote(state_path)}
}} | ConvertTo-Json -Compress
"""
        result = _run_powershell_harness(project, harness)
        assert result.returncode == 0, result.stdout + result.stderr
        payload = json.loads(result.stdout.strip().splitlines()[-1])
        assert payload["race_injected"] is True
        assert payload["state_exists"] is False
        process.wait(timeout=2)
        assert process.poll() is not None
        assert not state_path.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

def test_startup_rollback_reports_survivor_identity_mismatch_and_preserves_state(tmp_path):
    state_path = tmp_path / "delivery-processes.json"
    state_path.write_text("partial", encoding="utf-8")
    start_script = PROJECT_ROOT / "start_delivery.ps1"
    rollback_functions = "\n".join(
        _extract_powershell_function(start_script, name)
        for name in ("Get-DeliveryProcessIdentityState", "Stop-StartedProcessTrees", "Invoke-DeliveryStartupRollback")
    )
    harness = f"""
$ErrorActionPreference = "Stop"
{rollback_functions}
$script:stopCalls = 0
$script:projectRoot = {_ps_quote(tmp_path)}
$script:expectedStart = [DateTime]::UtcNow
function Get-CimInstance {{
    [CmdletBinding()]
    param([string]$ClassName)
    @(
        [pscustomobject]@{{
            ProcessId = 4242
            ParentProcessId = 1
            CommandLine = "$script:projectRoot\\unrelated.exe"
            CreationDate = $script:expectedStart.AddMinutes(1)
        }}
        [pscustomobject]@{{
            ProcessId = 4343
            ParentProcessId = 1
            CommandLine = "$script:projectRoot\\owned.exe"
            CreationDate = $script:expectedStart
        }}
    )
}}
function Get-Process {{
    [CmdletBinding()]
    param([int]$Id)
    $startTime = $script:expectedStart
    if ($Id -eq 4242) {{
        $startTime = $script:expectedStart.AddMinutes(1)
    }}
    [pscustomobject]@{{
        Id = $Id
        StartTime = $startTime
    }}
}}
function Stop-Process {{
    [CmdletBinding()]
    param([int]$Id, [switch]$Force)
    $script:stopCalls++
}}
function Start-Sleep {{ param([int]$Milliseconds) }}
$record = [pscustomobject]@{{
    id = 4242
    role = "api"
    start_time_ticks = $script:expectedStart.Ticks
    process = $null
}}
$stubbornRecord = [pscustomobject]@{{
    id = 4343
    role = "web"
    start_time_ticks = $script:expectedStart.Ticks
    process = $null
}}
$params = @{{
    OriginalError = "web start exploded"
    ProcessRecords = @($record, $stubbornRecord)
    ProjectRoot = $script:projectRoot
    ProcessStatePath = {_ps_quote(state_path)}
    CreatedAt = [DateTime]::UtcNow.ToString("o")
    StateWriteAttempted = $true
    TimeoutMilliseconds = 20
}}
$result = Invoke-DeliveryStartupRollback @params
$state = Get-Content -LiteralPath {_ps_quote(state_path)} -Raw -Encoding UTF8 | ConvertFrom-Json
[pscustomobject]@{{
    message = $result.message
    success = $result.success
    stop_calls = $script:stopCalls
    state_exists = Test-Path -LiteralPath {_ps_quote(state_path)}
    api_pid = $state.api_pid
    web_pid = $state.web_pid
    recovery_processes = @($state.recovery_processes)
}} | ConvertTo-Json -Compress
"""
    result = _run_powershell_harness(tmp_path, harness)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["success"] is False
    assert payload["stop_calls"] == 1
    assert payload["state_exists"] is True
    assert payload["api_pid"] == 0
    assert payload["web_pid"] == 4343
    recovery_ids = [item["pid"] for item in payload["recovery_processes"]]
    assert 4242 not in recovery_ids
    assert 4343 in recovery_ids
    assert "web start exploded" in payload["message"]
    assert "identity" in payload["message"].lower()
    assert "timed out" in payload["message"].lower()
    assert "4242" in payload["message"]
    assert "4343" in payload["message"]

def test_startup_rollback_stops_owned_controlled_process(tmp_path):
    sleeper = tmp_path / "rollback-sleeper.ps1"
    sleeper.write_text("Start-Sleep -Seconds 60\n", encoding="utf-8")
    start_script = PROJECT_ROOT / "start_delivery.ps1"
    rollback_function = "\n".join(
        _extract_powershell_function(start_script, name)
        for name in ("Get-DeliveryProcessIdentityState", "Stop-StartedProcessTrees")
    )
    harness = f"""
$ErrorActionPreference = "Stop"
{rollback_function}
$process = Start-Process powershell.exe -ArgumentList @("-NoProfile", "-File", {_ps_quote(sleeper)}) -WindowStyle Hidden -PassThru
$script:controlledPid = $process.Id
$script:stopRequested = $false
$script:raceInjected = $false
function Get-Process {{
    [CmdletBinding()]
    param([int]$Id)
    $live = Microsoft.PowerShell.Management\\Get-Process -Id $Id -ErrorAction SilentlyContinue
    if ($Id -eq $script:controlledPid -and $script:stopRequested -and -not $script:raceInjected -and $live) {{
        $script:raceInjected = $true
        $proxy = [pscustomobject]@{{ Id = $Id }}
        $proxy | Add-Member -MemberType ScriptProperty -Name StartTime -Value {{
            Microsoft.PowerShell.Management\\Stop-Process -Id $script:controlledPid -Force -ErrorAction SilentlyContinue
            Microsoft.PowerShell.Management\\Wait-Process -Id $script:controlledPid -Timeout 5 -ErrorAction SilentlyContinue
            throw "controlled rollback exit race"
        }}
        return $proxy
    }}
    return $live
}}
function Stop-Process {{
    [CmdletBinding()]
    param([int]$Id, [switch]$Force)
    if ($Id -eq $script:controlledPid) {{
        $script:stopRequested = $true
        return
    }}
    Microsoft.PowerShell.Management\\Stop-Process -Id $Id -Force:$Force -ErrorAction SilentlyContinue
}}
try {{
    $record = [pscustomobject]@{{
        id = $process.Id
        role = "api"
        start_time_ticks = $process.StartTime.ToUniversalTime().Ticks
        process = $process
    }}
    $result = Stop-StartedProcessTrees -ProcessRecords @($record) -ProjectRoot {_ps_quote(tmp_path)} -TimeoutMilliseconds 5000
    $process.Refresh()
    [pscustomobject]@{{
        success = $result.success
        survivors = @($result.survivor_ids)
        errors = @($result.errors)
        has_exited = $process.HasExited
        race_injected = $script:raceInjected
    }} | ConvertTo-Json -Compress
}} finally {{
    $process.Refresh()
    if (-not $process.HasExited) {{
        Microsoft.PowerShell.Management\\Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }}
}}
"""
    result = _run_powershell_harness(tmp_path, harness)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["race_injected"] is True
    assert payload["success"] is True
    assert payload["survivors"] == []
    assert payload["errors"] == []
    assert payload["has_exited"] is True

def test_stop_recovery_state_ignores_reused_pid_then_stops_exact_survivor(tmp_path):
    project = tmp_path / "recovery-stop-harness"
    data_dir = project / "data"
    data_dir.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "stop_delivery.ps1", project / "stop_delivery.ps1")
    sleeper = project / "recovery-sleeper.ps1"
    sleeper.write_text("Start-Sleep -Seconds 60\n", encoding="utf-8")
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    process = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-File", str(sleeper)],
        creationflags=creation_flags,
    )
    state_path = data_dir / "delivery-processes.json"
    try:
        ticks_result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                f"(Get-Process -Id {process.pid}).StartTime.ToUniversalTime().Ticks",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert ticks_result.returncode == 0, ticks_result.stdout + ticks_result.stderr
        exact_ticks = int(ticks_result.stdout.strip())
        state = {
            "project_root": str(project),
            "api_pid": process.pid,
            "web_pid": 0,
            "recovery_processes": [
                {"pid": process.pid, "start_time_ticks": exact_ticks - 1, "role": "api"}
            ],
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        state_path.write_text(json.dumps(state), encoding="utf-8")

        mismatch = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(project / "stop_delivery.ps1"),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert mismatch.returncode == 0, mismatch.stdout + mismatch.stderr
        assert process.poll() is None
        assert not state_path.exists()

        state["recovery_processes"][0]["start_time_ticks"] = exact_ticks
        state_path.write_text(json.dumps(state), encoding="utf-8")
        exact = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(project / "stop_delivery.ps1"),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert exact.returncode == 0, exact.stdout + exact.stderr
        process.wait(timeout=2)
        assert process.poll() is not None
        assert not state_path.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)

def test_startup_rollback_preserves_original_error_when_identity_property_races(tmp_path):
    state_path = tmp_path / "race-delivery-processes.json"
    start_script = PROJECT_ROOT / "start_delivery.ps1"
    rollback_functions = "\n".join(
        _extract_powershell_function(start_script, name)
        for name in ("Get-DeliveryProcessIdentityState", "Stop-StartedProcessTrees", "Invoke-DeliveryStartupRollback")
    )
    harness = f"""
$ErrorActionPreference = "Stop"
{rollback_functions}
$script:projectRoot = {_ps_quote(tmp_path)}
function Get-CimInstance {{
    [CmdletBinding()]
    param([string]$ClassName)
    [pscustomobject]@{{
        ProcessId = 5151
        ParentProcessId = 1
        CommandLine = "$script:projectRoot\\owned.exe"
        CreationDate = [DateTime]::UtcNow
    }}
}}
function Get-Process {{
    [CmdletBinding()]
    param([int]$Id)
    $value = [pscustomobject]@{{ Id = $Id }}
    $value | Add-Member -MemberType ScriptProperty -Name StartTime -Value {{ throw "process exited during StartTime read" }}
    return $value
}}
function Stop-Process {{
    [CmdletBinding()]
    param([int]$Id, [switch]$Force)
    throw "must not stop without identity"
}}
$record = [pscustomobject]@{{
    id = 5151
    role = "api"
    start_time_ticks = [DateTime]::UtcNow.Ticks
    process = $null
}}
$params = @{{
    OriginalError = "state write exploded"
    ProcessRecords = @($record)
    ProjectRoot = $script:projectRoot
    ProcessStatePath = {_ps_quote(state_path)}
    CreatedAt = [DateTime]::UtcNow.ToString("o")
    StateWriteAttempted = $true
    TimeoutMilliseconds = 20
}}
$result = Invoke-DeliveryStartupRollback @params
$state = Get-Content -LiteralPath {_ps_quote(state_path)} -Raw -Encoding UTF8 | ConvertFrom-Json
[pscustomobject]@{{
    success = $result.success
    message = $result.message
    recovery_ids = @($state.recovery_processes | ForEach-Object {{ $_.pid }})
}} | ConvertTo-Json -Compress
"""
    result = _run_powershell_harness(tmp_path, harness)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["success"] is False
    assert 5151 in payload["recovery_ids"]
    assert "state write exploded" in payload["message"]
    assert "Unable to read process identity" in payload["message"]

def test_stop_ignores_reused_recovery_pid_after_exact_verification(tmp_path):
    expected_ticks = 638000000000000000
    project = tmp_path / "stop-reuse-harness"
    data_dir = project / "data"
    data_dir.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "stop_delivery.ps1", project / "stop_delivery.ps1")
    state_path = data_dir / "delivery-processes.json"
    state_path.write_text(
        json.dumps(
            {
                "project_root": str(project),
                "api_pid": 6161,
                "web_pid": 0,
                "recovery_processes": [
                    {"pid": 6161, "start_time_ticks": expected_ticks, "role": "api"}
                ],
                "created_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    harness = f"""
$ErrorActionPreference = "Stop"
$script:getCalls = 0
$script:stopCalls = 0
$script:projectRoot = {_ps_quote(project)}
$script:expectedStart = [DateTime]::new({expected_ticks}, [DateTimeKind]::Utc)
function Get-CimInstance {{
    [CmdletBinding()]
    param([string]$ClassName, [string]$Filter)
    [pscustomobject]@{{
        ProcessId = 6161
        ParentProcessId = 1
        CommandLine = "$script:projectRoot\\owned.exe"
        CreationDate = $script:expectedStart
    }}
}}
function Get-Process {{
    [CmdletBinding()]
    param([int]$Id)
    $script:getCalls++
    if ($script:getCalls -eq 1) {{
        return [pscustomobject]@{{ Id = $Id; StartTime = $script:expectedStart }}
    }}
    [pscustomobject]@{{
        Id = $Id
        StartTime = $script:expectedStart.AddMinutes(1)
    }}
}}
function Stop-Process {{
    [CmdletBinding()]
    param([int]$Id, [switch]$Force)
    $script:stopCalls++
}}
. {_ps_quote(project / "stop_delivery.ps1")}
[pscustomobject]@{{
    stop_calls = $script:stopCalls
    state_exists = Test-Path -LiteralPath {_ps_quote(state_path)}
}} | ConvertTo-Json -Compress
"""
    result = _run_powershell_harness(tmp_path, harness)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["stop_calls"] == 0
    assert payload["state_exists"] is False

def test_startup_rollback_treats_descendant_identity_retry_reuse_as_exited(tmp_path):
    state_path = tmp_path / "descendant-race-state.json"
    start_script = PROJECT_ROOT / "start_delivery.ps1"
    rollback_functions = "\n".join(
        _extract_powershell_function(start_script, name)
        for name in ("Get-DeliveryProcessIdentityState", "Stop-StartedProcessTrees", "Invoke-DeliveryStartupRollback")
    )
    harness = f"""
$ErrorActionPreference = "Stop"
{rollback_functions}
$script:rootAlive = $true
$script:stopped = @()
$script:projectRoot = {_ps_quote(tmp_path)}
$script:rootStart = [DateTime]::UtcNow
$script:childGetCalls = 0
function Get-CimInstance {{
    [CmdletBinding()]
    param([string]$ClassName)
    @(
        [pscustomobject]@{{
            ProcessId = 7001
            ParentProcessId = 1
            CommandLine = "$script:projectRoot\\api.exe"
            CreationDate = $script:rootStart
        }}
        [pscustomobject]@{{
            ProcessId = 7002
            ParentProcessId = 7001
            CommandLine = "$script:projectRoot\\child.exe"
            CreationDate = $script:rootStart
        }}
    )
}}
function Get-Process {{
    [CmdletBinding()]
    param([int]$Id)
    if ($Id -eq 7001) {{
        if (-not $script:rootAlive) {{ return $null }}
        return [pscustomobject]@{{ Id = $Id; StartTime = $script:rootStart }}
    }}
    $script:childGetCalls++
    if ($script:childGetCalls -gt 1) {{
        return [pscustomobject]@{{ Id = $Id; StartTime = $script:rootStart.AddMinutes(1) }}
    }}
    $value = [pscustomobject]@{{ Id = $Id }}
    $value | Add-Member -MemberType ScriptProperty -Name StartTime -Value {{ throw "descendant identity race" }}
    return $value
}}
function Stop-Process {{
    [CmdletBinding()]
    param([int]$Id, [switch]$Force)
    $script:stopped += $Id
    if ($Id -eq 7001) {{ $script:rootAlive = $false }}
}}
$record = [pscustomobject]@{{
    id = 7001
    role = "api"
    start_time_ticks = $script:rootStart.Ticks
    process = $null
}}
$params = @{{
    OriginalError = "web start exploded"
    ProcessRecords = @($record)
    ProjectRoot = $script:projectRoot
    ProcessStatePath = {_ps_quote(state_path)}
    CreatedAt = $script:rootStart.ToString("o")
    StateWriteAttempted = $true
    TimeoutMilliseconds = 20
}}
$result = Invoke-DeliveryStartupRollback @params
[pscustomobject]@{{
    success = $result.success
    message = $result.message
    root_alive = $script:rootAlive
    stopped = @($script:stopped)
    state_exists = Test-Path -LiteralPath {_ps_quote(state_path)}
}} | ConvertTo-Json -Compress
"""
    result = _run_powershell_harness(tmp_path, harness)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["success"] is True
    assert payload["root_alive"] is False
    assert 7001 in payload["stopped"]
    assert 7002 not in payload["stopped"]
    assert payload["state_exists"] is False
    assert "web start exploded" in payload["message"]

@pytest.mark.parametrize("throwing_property", ["ProcessId", "ParentProcessId"])
def test_startup_rollback_keeps_root_anchor_when_descendant_cim_identity_throws(tmp_path, throwing_property):
    state_path = tmp_path / "descendant-cim-race-state.json"
    start_script = PROJECT_ROOT / "start_delivery.ps1"
    rollback_functions = "\n".join(
        _extract_powershell_function(start_script, name)
        for name in ("Get-DeliveryProcessIdentityState", "Stop-StartedProcessTrees", "Invoke-DeliveryStartupRollback")
    )
    child_identity = (
        "ParentProcessId = 7101"
        if throwing_property == "ProcessId"
        else "ProcessId = 7102"
    )
    harness = f"""
$ErrorActionPreference = "Stop"
{rollback_functions}
$script:rootAlive = $true
$script:stopped = @()
$script:projectRoot = {_ps_quote(tmp_path)}
$script:rootStart = [DateTime]::UtcNow
function Get-CimInstance {{
    [CmdletBinding()]
    param([string]$ClassName)
    $root = [pscustomobject]@{{
        ProcessId = 7101
        ParentProcessId = 1
        CommandLine = "$script:projectRoot\\api.exe"
        CreationDate = $script:rootStart
    }}
    $child = [pscustomobject]@{{
        {child_identity}
        CommandLine = "$script:projectRoot\\child.exe"
        CreationDate = $script:rootStart
    }}
    $child | Add-Member -MemberType ScriptProperty -Name {_ps_quote(throwing_property)} -Value {{ throw "descendant CIM identity race" }}
    @($root, $child)
}}
function Get-Process {{
    [CmdletBinding()]
    param([int]$Id)
    if ($Id -eq 7101 -and $script:rootAlive) {{
        return [pscustomobject]@{{ Id = $Id; StartTime = $script:rootStart }}
    }}
    return $null
}}
function Stop-Process {{
    [CmdletBinding()]
    param([int]$Id, [switch]$Force)
    $script:stopped += $Id
    if ($Id -eq 7101) {{ $script:rootAlive = $false }}
}}
$record = [pscustomobject]@{{
    id = 7101
    role = "api"
    start_time_ticks = $script:rootStart.Ticks
    process = $null
}}
$params = @{{
    OriginalError = "web start exploded"
    ProcessRecords = @($record)
    ProjectRoot = $script:projectRoot
    ProcessStatePath = {_ps_quote(state_path)}
    CreatedAt = $script:rootStart.ToString("o")
    StateWriteAttempted = $true
    TimeoutMilliseconds = 20
}}
$result = Invoke-DeliveryStartupRollback @params
$state = Get-Content -LiteralPath {_ps_quote(state_path)} -Raw -Encoding UTF8 | ConvertFrom-Json
$recovery = @($state.recovery_processes)[0]
[pscustomobject]@{{
    success = $result.success
    message = $result.message
    root_alive = $script:rootAlive
    stopped = @($script:stopped)
    recovery_pid = $recovery.pid
    recovery_ticks = $recovery.start_time_ticks
    expected_ticks = $script:rootStart.Ticks
    recovery_role = $recovery.role
}} | ConvertTo-Json -Compress
"""
    result = _run_powershell_harness(tmp_path, harness)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["success"] is False
    assert payload["root_alive"] is True
    assert 7101 not in payload["stopped"]
    assert payload["recovery_pid"] == 7101
    assert payload["recovery_ticks"] == payload["expected_ticks"]
    assert payload["recovery_role"] == "api"
    assert "web start exploded" in payload["message"]
    assert "descendant CIM identity" in payload["message"]


def test_startup_rollback_ignores_descendant_reused_after_cim_snapshot(tmp_path):
    start_script = PROJECT_ROOT / "start_delivery.ps1"
    rollback_functions = "\n".join(
        _extract_powershell_function(start_script, name)
        for name in ("Get-DeliveryProcessIdentityState", "Stop-StartedProcessTrees")
    )
    harness = f"""
$ErrorActionPreference = "Stop"
{rollback_functions}
$script:rootStart = [DateTime]::UtcNow
$script:childSnapshotStart = $script:rootStart.AddMinutes(-2)
$script:childReplacementStart = $script:rootStart.AddMinutes(-1)
$script:rootAlive = $true
$script:childAlive = $true
$script:stopped = @()
$script:projectRoot = {_ps_quote(tmp_path)}
function Get-CimInstance {{
    [CmdletBinding()]
    param([string]$ClassName)
    @(
        [pscustomobject]@{{
            ProcessId = 8201
            ParentProcessId = 1
            CommandLine = "$script:projectRoot\\api.exe"
            CreationDate = $script:rootStart
        }}
        [pscustomobject]@{{
            ProcessId = 8202
            ParentProcessId = 8201
            CommandLine = "$script:projectRoot\\child.exe"
            CreationDate = $script:childSnapshotStart
        }}
    )
}}
function Get-Process {{
    [CmdletBinding()]
    param([int]$Id)
    if ($Id -eq 8201) {{
        if (-not $script:rootAlive) {{ return $null }}
        return [pscustomobject]@{{ Id = $Id; StartTime = $script:rootStart }}
    }}
    if (-not $script:childAlive) {{ return $null }}
    return [pscustomobject]@{{ Id = $Id; StartTime = $script:childReplacementStart }}
}}
function Stop-Process {{
    [CmdletBinding()]
    param([int]$Id, [switch]$Force)
    $script:stopped += $Id
    if ($Id -eq 8201) {{ $script:rootAlive = $false }}
    if ($Id -eq 8202) {{ $script:childAlive = $false }}
}}
$record = [pscustomobject]@{{
    id = 8201
    role = "api"
    start_time_ticks = $script:rootStart.Ticks
    process = $null
}}
$result = Stop-StartedProcessTrees -ProcessRecords @($record) -ProjectRoot $script:projectRoot -TimeoutMilliseconds 20
[pscustomobject]@{{
    success = $result.success
    stopped = @($script:stopped)
    survivors = @($result.survivor_ids)
}} | ConvertTo-Json -Compress
"""
    result = _run_powershell_harness(tmp_path, harness)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["success"] is True
    assert 8201 in payload["stopped"]
    assert 8202 not in payload["stopped"]
    assert 8202 not in payload["survivors"]


@pytest.mark.parametrize("reused_role", ["root", "descendant"])
def test_stop_legacy_state_ignores_pid_reused_after_single_cim_snapshot(tmp_path, reused_role):
    project = tmp_path / f"stop-cim-reuse-{reused_role}"
    data_dir = project / "data"
    data_dir.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "stop_delivery.ps1", project / "stop_delivery.ps1")
    state_path = data_dir / "delivery-processes.json"
    state_path.write_text(
        json.dumps(
            {
                "project_root": str(project),
                "api_pid": 8301,
                "web_pid": 0,
                "created_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    reused_pid = 8301 if reused_role == "root" else 8302
    harness = f"""
$ErrorActionPreference = "Stop"
$script:rootSnapshotStart = [DateTime]::new(638000000000000000, [DateTimeKind]::Utc)
$script:childSnapshotStart = $script:rootSnapshotStart.AddSeconds(1)
$script:replacementStart = $script:rootSnapshotStart.AddMinutes(1)
$script:cimCalls = 0
$script:stopped = @()
$script:alive = @{{ "8301" = $true; "8302" = $true }}
$script:projectRoot = {_ps_quote(project)}
$script:reusedPid = {reused_pid}
function Get-CimInstance {{
    [CmdletBinding()]
    param([string]$ClassName, [string]$Filter)
    $script:cimCalls++
    $all = @(
        [pscustomobject]@{{
            ProcessId = 8301
            ParentProcessId = 1
            CommandLine = "$script:projectRoot\\api.exe"
            CreationDate = $script:rootSnapshotStart
        }}
        [pscustomobject]@{{
            ProcessId = 8302
            ParentProcessId = 8301
            CommandLine = "$script:projectRoot\\child.exe"
            CreationDate = $script:childSnapshotStart
        }}
    )
    if ($Filter) {{
        return $all | Where-Object {{ [int]$_.ProcessId -eq 8301 }}
    }}
    return $all
}}
function Get-Process {{
    [CmdletBinding()]
    param([int]$Id)
    if (-not $script:alive[[string]$Id]) {{ return $null }}
    $startTime = if ($Id -eq $script:reusedPid) {{
        $script:replacementStart
    }} elseif ($Id -eq 8301) {{
        $script:rootSnapshotStart
    }} else {{
        $script:childSnapshotStart
    }}
    [pscustomobject]@{{ Id = $Id; StartTime = $startTime }}
}}
function Stop-Process {{
    [CmdletBinding()]
    param([int]$Id, [switch]$Force)
    $script:stopped += $Id
    $script:alive[[string]$Id] = $false
}}
. {_ps_quote(project / "stop_delivery.ps1")}
[pscustomobject]@{{
    cim_calls = $script:cimCalls
    stopped = @($script:stopped)
    state_exists = Test-Path -LiteralPath {_ps_quote(state_path)}
}} | ConvertTo-Json -Compress
"""
    result = _run_powershell_harness(tmp_path, harness)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert reused_pid not in payload["stopped"]
    assert payload["cim_calls"] == 1
    assert payload["state_exists"] is False


def test_stop_legacy_root_uses_exact_identity_after_snapshot_match(tmp_path):
    project = tmp_path / "stop-cim-exact-root"
    data_dir = project / "data"
    data_dir.mkdir(parents=True)
    shutil.copy2(PROJECT_ROOT / "stop_delivery.ps1", project / "stop_delivery.ps1")
    state_path = data_dir / "delivery-processes.json"
    state_path.write_text(
        json.dumps(
            {
                "project_root": str(project),
                "api_pid": 8401,
                "web_pid": 0,
                "created_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    harness = f"""
$ErrorActionPreference = "Stop"
$script:snapshotStart = [DateTime]::new(638000000000000000, [DateTimeKind]::Utc)
$script:firstLiveStart = $script:snapshotStart.AddTicks(5)
$script:replacementStart = $script:snapshotStart.AddTicks(6)
$script:getCalls = 0
$script:cimCalls = 0
$script:stopCalls = 0
$script:projectRoot = {_ps_quote(project)}
function Get-CimInstance {{
    [CmdletBinding()]
    param([string]$ClassName, [string]$Filter)
    $script:cimCalls++
    [pscustomobject]@{{
        ProcessId = 8401
        ParentProcessId = 1
        CommandLine = "$script:projectRoot\\api.exe"
        CreationDate = $script:snapshotStart
    }}
}}
function Get-Process {{
    [CmdletBinding()]
    param([int]$Id)
    $script:getCalls++
    $startTime = if ($script:getCalls -eq 1) {{
        $script:firstLiveStart
    }} else {{
        $script:replacementStart
    }}
    [pscustomobject]@{{ Id = $Id; StartTime = $startTime }}
}}
function Stop-Process {{
    [CmdletBinding()]
    param([int]$Id, [switch]$Force)
    $script:stopCalls++
}}
. {_ps_quote(project / "stop_delivery.ps1")}
[pscustomobject]@{{
    cim_calls = $script:cimCalls
    stop_calls = $script:stopCalls
    state_exists = Test-Path -LiteralPath {_ps_quote(state_path)}
}} | ConvertTo-Json -Compress
"""
    result = _run_powershell_harness(tmp_path, harness)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["stop_calls"] == 0
    assert payload["cim_calls"] == 1
    assert payload["state_exists"] is False
