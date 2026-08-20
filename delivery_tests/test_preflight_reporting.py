import json
import os
from hashlib import sha256
from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PREFLIGHT = PROJECT_ROOT / "scripts" / "preflight.py"


def run_preflight(extra_env):
    environment = os.environ.copy()
    environment.update(extra_env)
    completed = subprocess.run(
        [sys.executable, str(PREFLIGHT)],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    assert completed.returncode == 0, completed.stderr
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    return json.loads(lines[-1])


def test_preflight_reports_ready_detector_and_behavior_artifacts(tmp_path):
    behavior = tmp_path / "behavior.pt"
    behavior.write_bytes(b"behavior")

    payload = run_preflight({"AGRINEBULA_BEHAVIOR_MODEL": str(behavior)})

    assert payload["detector_status"] == "ready"
    assert Path(payload["detector_path"]).is_file()
    assert payload["detector_sha256"] == payload["model_sha256"]
    assert payload["behavior_status"] == "ready"
    assert payload["behavior_path"] == str(behavior.resolve())
    assert payload["behavior_sha256"] == sha256(b"behavior").hexdigest()
    assert payload["behavior_error"] is None


def test_preflight_keeps_missing_behavior_model_nonfatal(tmp_path):
    missing = tmp_path / "missing.pt"

    payload = run_preflight({"AGRINEBULA_BEHAVIOR_MODEL": str(missing)})

    assert payload["status"] == "ok"
    assert payload["behavior_status"] == "unavailable"
    assert payload["behavior_path"] == str(missing.resolve())
    assert payload["behavior_sha256"] is None
    assert "missing" in payload["behavior_error"].lower()
