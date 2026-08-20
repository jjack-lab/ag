from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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
    assert "Get-Content -LiteralPath $Path -Tail 40" in script
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
