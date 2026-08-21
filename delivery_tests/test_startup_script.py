from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]

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




def test_startup_normal_state_persists_exact_root_identities():
    start = (PROJECT_ROOT / "start_delivery.ps1").read_text(encoding="utf-8")
    stop = (PROJECT_ROOT / "stop_delivery.ps1").read_text(encoding="utf-8")
    normal_state = start[start.rindex("$state = @{") : start.index("$stateDir =", start.rindex("$state = @{"))]

    assert "api_pid = $apiProcess.Id" in normal_state
    assert "web_pid = $webProcess.Id" in normal_state
    assert "processes = @(" in normal_state
    assert "start_time_ticks = [long]$apiProcessRecord.start_time_ticks" in normal_state
    assert "start_time_ticks = [long]$webProcessRecord.start_time_ticks" in normal_state
    assert 'PSObject.Properties.Name -contains "processes"' in stop
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
