# Unicode In-Project Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Windows test and image-output paths Unicode-safe so the complete project can be verified entirely below `F:\new大创`.

**Architecture:** Use explicit test fixture helpers for PyTorch and OpenCV writes, product image I/O based on Python file APIs plus `cv2.imdecode`/`cv2.imencode`, UTF-8 BOM for Windows PowerShell 5 harnesses, and a fail-closed safety-root fallback. Do not globally monkeypatch libraries or touch frozen experiment artifacts.

**Tech Stack:** Python 3.8, pathlib, PyTorch 2.0, OpenCV, pytest, Windows PowerShell 5, React/Vitest.

---

### Task 1: Unicode-safe test fixture I/O

**Files:**
- Create: `delivery_tests/io_helpers.py`
- Create: `delivery_tests/test_unicode_project_io.py`
- Modify: `delivery_tests/test_behavior_model.py`
- Modify: `delivery_tests/test_behavior_training.py`
- Modify: `delivery_tests/test_cvb_dataset.py`
- Modify: `delivery_tests/test_cvb_index.py`

- [ ] **Step 1: Write failing helper tests**

Test a nested non-ASCII path for a torch payload round trip and a JPEG round trip. Assert files exist and decoded content matches.

- [ ] **Step 2: Run the tests and verify RED**

Run: `python -m pytest delivery_tests/test_unicode_project_io.py -q --basetemp outputs/test-temp/unicode-helper-red`

Expected: import failure because `delivery_tests.io_helpers` does not exist.

- [ ] **Step 3: Implement explicit fixture helpers**

`save_torch_fixture(path, payload)` creates the parent and calls `torch.save(payload, handle)` on an opened `wb` handle. `write_cv_image_fixture(path, image)` calls `cv2.imencode(path.suffix, image)`, rejects failure, and writes encoded bytes through `Path.write_bytes`.

- [ ] **Step 4: Replace direct setup writes and verify GREEN**

Replace only test-fixture calls to `torch.save(path)` and `cv2.imwrite(path)`. Run the four affected test files and confirm no failures.

- [ ] **Step 5: Commit**

Commit: `test: support unicode fixture paths`

### Task 2: Unicode-safe application image I/O

**Files:**
- Create: `cattle_health_app/image_io.py`
- Modify: `cattle_health_app/behavior/dataset.py`
- Modify: `cattle_health_app/behavior/cvb_index.py`
- Modify: `cattle_health_app/behavior/validate_index.py`
- Modify: `cattle_health_app/media_processor.py`
- Modify: `delivery_tests/test_unicode_project_io.py`

- [ ] **Step 1: Add failing product image-I/O tests**

Assert a PNG can be written and read below a non-ASCII nested directory, missing/empty/invalid files return `None`, and an extensionless target is rejected without creating a file.

- [ ] **Step 2: Run the tests and verify RED**

Expected: import failure because `cattle_health_app.image_io` does not exist.

- [ ] **Step 3: Implement and integrate `read_cv_image` / `write_cv_image`**

Read bytes with `Path.read_bytes` and decode with `cv2.imdecode`; return `None` for missing, empty, unreadable, or invalid images so existing callers preserve their undecodable-frame behavior. Create the parent, encode from the target suffix with `cv2.imencode`, write bytes with `Path.write_bytes`, and raise `ValueError` for an absent suffix or failed encoding. Use the reader in behavior dataset/index paths and the writer in `LocalMediaProcessor.detect_image`.

- [ ] **Step 4: Verify product and delivery tests**

Run the Unicode image-I/O test, affected behavior dataset/index tests, delivery API tests, and image recognition contract tests.

- [ ] **Step 5: Commit**

Commit: `fix: read and write images on unicode paths`

### Task 3: PowerShell and safe-replace compatibility

**Files:**
- Modify: `delivery_tests/test_process_lifecycle_races.py`
- Modify: `delivery_tests/test_behavior_prepare_dataset.py`
- Modify: `cattle_health_app/behavior/prepare_dataset.py`

- [ ] **Step 1: Preserve the reproduced failures**

Record that PowerShell paths contain `new澶у垱` with UTF-8 and that `Path.home().resolve()` raises `PermissionError` in the restricted environment.

- [ ] **Step 2: Write BOM and safety-fallback tests**

Assert the harness file begins with UTF-8 BOM and a simulated home-resolution failure does not prevent a safe nested output replacement or allow current/home/root output deletion.

- [ ] **Step 3: Implement minimal compatibility**

Write harness files with `encoding="utf-8-sig"`. Add a helper that tries `path.resolve()` for a safety root and falls back to `Path(os.path.abspath(path))`; keep `output.resolve()` strict.

- [ ] **Step 4: Verify affected suites**

Run process lifecycle, dataset preparation, behavior model/training and CVB dataset tests from an in-project `--basetemp`.

- [ ] **Step 5: Commit**

Commit: `fix: verify safely from unicode project paths`

### Task 4: Full completion verification

**Files:**
- Modify: `docs/superpowers/plans/2026-08-23-cross-domain-cattle-behavior-robustness.md`
- Modify: `README_BEHAVIOR_DATA.md` only if commands or limitations change

- [ ] **Step 1: Run all Python tests inside the project**

Run: `python -m pytest -q --basetemp outputs/test-temp/full-unicode-green`

Expected: no failures; only already documented environment-dependent skips.

- [ ] **Step 2: Run cross-domain, frontend, build and preflight checks**

Run the 22 focused cross-domain tests, all 16 frontend tests, `npm run build`, and `start_delivery.ps1 -CheckOnly` with `AGRINEBULA_PYTHON` set to the verified environment.

- [ ] **Step 3: Re-audit repository scope and scientific outputs**

Confirm no media/raw prediction caches are tracked and all frozen hashes/metrics remain unchanged.

- [ ] **Step 4: Review and commit final verification evidence**

Commit: `test: verify project from unicode workspace`
