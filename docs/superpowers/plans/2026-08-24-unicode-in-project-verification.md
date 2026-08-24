# Unicode In-Project Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing Windows test and image-I/O paths Unicode-safe so the complete project can be verified entirely below `F:\new大创`.

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

- [x] **Step 1: Write failing helper tests**

Test a nested non-ASCII path for a torch payload round trip and a JPEG round trip. Assert files exist and decoded content matches.

- [x] **Step 2: Run the tests and verify RED**

Run: `python -m pytest delivery_tests/test_unicode_project_io.py -q --basetemp outputs/test-temp/unicode-helper-red`

Expected: import failure because `delivery_tests.io_helpers` does not exist.

- [x] **Step 3: Implement explicit fixture helpers**

`save_torch_fixture(path, payload)` creates the parent and calls `torch.save(payload, handle)` on an opened `wb` handle. `write_cv_image_fixture(path, image)` calls `cv2.imencode(path.suffix, image)`, rejects failure, and writes encoded bytes through `Path.write_bytes`.

- [x] **Step 4: Replace direct setup writes and verify GREEN**

Replace only test-fixture calls to `torch.save(path)` and `cv2.imwrite(path)`. Run the four affected test files and confirm no failures.

- [x] **Step 5: Commit**

Commit: `test: support unicode fixture paths`

### Task 2: Unicode-safe application image I/O

**Files:**
- Create: `cattle_health_app/image_io.py`
- Modify: `cattle_health_app/behavior/dataset.py`
- Modify: `cattle_health_app/behavior/cvb_index.py`
- Modify: `cattle_health_app/behavior/validate_index.py`
- Modify: `cattle_health_app/media_processor.py`
- Modify: `delivery_tests/test_unicode_project_io.py`

- [x] **Step 1: Add failing product image-I/O tests**

Assert a PNG can be written and read below a non-ASCII nested directory, missing/empty/invalid files return `None`, and an extensionless target is rejected without creating a file.

- [x] **Step 2: Run the tests and verify RED**

Expected: import failure because `cattle_health_app.image_io` does not exist.

- [x] **Step 3: Implement and integrate `read_cv_image` / `write_cv_image`**

Read bytes with `Path.read_bytes` and decode with `cv2.imdecode`; return `None` for missing, empty, unreadable, or invalid images so existing callers preserve their undecodable-frame behavior. Create the parent, encode from the target suffix with `cv2.imencode`, write bytes with `Path.write_bytes`, and raise `ValueError` for an absent suffix or failed encoding. Use the reader in behavior dataset/index paths and the writer in `LocalMediaProcessor.detect_image`.

- [x] **Step 4: Verify product and delivery tests**

Run the Unicode image-I/O test, affected behavior dataset/index tests, delivery API tests, and image recognition contract tests. Directly cover `LocalMediaProcessor.detect_image()` writing to a Unicode result path and translating writer `OSError`/`ValueError` into its public save-error contract.

- [x] **Step 5: Commit**

Commit: `fix: read and write images on unicode paths`

### Task 3: PowerShell and safe-replace compatibility

**Files:**
- Modify: `delivery_tests/test_process_lifecycle_races.py`
- Modify: `delivery_tests/test_behavior_prepare_dataset.py`
- Modify: `cattle_health_app/behavior/prepare_dataset.py`

- [x] **Step 1: Preserve the reproduced failures**

Record that PowerShell paths contain `new澶у垱` with UTF-8, that `Path.home().resolve()` raises `PermissionError`, and that the restricted environment denies WMI/CIM process enumeration even after BOM decoding is fixed.

- [x] **Step 2: Write BOM, controlled CIM snapshot, and safety-fallback tests**

Assert the harness file begins with UTF-8 BOM; lifecycle race tests inject a read-only snapshot only for the controlled process they create; and a simulated home-resolution failure does not prevent a safe new output or allow current/home/root output deletion. Add an existing-output alias regression: if a safety root cannot resolve, `samefile=True` or a failed `samefile` check must reject overwrite before `rmtree`.

- [x] **Step 3: Implement minimal compatibility**

Write harness files with `encoding="utf-8-sig"` and give real-process race tests deterministic CIM snapshots without changing production fail-closed behavior. Keep `output.resolve()` strict. A failed safety-root resolve may use `Path(os.path.abspath(path))` for new outputs; overwriting an existing directory additionally requires `os.path.samefile(output, safety_root)` to return false, otherwise reject.

- [x] **Step 4: Verify affected suites**

Run process lifecycle, dataset preparation, behavior model/training and CVB dataset tests from an in-project `--basetemp`.

- [x] **Step 5: Commit**

Commit: `fix: verify safely from unicode project paths`

### Task 4: Full completion verification

**Files:**
- Modify: `docs/superpowers/plans/2026-08-23-cross-domain-cattle-behavior-robustness.md`
- Modify: `README_BEHAVIOR_DATA.md` only if commands or limitations change

- [x] **Step 1: Run all Python tests inside the project**

Run: `python -m pytest -q --basetemp outputs/test-temp/full-unicode-green`

Expected: no failures; only already documented environment-dependent skips.

Actual after the deletion-safety review fix: `541 passed, 4 skipped, 0 failed` in 37.10 seconds from the Unicode worktree with `--basetemp outputs/test-temp/full-unicode-green-after-safety-review-rerun`.

- [x] **Step 2: Run cross-domain, frontend, build and preflight checks**

Run the 22 focused cross-domain tests, all 16 frontend tests, `npm run build`, and `start_delivery.ps1 -CheckOnly` with `AGRINEBULA_PYTHON` set to the verified environment.

Actual: the comprehensive cross-domain superset passed `76/76`, frontend passed `16/16`, Vite production build succeeded, and delivery preflight passed with the expected detector and behavior artifacts.

- [x] **Step 3: Re-audit repository scope and scientific outputs**

Confirm no media/raw prediction caches are tracked and all frozen hashes/metrics remain unchanged.

Actual: 687 MP4 files total 3,480,105,107 bytes; tracked video, `predictions.csv`, and raw-cache counts are all zero. Checkpoint SHA-256 remains `731c6ed39dcf002915e888c829e1f86727f815331a2b3c21d06a17d40d62a08e`, calibration remains `655f4e32f92dcba08023d4a18b0c457f047affb4bd3f691ac6cdc7d90789cfe2`, and `metrics.json` remains `9ce519210226820659df2de472b4af523e0d97ec7f40acc240badd988b489a48`.

- [ ] **Step 4: Review and commit final verification evidence**

Commit: `test: verify project from unicode workspace`
