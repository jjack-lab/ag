# Runtime Operability Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add actionable background-service logs and complete detector/behavior artifact reporting to the current Windows one-click startup flow.

**Architecture:** Keep `start_delivery.ps1` as the process owner and redirect each child stream to a stable file under `data/logs`. Extend the existing Python preflight JSON through the model registry without eagerly constructing X3D, so missing behavior weights remain a nonfatal detector-only state.

**Tech Stack:** PowerShell 5.1, Python 3.8, pytest, FastAPI/Uvicorn, Vite/React, Git.

---

## File map

- Create `delivery_tests/test_preflight_reporting.py` — subprocess-level preflight JSON contract, including nonfatal missing behavior weights.
- Modify `scripts/preflight.py` — report detector and behavior artifact paths, hashes, statuses, and behavior resolver errors.
- Modify `delivery_tests/test_startup_script.py` — lock down the four logs, process redirection, bounded log tails, and documented log path.
- Modify `start_delivery.ps1` — create/reset logs, redirect API/Web streams, show bounded diagnostics on failure, and print the log directory on success.
- Modify `README.md` — document current-run logs and behavior preflight semantics.
- Modify `README_DELIVERY.md` — add concise operator troubleshooting instructions.

## Task 1: Report both model artifacts in preflight

**Files:**

- Create: `delivery_tests/test_preflight_reporting.py`
- Modify: `scripts/preflight.py`

- [ ] **Step 1: Write subprocess-level failing preflight tests**

Create `delivery_tests/test_preflight_reporting.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify the new JSON fields are absent**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_preflight_reporting.py -q -p no:cacheprovider
```

Expected: both tests fail with `KeyError: 'detector_status'` or `KeyError: 'behavior_status'`.

- [ ] **Step 3: Extend preflight with registry-only behavior reporting**

In `scripts/preflight.py`, replace the detector-only import with:

```python
from cattle_health_app.model_registry import (
    resolve_behavior_model,
    resolve_detector_model,
)
```

After the detector has loaded successfully, resolve the optional artifact:

```python
behavior_artifact = resolve_behavior_model(project_root=project_root)
```

Extend the printed JSON dictionary while preserving `model_sha256`:

```python
{
    "status": "ok",
    "python": sys.version.split()[0],
    "opencv": cv2.__version__,
    "torch": torch.__version__,
    "fastapi": fastapi.__version__,
    "uvicorn": uvicorn.__version__,
    "ultralytics": ultralytics.__version__,
    "model_sha256": artifact.sha256,
    "detector_status": "ready",
    "detector_path": str(artifact.path),
    "detector_sha256": artifact.sha256,
    "behavior_status": behavior_artifact.status,
    "behavior_path": str(behavior_artifact.path),
    "behavior_sha256": behavior_artifact.sha256,
    "behavior_error": behavior_artifact.error,
}
```

Do not import `TorchBehaviorClassifier`, build X3D, or make `unavailable` raise.

- [ ] **Step 4: Run focused preflight and registry tests**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_preflight_reporting.py delivery_tests/test_model_registry.py delivery_tests/test_behavior_registry_contract.py -q -p no:cacheprovider
```

Expected: all tests pass, and the missing behavior test exits zero.

- [ ] **Step 5: Commit preflight reporting**

```powershell
git add -- scripts/preflight.py delivery_tests/test_preflight_reporting.py
git commit -m "feat: report behavior artifact in preflight"
```

## Task 2: Persist child-process logs and show failure tails

**Files:**

- Modify: `delivery_tests/test_startup_script.py`
- Modify: `start_delivery.ps1`

- [ ] **Step 1: Add failing startup-log contract tests**

Append to `delivery_tests/test_startup_script.py`:

```python
def test_startup_redirects_all_child_streams_to_delivery_logs():
    script = (PROJECT_ROOT / "start_delivery.ps1").read_text(encoding="utf-8")

    for filename in (
        "api.stdout.log",
        "api.stderr.log",
        "web.stdout.log",
        "web.stderr.log",
    ):
        assert filename in script
    assert script.count("-RedirectStandardOutput") == 2
    assert script.count("-RedirectStandardError") == 2
    assert 'Join-Path $projectRoot "data\\logs"' in script


def test_startup_failure_prints_bounded_log_tails_and_success_prints_log_path():
    script = (PROJECT_ROOT / "start_delivery.ps1").read_text(encoding="utf-8")

    assert "Show-DeliveryLogTail" in script
    assert "Get-Content -LiteralPath $Path -Tail 40" in script
    assert "Unable to read delivery log" in script
    assert 'Write-Host "Logs: $logRoot"' in script
```

- [ ] **Step 2: Run the tests and verify they fail for missing logging contracts**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_startup_script.py -q -p no:cacheprovider
```

Expected: the two new tests fail because log filenames and redirection flags are absent.

- [ ] **Step 3: Define log paths and bounded diagnostic output**

Near the existing path declarations in `start_delivery.ps1`, add:

```powershell
$logRoot = Join-Path $projectRoot "data\logs"
$apiStdoutPath = Join-Path $logRoot "api.stdout.log"
$apiStderrPath = Join-Path $logRoot "api.stderr.log"
$webStdoutPath = Join-Path $logRoot "web.stdout.log"
$webStderrPath = Join-Path $logRoot "web.stderr.log"
```

After `Stop-WithDiagnostic`, add:

```powershell
function Show-DeliveryLogTail {
    param(
        [string]$Label,
        [string]$Path
    )
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }
    try {
        $lines = @(Get-Content -LiteralPath $Path -Tail 40 -ErrorAction Stop)
        if ($lines.Count -eq 0) {
            return
        }
        Write-Host "----- $Label ($Path) -----"
        $lines | ForEach-Object { Write-Host $_ }
    } catch {
        Write-Warning "Unable to read delivery log: $Path ($($_.Exception.Message))"
    }
}
```

- [ ] **Step 4: Reset current-run logs and redirect both child processes**

Immediately before `$createdAt`, create/reset the stable files:

```powershell
try {
    New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
    foreach ($path in @($apiStdoutPath, $apiStderrPath, $webStdoutPath, $webStderrPath)) {
        [System.IO.File]::WriteAllText(
            $path,
            "",
            [System.Text.UTF8Encoding]::new($false)
        )
    }
} catch {
    Stop-WithDiagnostic "Unable to prepare delivery logs at $logRoot`: $($_.Exception.Message)"
}
```

Add these arguments to the API `Start-Process` call:

```powershell
-RedirectStandardOutput $apiStdoutPath `
-RedirectStandardError $apiStderrPath `
```

Add these arguments to the Web `Start-Process` call:

```powershell
-RedirectStandardOutput $webStdoutPath `
-RedirectStandardError $webStderrPath `
```

- [ ] **Step 5: Print tails after failed readiness and the log path after success**

In the existing readiness failure block, keep the safe stop call and add:

```powershell
Show-DeliveryLogTail -Label "API stdout" -Path $apiStdoutPath
Show-DeliveryLogTail -Label "API stderr" -Path $apiStderrPath
Show-DeliveryLogTail -Label "Web stdout" -Path $webStdoutPath
Show-DeliveryLogTail -Label "Web stderr" -Path $webStderrPath
```

After the two ready messages, add:

```powershell
Write-Host "Logs: $logRoot"
```

- [ ] **Step 6: Run startup script tests and CheckOnly**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_startup_script.py -q -p no:cacheprovider
$env:AGRINEBULA_PYTHON = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1 -CheckOnly
```

Expected: startup tests pass and preflight prints both detector and behavior fields before `Delivery preflight passed.`

- [ ] **Step 7: Commit runtime logging**

```powershell
git add -- start_delivery.ps1 delivery_tests/test_startup_script.py
git commit -m "feat: persist delivery process logs"
```

## Task 3: Document and accept the real start/stop flow

**Files:**

- Modify: `delivery_tests/test_startup_script.py`
- Modify: `README.md`
- Modify: `README_DELIVERY.md`

- [ ] **Step 1: Add a failing documentation contract test**

Append to `delivery_tests/test_startup_script.py`:

```python
def test_runtime_docs_name_logs_and_nonfatal_behavior_preflight():
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    delivery = (PROJECT_ROOT / "README_DELIVERY.md").read_text(encoding="utf-8")

    for content in (readme, delivery):
        assert "data/logs" in content
        assert "api.stderr.log" in content
        assert "web.stderr.log" in content
        assert "行为模型" in content
        assert "不阻断" in content
```

- [ ] **Step 2: Run the documentation test and verify it fails**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_startup_script.py::test_runtime_docs_name_logs_and_nonfatal_behavior_preflight -q -p no:cacheprovider
```

Expected: fail because the log directory and stderr filenames are not documented.

- [ ] **Step 3: Document logs and optional behavior preflight**

Add a troubleshooting section to `README.md` and `README_DELIVERY.md` stating exactly:

```markdown
运行日志保存在 `data/logs`：

- `api.stdout.log` / `api.stderr.log`
- `web.stdout.log` / `web.stderr.log`

每次启动会覆盖上一轮日志。启动失败时脚本会自动显示每个非空日志的最后 40 行；停止项目不会删除日志。

启动预检会输出检测模型与行为模型的状态、路径和 SHA-256。检测模型缺失会阻断启动；行为模型缺失只会报告 `unavailable`，不阻断检测、跟踪和原有健康分析。
```

- [ ] **Step 4: Run focused documentation/startup tests**

Run:

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest delivery_tests/test_startup_script.py delivery_tests/test_preflight_reporting.py -q -p no:cacheprovider
```

Expected: all tests pass.

- [ ] **Step 5: Start the real services and verify logs/endpoints**

Run:

```powershell
$env:AGRINEBULA_PYTHON = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1
Invoke-RestMethod -Uri http://127.0.0.1:8000/api/health
(Invoke-WebRequest -UseBasicParsing -Uri http://127.0.0.1:5173).StatusCode
Get-Item data\logs\api.stdout.log,data\logs\api.stderr.log,data\logs\web.stdout.log,data\logs\web.stderr.log
powershell -NoProfile -ExecutionPolicy Bypass -File .\stop_delivery.ps1
```

Expected: API status is `ok`, Web status is `200`, all four logs exist, stop succeeds, and ports 8000/5173 are released.

- [ ] **Step 6: Commit documentation**

```powershell
git add -- README.md README_DELIVERY.md delivery_tests/test_startup_script.py
git commit -m "docs: explain delivery runtime diagnostics"
```

## Task 4: Complete regression, review, and publish

**Files:**

- Modify only if a regression defect is found: files owned by Tasks 1-3

- [ ] **Step 1: Run complete Python regression**

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest -q -p no:cacheprovider --tb=short
```

Expected: all tests pass; existing Torch warnings may remain but no new startup-log warnings are introduced.

- [ ] **Step 2: Run complete React regression and production build**

```powershell
Set-Location web
npm test -- --run --reporter=dot
npm run build
Set-Location ..
```

Expected: React tests pass and Vite production build exits zero.

- [ ] **Step 3: Run final preflight and state checks**

```powershell
$env:AGRINEBULA_PYTHON = 'F:\deepl\anaconda1\envs\pytorch\python.exe'
powershell -NoProfile -ExecutionPolicy Bypass -File .\start_delivery.ps1 -CheckOnly
git diff --check
git status --short --branch
```

Expected: preflight passes with detector and behavior metadata, no whitespace errors exist, and only the pre-existing user-owned `.idea/`, `=ro`, `cloud_pack/`, and `cloud_upload/` remain untracked.

- [ ] **Step 4: Request independent code review**

Review the complete change from design commit `dd5ecaf` through the implementation HEAD. Fix every Critical or Important finding using a new failing test first, then rerun Steps 1-3.

- [ ] **Step 5: Push the verified `integration` branch**

```powershell
git push origin integration
git status --short --branch
```

Expected: `integration` and `origin/integration` point to the same commit; user-owned untracked files remain untouched.

## Plan self-review

- The preflight task covers every model-reporting field in the approved design and explicitly preserves the legacy detector hash.
- The logging task covers directory creation, four separate streams, stable current-run files, bounded failure tails, secondary log-read errors, and success output.
- The acceptance task covers real start, API/Web readiness, log existence, stop cleanup, and operator documentation.
- Portability, installers, configurable ports, LAN exposure, and eager X3D loading remain outside the plan.
- Function names, log filenames, paths, and the 40-line bound are consistent across production code, tests, and documentation.
