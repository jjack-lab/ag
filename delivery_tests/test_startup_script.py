from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_startup_script_discovers_python_without_machine_specific_path():
    script = (PROJECT_ROOT / "start_delivery.ps1").read_text(encoding="utf-8")

    assert "F:\\deepl\\anaconda1\\envs\\pytorch\\python.exe" not in script
    assert "$env:AGRINEBULA_PYTHON" in script
    assert 'Join-Path $projectRoot ".venv\\Scripts\\python.exe"' in script
    assert "Get-Command python.exe" in script

