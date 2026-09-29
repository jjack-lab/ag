# WAID4500 YOLO11s Reproducibility Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the exact WAID source data, frozen WAID4500 split, archived YOLO11s training run, and portable verification/training commands without committing third-party media or large generated artifacts.

**Architecture:** Keep local assets in the repository's existing ignored `data/external/waid/{raw,derived,cache}` structure and archived runs under ignored `outputs/training`. Track the authoritative manifest, portable configuration, hashes, environment, and result summary in `reproducibility/waid4500`; put reusable logic in one detection module with thin CLI wrappers.

**Tech Stack:** Python 3.8, Python standard library, PyYAML 6.0.2, Ultralytics 8.4.22, PyTorch 2.0.0, pytest/unittest, PowerShell.

---

## File structure

| Path | Responsibility |
| --- | --- |
| `cattle_health_app/detection/waid_repro.py` | Manifest parsing, label validation, safe paths, atomic rebuild/import, hashes, summaries, environment capture, and training arguments. |
| `tests/test_waid_repro.py` | Temporary miniature datasets and mocked-training tests. |
| `scripts/reproducibility/import_waid_assets.py` | Import local raw, derived, pretrained, run, and log assets. |
| `scripts/reproducibility/rebuild_waid4500.py` | Rebuild the frozen split from raw WAID and its manifest. |
| `scripts/reproducibility/train_waid_yolo11s.py` | Check-only, smoke, full training, and resume entry point. |
| `scripts/reproducibility/verify_waid_reproduction.py` | Asset, lineage, runtime, and result verifier. |
| `scripts/reproducibility/run_waid_reproduction.ps1` | One-command PowerShell workflow. |
| `reproducibility/waid4500/` | Tracked manifest, statistics, summaries, configuration, environment, and hashes. |
| `docs/WAID4500_REPRODUCIBILITY.md` | Reproduction guide. |

The approved design named `data/waid`; implementation uses the repository's equivalent existing convention:

```text
data/external/waid/raw/
data/external/waid/derived/waid4500_v1/
data/external/waid/cache/yolo11s.pt
outputs/training/waid4500_yolo11s/{run,logs}/
```

This preserves the approved Git boundary and avoids touching the user's current root `.gitignore` edit.

### Task 1: Define and test the manifest contract

**Files:**
- Create: `cattle_health_app/detection/__init__.py`
- Create: `cattle_health_app/detection/waid_repro.py`
- Create: `tests/test_waid_repro.py`

- [ ] **Step 1: Write failing tests**

Create a temporary manifest with the production header:

```python
MANIFEST_FIELDS = (
    "split", "output_image", "output_label", "source_image", "source_label",
    "source_split", "class_id", "class_name", "instances", "group_id",
)
```

Assert that `load_manifest()` preserves row order and returns relative POSIX output paths. Assert rejection of missing/reordered columns, duplicate output paths, absolute output paths, `..`, unsupported splits, mismatched class ID/name, invalid instance counts, and empty manifests. Assert `parse_label(b"1 0.5 0.5 0.2 0.2\n") == (1, 1)` and rejection of empty, mixed-class, nonnumeric, nonintegral, out-of-range class, and out-of-range-coordinate labels.

- [ ] **Step 2: Verify RED**

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest tests/test_waid_repro.py -q -p no:cacheprovider
```

Expected: import failure for `cattle_health_app.detection.waid_repro`.

- [ ] **Step 3: Implement the contract**

Define `CLASS_NAMES`, `MANIFEST_FIELDS`, `ManifestError`, immutable `ManifestRow`, `load_manifest(path)`, `parse_label(content)`, and `split_counts(rows)`. Read CSV as UTF-8 with BOM support. Use `PureWindowsPath(source_image).name` and `PureWindowsPath(source_label).name` so old E-drive paths remain provenance only. Require output path prefixes `images/<split>/` and `labels/<split>/`, and allow only `train`, `valid`, `test`.

- [ ] **Step 4: Verify GREEN and commit**

Run the Step 2 command; expect all tests to pass.

```powershell
git add cattle_health_app/detection/__init__.py cattle_health_app/detection/waid_repro.py tests/test_waid_repro.py
git commit -m "feat: define WAID4500 manifest contract"
```

### Task 2: Rebuild the exact dataset atomically

**Files:**
- Modify: `cattle_health_app/detection/waid_repro.py`
- Modify: `tests/test_waid_repro.py`
- Create: `scripts/reproducibility/rebuild_waid4500.py`

- [ ] **Step 1: Write failing rebuild tests**

Build a two-sample raw fixture. Call:

```python
summary = rebuild_dataset(
    raw_root=raw,
    manifest_path=manifest,
    output_root=output,
    expected_counts={"train": 1, "valid": 0, "test": 1},
)
assert summary["splits"] == {"train": 1, "valid": 0, "test": 1}
assert (output / "images/train/a.jpg").read_bytes() == b"image-a"
assert yaml.safe_load((output / "data.yaml").read_text(encoding="utf-8"))["path"] == str(output.resolve())
```

Test existing-output refusal, missing-source cleanup, path escapes, manifest/label mismatch, and cross-split `group_id` leakage.

- [ ] **Step 2: Verify RED**

Run the focused test; expect missing `rebuild_dataset`.

- [ ] **Step 3: Implement rebuilding**

Resolve sources only as `raw/images/<source_split>/<source_image_name>` and `raw/labels/<source_split>/<source_label_name>`, verifying each resolved path remains under `raw_root`. Create a sibling staging directory with prefix `.<output-name>.staging-`, copy with `shutil.copy2`, write deterministic split lists and portable `data.yaml`, validate counts/labels/groups, and rename staging into place. Cleanup may remove only the verified staging child.

- [ ] **Step 4: Add CLI and verify**

Expose `--raw-root`, `--manifest`, `--output`, `--expected-train` (4500), `--expected-valid` (200), `--expected-test` (20), and `--validate-only`. Print JSON; exit 0 success, 1 validation failure, 130 interruption.

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest tests/test_waid_repro.py -q -p no:cacheprovider
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' scripts/reproducibility/rebuild_waid4500.py --help
git add cattle_health_app/detection/waid_repro.py tests/test_waid_repro.py scripts/reproducibility/rebuild_waid4500.py
git commit -m "feat: rebuild frozen WAID4500 split"
```

### Task 3: Import local training assets safely

**Files:**
- Modify: `cattle_health_app/detection/waid_repro.py`
- Modify: `tests/test_waid_repro.py`
- Create: `scripts/reproducibility/import_waid_assets.py`

- [ ] **Step 1: Write failing importer tests**

Create miniature raw, `waid4500_v1`, `runs/waid4500_v1_yolo11s_img960_e120/weights/best.pt`, `training_logs`, and `yolo11s.pt` sources. Assert exact destination mapping, returned file counts/bytes, default existing-destination refusal, successful explicit replacement, and restoration of the original destination after injected copy failure.

- [ ] **Step 2: Verify RED**

Run the focused test; expect missing `ImportSources` and `import_assets`.

- [ ] **Step 3: Implement importer**

Create immutable `ImportSources(raw, frozen_dataset, pretrained, run, logs)` and `import_assets(sources, project_root, replace=False)`. Map them to the four documented local roots. Require marker files/directories before copying, reject destinations outside `project_root`, calculate counts/bytes, stage each component, verify staged totals, then publish. For replacement, rename old destination to a sibling backup, publish staging, restore on failure, and delete backup only after success.

- [ ] **Step 4: Add CLI, test, and commit**

Expose explicit `--source-raw`, `--source-training-root`, `--project-root`, and `--replace`; defaults may reference the current E-drive sources but all must be overrideable.

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest tests/test_waid_repro.py -q -p no:cacheprovider
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' scripts/reproducibility/import_waid_assets.py --help
git add cattle_health_app/detection/waid_repro.py tests/test_waid_repro.py scripts/reproducibility/import_waid_assets.py
git commit -m "feat: import local WAID training assets"
```

### Task 4: Add portable training

**Files:**
- Modify: `cattle_health_app/detection/waid_repro.py`
- Modify: `tests/test_waid_repro.py`
- Create: `scripts/reproducibility/train_waid_yolo11s.py`
- Create: `reproducibility/waid4500/training_config.yaml`

- [ ] **Step 1: Write failing configuration tests**

Require this committed configuration:

```yaml
model: data/external/waid/cache/yolo11s.pt
data_root: data/external/waid/derived/waid4500_v1
project: outputs/training/waid4500_yolo11s/reproduced
name: full_e120_seed42
epochs: 120
patience: 120
batch: 4
imgsz: 960
workers: 0
seed: 42
deterministic: true
cos_lr: true
device: auto
```

Mock `ultralytics.YOLO`. Assert full arguments; smoke overrides `epochs=1`, `fraction=0.02`, `name=smoke_e1`; device override; and resume requires an existing `last.pt`.

- [ ] **Step 2: Verify RED**

Run focused tests; expect missing configuration/training functions.

- [ ] **Step 3: Implement portable runtime**

Implement config loading, repository-contained path resolution, runtime `data.yaml` generation, full/smoke argument construction, check-only environment inspection, and lazy Ultralytics import. For `device: auto`, use `0` with CUDA or `cpu` otherwise. New output must never target the archived run directory.

- [ ] **Step 4: Add CLI, test, and commit**

Expose `--project-root`, `--config`, `--check-only`, `--smoke`, `--device`, and `--resume`. Check-only prints dependency versions, selected device, 4500/200/20 counts, pretrained SHA-256, and output path without calling training.

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest tests/test_waid_repro.py -q -p no:cacheprovider
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' scripts/reproducibility/train_waid_yolo11s.py --help
git add cattle_health_app/detection/waid_repro.py tests/test_waid_repro.py scripts/reproducibility/train_waid_yolo11s.py reproducibility/waid4500/training_config.yaml
git commit -m "feat: add portable WAID4500 training entry point"
```

### Task 5: Verify lineage and results

**Files:**
- Modify: `cattle_health_app/detection/waid_repro.py`
- Modify: `tests/test_waid_repro.py`
- Create: `scripts/reproducibility/verify_waid_reproduction.py`

- [ ] **Step 1: Write failing verification tests**

Test chunked SHA-256, standard two-space checksum parsing, mismatch reporting, delivery/archive equality, and best-row selection from `results.csv`. Require the production summary:

```json
{"epochs_recorded": 120, "selection_metric": "metrics/mAP50-95(B)", "best": {"epoch": 89, "precision": 0.94186, "recall": 0.91602, "map50": 0.95385, "map50_95": 0.584}}
```

- [ ] **Step 2: Verify RED**

Run focused tests; expect missing checksum, summary, and verifier functions.

- [ ] **Step 3: Implement verification**

Implement `sha256_file`, checksum parsing, checksum verification, result summarization, environment capture, and a report with `assets`, `lineage`, `runtime`, `results`, plus top-level status. Require archived `best.pt` and `models/detection/yolo11s-waid.pt` to equal `46d734cba7553f31e89e739156f50e9a675b176f798c70159838497531771a64`.

- [ ] **Step 4: Add CLI, test, and commit**

Expose `--project-root`, `--manifest`, `--checksums`, and `--output-json`. Output indented UTF-8 JSON; exit 0 passed and 1 failed.

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest tests/test_waid_repro.py -q -p no:cacheprovider
git add cattle_health_app/detection/waid_repro.py tests/test_waid_repro.py scripts/reproducibility/verify_waid_reproduction.py
git commit -m "feat: verify WAID4500 reproduction evidence"
```

### Task 6: Add one-command PowerShell orchestration

**Files:**
- Create: `scripts/reproducibility/run_waid_reproduction.ps1`
- Modify: `tests/test_waid_repro.py`

- [ ] **Step 1: Write a failing script contract test**

Assert parameters `Mode`, `Python`, `ProjectRoot`, `Device`, `Resume`; `$PSScriptRoot` path resolution; argument arrays; and absence of E-drive literals.

- [ ] **Step 2: Implement and verify**

Use `ValidateSet('verify','rebuild','smoke','train','resume')`, validate Python with `Test-Path -LiteralPath`, invoke wrappers with `& $Python @arguments`, and propagate `$LASTEXITCODE`. Map each mode to its same-named wrapper behavior; resume requires `-Resume`.

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest tests/test_waid_repro.py -q -p no:cacheprovider
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/reproducibility/run_waid_reproduction.ps1 -?
git add scripts/reproducibility/run_waid_reproduction.ps1 tests/test_waid_repro.py
git commit -m "feat: add WAID reproduction workflow"
```

### Task 7: Import evidence and local large assets

**Files:**
- Create: `reproducibility/waid4500/dataset_manifest.csv`
- Create: `reproducibility/waid4500/class_statistics.csv`
- Create: `reproducibility/waid4500/generation_summary.json`
- Create: `reproducibility/waid4500/run_summary.json`
- Create: `reproducibility/waid4500/environment.json`
- Create: `reproducibility/waid4500/checksums.sha256`
- Local-only: `F:\new大创\data\external\waid`
- Local-only: `F:\new大创\outputs\training\waid4500_yolo11s`

- [ ] **Step 1: Copy lightweight evidence**

Copy the frozen manifest, statistics, and generation summary into the worktree. Generate run summary from archived results and environment JSON from the selected Python runtime plus archived args/log evidence.

- [ ] **Step 2: Import local assets**

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' scripts/reproducibility/import_waid_assets.py `
  --source-raw 'E:\大创\WAID-main\WAID' `
  --source-training-root 'E:\大创\WAID_YOLO11' `
  --project-root 'F:\new大创'
```

Expected source totals: raw 28,733 files/1,630,319,326 bytes; frozen dataset 9,450 files/638,149,826 bytes; run 24 files/45,270,542 bytes; logs 16 files/22,644,001 bytes; pretrained one file.

- [ ] **Step 3: Generate hashes and validate reconstruction**

Hash pretrained, tracked manifest/statistics, results CSV, best/last weights, and delivery model into sorted lowercase `checksums.sha256`. Rebuild from raw into one explicitly named temporary sibling, compare every relative dataset file hash to the frozen snapshot, then remove only that verified temporary rebuild.

- [ ] **Step 4: Check Git boundaries and commit**

Confirm Git lists no raw image, label, `.pt`, plot, or log. Commit only the six lightweight evidence files.

```powershell
git add reproducibility/waid4500/dataset_manifest.csv reproducibility/waid4500/class_statistics.csv reproducibility/waid4500/generation_summary.json reproducibility/waid4500/run_summary.json reproducibility/waid4500/environment.json reproducibility/waid4500/checksums.sha256
git commit -m "data: record WAID4500 reproduction evidence"
```

### Task 8: Document the workflow and license boundary

**Files:**
- Create: `docs/WAID4500_REPRODUCIBILITY.md`
- Modify: `README.md`
- Modify: `THIRD_PARTY_DATA.md`
- Modify: `docs/superpowers/specs/2026-09-29-waid-yolo11s-reproducibility-design.md`

- [ ] **Step 1: Write documentation**

Document exact commands for import, verify, rebuild, smoke, train, resume, and normal app startup. Record the production hash and epoch-89 metrics. State that asset integration does not improve accuracy, retraining is not bitwise-identical across GPU stacks, and WAID redistribution still requires author permission.

- [ ] **Step 2: Align design paths and verify commands**

Replace design references to `data/waid` with `data/external/waid/{raw,derived,cache}` and explain reuse of existing ignore rules. Run every documented help/check-only command.

- [ ] **Step 3: Commit documentation**

```powershell
git add docs/WAID4500_REPRODUCIBILITY.md README.md THIRD_PARTY_DATA.md docs/superpowers/specs/2026-09-29-waid-yolo11s-reproducibility-design.md
git commit -m "docs: explain WAID4500 model reproduction"
```

### Task 9: End-to-end verification and handoff

**Files:**
- Modify: `HANDOFF.md`

- [ ] **Step 1: Run Python verification**

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest tests/test_waid_repro.py -q -p no:cacheprovider
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' -m pytest -q -p no:cacheprovider
```

Record exact pre-existing unrelated failures instead of describing the whole suite as green.

- [ ] **Step 2: Run real check-only, smoke, and verifier**

```powershell
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' scripts/reproducibility/train_waid_yolo11s.py --project-root 'F:\new大创' --check-only
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' scripts/reproducibility/train_waid_yolo11s.py --project-root 'F:\new大创' --smoke --device 0
& 'F:\deepl\anaconda1\envs\pytorch\python.exe' scripts/reproducibility/verify_waid_reproduction.py --project-root 'F:\new大创' --output-json 'F:\new大创\outputs\training\waid4500_yolo11s\verification.json'
```

Expect 4500/200/20, a separate `smoke_e1` checkpoint, passed status, matching delivery/archive best hashes, and selected epoch 89.

- [ ] **Step 3: Run frontend verification**

```powershell
Set-Location web
npm test -- --run --reporter=dot
npm run build
Set-Location ..
```

- [ ] **Step 4: Update handoff and commit**

Record asset locations/totals, hashes, all test results, smoke output, licensing caveat, and next work: a preregistered accuracy-improvement experiment against this frozen baseline.

```powershell
git add HANDOFF.md
git commit -m "docs: hand off WAID4500 reproduction workflow"
git status --short
git log --oneline -10
```

Expected: implementation worktree clean; ignored local assets remain in `F:\new大创`.

## Self-review

- Coverage: import, exact rebuild, portable training, results, hashes, environment, licensing, docs, smoke, full tests, and handoff all map to tasks.
- No placeholders: every task names exact files, public behavior, commands, and expected outcomes.
- Consistency: split names are `train`, `valid`, `test`; metrics match archived Ultralytics columns; SHA-256 is lowercase at rest.
- Safety: default no overwrite, constrained staging cleanup, root-contained paths, provenance-only E-drive paths, separate new training output, immutable archive.
