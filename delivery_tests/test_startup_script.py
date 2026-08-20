import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path


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


def test_runtime_docs_name_logs_and_nonfatal_behavior_preflight():
    required_phrases = (
        "data/logs",
        "api.stdout.log",
        "api.stderr.log",
        "web.stdout.log",
        "web.stderr.log",
        "进入服务启动阶段",
        "未通过就绪检查",
        "最后 40 行",
        "停止服务不会删除日志",
        "检测模型缺失会阻断",
        "`behavior` 状态显示 `unavailable`",
        "不阻断",
        "研究演示",
        "不是兽医疾病诊断",
    )

    for filename in ("README.md", "README_DELIVERY.md"):
        documentation = (PROJECT_ROOT / filename).read_text(encoding="utf-8")

        for phrase in required_phrases:
            assert phrase in documentation, f"{filename} must contain {phrase!r}"


def test_startup_script_discovers_python_without_machine_specific_path():
    script = (PROJECT_ROOT / "start_delivery.ps1").read_text(encoding="utf-8")

    assert "F:\\deepl\\anaconda1\\envs\\pytorch\\python.exe" not in script
    assert "$env:AGRINEBULA_PYTHON" in script
    assert 'Join-Path $projectRoot ".venv\\Scripts\\python.exe"' in script
    assert "Get-Command python.exe" in script


def test_startup_script_runs_real_preflight_and_records_processes():
    script = (PROJECT_ROOT / "start_delivery.ps1").read_text(encoding="utf-8")

    assert "scripts\\preflight.py" in script
    assert "node_modules\\.bin\\vite.cmd" in script
    assert "delivery-processes.json" in script
    assert "stop_delivery.ps1" in script


def test_startup_script_persists_process_output_to_stable_log_files():
    script = (PROJECT_ROOT / "start_delivery.ps1").read_text(encoding="utf-8")

    assert 'Join-Path $projectRoot "data\\logs"' in script
    assert "api.stdout.log" in script
    assert "api.stderr.log" in script
    assert "web.stdout.log" in script
    assert "web.stderr.log" in script
    assert script.count("-RedirectStandardOutput") == 2
    assert script.count("-RedirectStandardError") == 2


def test_startup_script_tails_delivery_logs_for_failed_readiness():
    script = (PROJECT_ROOT / "start_delivery.ps1").read_text(encoding="utf-8")

    assert "Show-DeliveryLogTail" in script
    assert "Get-Content -LiteralPath $Path -Encoding UTF8 -Tail 40" in script
    assert "Unable to read delivery log" in script
    assert 'Write-Host "Logs: $logRoot"' in script
    helper = script[script.index("function Show-DeliveryLogTail") : script.index("$pythonCandidates")]
    assert helper.index("try {") < helper.index("Test-Path")
    assert "-WarningAction Continue" in helper


def test_startup_and_stop_scripts_guard_process_ownership():
    start = (PROJECT_ROOT / "start_delivery.ps1").read_text(encoding="utf-8")
    stop = (PROJECT_ROOT / "stop_delivery.ps1").read_text(encoding="utf-8")

    assert "Get-NetTCPConnection" in start
    assert ".HasExited" in start
    assert "Refusing to start" in start
    assert "CommandLine" in stop
    assert "CreationDate" in stop
    assert "projectRoot" in stop


def test_double_click_launcher_delegates_to_verified_delivery_script():
    launcher = (PROJECT_ROOT / "启动项目.bat").read_text(encoding="utf-8")

    assert (
        'set "AGRINEBULA_PYTHON=F:\\deepl\\anaconda1\\envs\\pytorch\\python.exe"'
        in launcher
    )
    assert "start_delivery.ps1" in launcher
    assert "http://127.0.0.1:5173" in launcher
    assert "if errorlevel 1" in launcher.lower()


def test_double_click_stop_wrapper_delegates_to_stop_script():
    launcher = (PROJECT_ROOT / "停止项目.bat").read_text(encoding="utf-8")

    assert "stop_delivery.ps1" in launcher
    assert "if errorlevel 1" in launcher.lower()


def test_double_click_wrappers_are_cmd_safe_ascii():
    for filename in ("启动项目.bat", "停止项目.bat"):
        content = (PROJECT_ROOT / filename).read_bytes()
        assert content.isascii()


def test_stop_script_tolerates_process_exit_race():
    stop = (PROJECT_ROOT / "stop_delivery.ps1").read_text(encoding="utf-8")
    assert "Stop-Process -Id $id -Force -ErrorAction SilentlyContinue" in stop


def test_stop_script_waits_before_removing_process_state():
    stop = (PROJECT_ROOT / "stop_delivery.ps1").read_text(encoding="utf-8")
    stop_flow = stop[stop.index("$ids = Get-DescendantProcessIds") :]

    assert "Wait-DeliveryProcessesExit -ProcessIds $ids" in stop_flow
    assert stop_flow.index("Stop-Process -Id $id") < stop_flow.index("Wait-DeliveryProcessesExit")
    assert stop_flow.index("Wait-DeliveryProcessesExit") < stop_flow.index("Remove-Item")
    assert "Timed out waiting for delivery processes to exit" in stop_flow
    assert "Where-Object { $_ -gt 0 }" in stop


def test_startup_script_rolls_back_partial_process_startup():
    start = (PROJECT_ROOT / "start_delivery.ps1").read_text(encoding="utf-8")
    startup = start[start.index("$createdAt =") : start.index("$apiReady =")]

    assert "$startedProcesses = @()" in startup
    assert startup.index("try {") < startup.index("$apiProcess = Start-Process")
    assert "Invoke-DeliveryStartupRollback" in startup
    assert "start_time_ticks" in start
    assert "recovery_processes" in start
    assert "recovery_processes" in (PROJECT_ROOT / "stop_delivery.ps1").read_text(encoding="utf-8")
    assert "Delivery process startup failed" in start
    assert "Rollback internal failure" in startup
    assert "$stateWriteAttempted" in startup
    assert startup.index("[System.IO.File]::WriteAllText(") < startup.index("} catch {")
    cleanup = start[start.index("function Stop-StartedProcessTrees") : start.index("$pythonCandidates")]
    assert cleanup.index("Get-CimInstance") < cleanup.index("Stop-Process")
    assert "Process identity mismatch" in cleanup
    assert "survivor_processes = @()" in cleanup


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

        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(project / "stop_delivery.ps1"),
            ],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=15,
        )
        assert result.returncode == 0, result.stdout + result.stderr
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
        for name in ("Stop-StartedProcessTrees", "Invoke-DeliveryStartupRollback")
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
    rollback_function = _extract_powershell_function(start_script, "Stop-StartedProcessTrees")
    harness = f"""
$ErrorActionPreference = "Stop"
{rollback_function}
$process = Start-Process powershell.exe -ArgumentList @("-NoProfile", "-File", {_ps_quote(sleeper)}) -WindowStyle Hidden -PassThru
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
    }} | ConvertTo-Json -Compress
}} finally {{
    $process.Refresh()
    if (-not $process.HasExited) {{
        Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
    }}
}}
"""
    result = _run_powershell_harness(tmp_path, harness)

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["success"] is True
    assert payload["survivors"] == []
    assert payload["errors"] == []
    assert payload["has_exited"] is True

def test_stop_recovery_state_rejects_reused_pid_then_stops_exact_survivor(tmp_path):
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
        assert mismatch.returncode != 0
        assert process.poll() is None
        assert state_path.exists()

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
        for name in ("Stop-StartedProcessTrees", "Invoke-DeliveryStartupRollback")
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
