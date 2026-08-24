# Cross-Domain Cattle Behavior Robustness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a provenance-safe, reproducible CVB-to-CBVD-5 cross-domain cattle behavior benchmark with frozen calibration, quality-aware selective prediction, controlled video degradations, paper-ready reports, and a defense-facing results view.

**Architecture:** Keep external data governance, acquisition, dataset parsing, clip construction, quality measurement, experiment execution, and reporting in separate modules under `cattle_health_app/behavior`. All large media stays below `data/external` and is ignored by Git; committed manifests preserve source URLs, licenses, hashes, transformations, mappings, exclusions, and split groups. The existing X3D checkpoint and calibration policy are immutable inputs to a test-only external benchmark; any later few-shot adaptation uses a new group-isolated protocol.

**Tech Stack:** Python 3.8, dataclasses, pathlib, csv/json, requests, OpenCV, NumPy, pandas, PyTorch, scikit-learn, matplotlib, pytest, FastAPI, React, TypeScript, Vitest.

---

## File map

Create focused modules:

- `cattle_health_app/behavior/external_registry.py`: typed dataset registry and license-state validation.
- `cattle_health_app/behavior/external_download.py`: budgeted downloads, hashing, safe ZIP extraction, and append-only operation records.
- `cattle_health_app/behavior/cbvd5.py`: CBVD-5 annotation parsing and strict/extended label mapping.
- `cattle_health_app/behavior/external_clips.py`: source-group IDs, deterministic selection, clip provenance, and leakage checks.
- `cattle_health_app/behavior/quality.py`: image/video/track quality measurements and quality-gate scoring.
- `cattle_health_app/behavior/degradations.py`: deterministic controlled corruptions.
- `cattle_health_app/behavior/cross_domain_experiment.py`: frozen model protocol, inference records, metrics, and ablations.
- `cattle_health_app/behavior/cross_domain_reporting.py`: CSV/JSON/Markdown/PNG outputs.
- `scripts/prepare_external_behavior_data.py`: registry, inspection, acquisition, extraction, and manifest CLI.
- `scripts/run_cross_domain_behavior_experiment.py`: experiment and report CLI.
- `data/external/registry.json`: machine-readable official-source registry.
- `docs/data/2026-08-23-public-cattle-video-data-record.md`: user-facing dataset and operations ledger.
- `docs/experiments/2026-08-23-cross-domain-behavior-results.md`: final scientific result and claim boundaries.

Tests mirror each module in `delivery_tests/`. Frontend/API changes occur only after result JSON exists.

## Execution order and change log

Execute tasks in this dependency order: `1 -> 2 -> 10 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8 -> 9 -> 11 -> 12 -> 13 -> 14`.

- `2026-08-23`: Moved the metadata/license inspection gate (Task 10) ahead of the CBVD-5 parser (Task 3). The original numeric order could have encouraged implementing an annotation adapter from assumptions. The revised order verifies the official file list, license, and a small official annotation/metadata sample before the parser contract is finalized. The `5 GiB` cap, frozen-test protocol, label-mapping boundaries, and VLM deferral are unchanged.
- `2026-08-23`: Baseline tests revealed two independent Windows path limits: Python 3.8 needs `-X utf8` to decode the project path, while PyTorch 2.0 native file I/O and Windows PowerShell 5 still cannot operate on selected temporary paths below the non-ASCII parent. A `subst` experiment was rejected because `Path.resolve()` returns the physical path. Use the user's previously authorized `F:\codex-test-temp` only as an ephemeral ASCII Git worktree for baseline/final full-suite verification, then remove it. All implementation edits, downloaded datasets, manifests, caches, and experiment outputs remain under `F:\new大创`; scientific semantics are unchanged.
- `2026-08-23`: Official Kaggle metadata shows CBVD-5 is now version 11 under CC0 and totals 11,642,084,084 bytes. The old `video_cut` assumption is obsolete: 687 continuous MP4 files are under `videos/videos` and total 3,480,105,107 bytes; `miniannotations` plus the root VIA CSV keep the approved subset at 3,485,904,149 bytes. Use those version-11 paths. The subset remains below `5 GiB`, so the primary dataset and frozen external-test protocol are unchanged.
- `2026-08-23`: Replaced materialized duplicate clip MP4 files with hash-bound virtual clip specifications over immutable source videos. Each manifest row stores the source path and SHA-256, time window, normalized crop, and transformation record; the experiment loader applies those operations at read time. This avoids consuming the remaining `5 GiB` budget with redundant derivatives while preserving deterministic samples, source-group isolation, visual auditability, and the frozen external-test protocol.
- `2026-08-23`: The project contains the frozen checkpoint, calibration artifact, and a 2,897-row CVB validation logits cache, but not the corresponding CVB validation videos or previously measured video-quality rows. A learned video-quality gate therefore cannot be fitted without inventing evidence or using forbidden CBVD-5 test labels. Keep the implemented validation-only Logistic gate for future use when the CVB media is restored; for this real run, freeze a clearly named heuristic quality guard from absolute image/track bounds before reading external metrics. Report it as exploratory and do not claim a learned quality-gate improvement. Temperature calibration and the existing CVB-selected fixed rejection policy remain unchanged.
- `2026-08-23`: Freeze and commit the tested Task 12 runner before launching the first label-scored CBVD-5 inference. This adds a reproducibility checkpoint between dry-run protocol validation and metric generation; it does not change the external samples, calibration, rejection thresholds, quality rules, stress seed, or metrics.
- `2026-08-23`: Pre-run code review blocked the first label-scored inference until three evidence-integrity gaps are closed: move mutable run status out of the immutable protocol so dry-run/formal-run/resume share one fingerprint; bind every stress cache to its degradation, severity, selected-sample digest, and transformation evidence; and include the design-required NLL, ECE, Brier, per-class precision/recall/F1, and inference timing. These are reporting/cache corrections only; frozen samples, labels, model, calibration, rejection thresholds, heuristic rules, and seed remain unchanged.
- `2026-08-24`: The formal CUDA run completed before the time stop: 1000 logical baseline samples, 600 unique physical clips, 18 nonzero stress conditions, and 96 stress metric rows. Strict zero-shot Macro-F1 is 0.0048, so the result is recorded as cross-domain failure evidence; fixed and heuristic-quality rejection did not improve risk. The predeclared gate therefore recommends a separate group-isolated adaptation plan but does not execute it here.
- `2026-08-24`: Final Python execution from the Unicode worktree produced 486 passed, 4 skipped, and 37 failures, all in existing PyTorch `.pt` temporary writes or Windows PowerShell 5 harness paths that resolve through `F:\new大创`. `subst` is ineffective because `Path.resolve()` returns the physical Unicode path, and 8.3 aliases are disabled. The user's latest boundary forbids the previously authorized external ASCII worktree, so no files were copied outside the project. Cross-domain focused tests (21), artifact/API tests (8), delivery E2E tests (15), all frontend tests (16), the production build, and the explicitly configured delivery preflight pass. This changes only the final verification evidence, not experimental semantics.
- `2026-08-24`: Final scientific-claim review found that the defense UI still contained the obsolete learned-quality-gate wording from before real data inspection. Replace it with the verified `predeclared_heuristic` policy exposed through the validated API, state that CBVD-5 labels were not used for fitting, label it exploratory, and display Macro-F1 beside coverage/risk so the 0.0048 strict failure cannot be hidden. This closes the review HIGH without altering experimental outputs.
- `2026-08-24`: Local integration is gated because the branch-finishing workflow forbids merging while 37 full-suite failures remain. The latest user boundary also forbids the earlier external ASCII worktree. Add the approved supplemental plan `2026-08-24-unicode-in-project-verification.md`: fix explicit test fixture I/O, PowerShell BOM handling, fail-closed safety-root resolution, and real recognition-image output entirely below `F:\new大创`. Frozen external samples, metrics, hashes, thresholds and VLM deferral remain unchanged.
- `2026-08-24`: After explicit Unicode-safe test fixtures became green, the CVB dataset/index tests exposed a product defect hidden by their previous setup failures: OpenCV `cv2.imread(path)` returns `None` for valid frames below the Chinese project path. Expand supplemental Task 2 from output-only handling to explicit product image read/write using Python file APIs plus `cv2.imdecode`/`cv2.imencode`, including dataset, index and validation callers. This is an application path-compatibility correction only; frozen samples, experiment metrics, hashes, thresholds, quality policy and VLM deferral remain unchanged.
- `2026-08-24`: Adding the PowerShell UTF-8 BOM removed the 11 path-decoding failures, after which 3 lifecycle tests exposed a separate restricted-host dependency: WMI/CIM enumeration is denied. Keep production process ownership checks fail-closed; make only the real-process test harnesses inject deterministic CIM identity snapshots for the controlled processes they create and clean up. This changes verification portability, not delivery process safety or experimental semantics.
- `2026-08-24`: Final code review found a deletion-safety gap in the first safety-root fallback: an existing output alias could resolve to a protected root while that root's own `resolve()` failed, making canonical-vs-text comparison insufficient. Reopen supplemental Task 3 and final verification. For any existing-directory overwrite, require `os.path.samefile(output, unresolved_safety_root)` to prove the paths differ; equality or comparison failure rejects before `rmtree`. New-output publication remains allowed because it performs no deletion. Experiment semantics and frozen artifacts remain unchanged.
- `2026-08-24`: After fast-forward integration, main-root full-suite runs exposed drifting transient Windows `PermissionError` failures at directory-level `os.replace`: first CVB index, then dataset preparation and uncertainty experiment; each isolated rerun passed, while the same branch had 541/541 passing in the experiment worktree. Reopen final verification and add supplemental Task 5: a shared six-attempt exponential retry only for `PermissionError` on directory publication/backup restoration. Non-permission errors, bounded final failure, rollback safety, frozen experiments and VLM deferral remain unchanged.

### Task 1: External dataset registry and provenance contract

**Files:**
- Create: `delivery_tests/test_external_dataset_registry.py`
- Create: `cattle_health_app/behavior/external_registry.py`
- Create: `data/external/registry.json`
- Create: `docs/data/2026-08-23-public-cattle-video-data-record.md`
- Modify: `.gitignore`

- [x] **Step 1: Write failing registry tests**

Test a valid record, reject an unknown license state, reject a relative/escaping storage root, and require official URL, access URL, intended use, download budget, and status.

```python
def test_registry_loads_cbvd5_with_project_relative_storage(tmp_path):
    registry = load_registry(FIXTURE, project_root=tmp_path)
    cbvd5 = registry.require("cbvd5")
    assert cbvd5.license_status == "verify_before_download"
    assert cbvd5.storage_root == tmp_path / "data" / "external" / "cbvd5"


def test_registry_rejects_storage_outside_project(tmp_path):
    with pytest.raises(RegistryError, match="inside project_root"):
        load_registry(registry_file(tmp_path, storage_root="../outside"), tmp_path)
```

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_external_dataset_registry.py -q`

Expected: collection fails because `external_registry` does not exist.

- [x] **Step 3: Implement typed registry validation**

Define immutable `DatasetRecord` and `DatasetRegistry`. Allowed license states are `verified`, `verify_before_download`, `blocked_license`, and `not_used`. Resolve storage paths against an explicit project root and reject any path whose resolved form is outside it.

```python
@dataclass(frozen=True)
class DatasetRecord:
    dataset_id: str
    name: str
    version: str
    official_url: str
    access_url: str
    license_name: str
    license_url: str
    license_status: str
    intended_use: str
    storage_root: Path
    max_download_bytes: int
```

- [x] **Step 4: Add initial registry and ledger**

Register `cvb`, `cbvd5`, `mmcows`, and `cattleeyeview`. CBVD-5 starts as `verify_before_download`; MmCows records `CC-BY-NC-SA-4.0`; CattleEyeView is `not_used`. The ledger states that no external files have been downloaded yet and includes headings for operations, hashes, exclusions, and plan changes.

- [x] **Step 5: Ignore only external large-data directories**

Add rules for archives, raw media, derived frames/clips, and experiment caches. Negate `registry.json`, manifests, `.gitkeep`, result summaries, and documentation so provenance stays tracked.

- [x] **Step 6: Run focused tests and commit**

Run: `python -m pytest delivery_tests/test_external_dataset_registry.py -q`

Expected: all tests pass.

Commit: `feat: add external cattle dataset registry`

### Task 2: Budgeted acquisition, hashing, and safe extraction

**Files:**
- Create: `delivery_tests/test_external_dataset_download.py`
- Create: `cattle_health_app/behavior/external_download.py`

- [x] **Step 1: Write failing acquisition tests**

Cover: blocked unverified license, expected-size budget rejection before network access, streamed budget overflow, idempotent reuse after SHA-256 match, corrupt hash rejection, ZIP path traversal rejection, and append-only JSONL operation records.

```python
def test_download_refuses_unverified_license(tmp_path):
    with pytest.raises(DownloadBlocked, match="license"):
        acquire_file(record(status="verify_before_download"), file_spec(), tmp_path)


def test_safe_extract_rejects_zip_slip(tmp_path):
    archive = malicious_zip(tmp_path, "../escape.mp4")
    with pytest.raises(UnsafeArchive, match="outside extraction root"):
        safe_extract_zip(archive, tmp_path / "raw")
```

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_external_dataset_download.py -q`

Expected: import failure for the missing module.

- [x] **Step 3: Implement download primitives**

Add `RemoteFileSpec`, `AcquisitionResult`, `sha256_file`, `acquire_file`, `safe_extract_zip`, and `append_operation`. Accept an injected stream opener so tests never use the internet. Write to a `.part` file, enforce the cumulative byte limit while streaming, verify hash when supplied, then atomically rename inside the dataset archive directory.

- [x] **Step 4: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_external_dataset_download.py -q`

Expected: all tests pass without network access.

Commit: `feat: add provenance-safe external data acquisition`

### Task 3: CBVD-5 annotation parsing and transparent label mapping

**Files:**
- Create: `delivery_tests/test_cbvd5_dataset.py`
- Create: `cattle_health_app/behavior/cbvd5.py`

- [x] **Step 1: Write failing parser and mapping tests**

Use tiny committed CSV fixtures constructed in the test. Verify source labels are retained, combined posture/state labels map correctly, approximate mappings are excluded from strict mode, conflicts are rejected, and malformed times/boxes produce explicit exclusion records.

```python
@pytest.mark.parametrize(
    "source,expected",
    [
        (("foraging",), "grazing"),
        (("drinking",), "drinking"),
        (("rumination", "standing"), "ruminating-standing"),
        (("rumination", "lying"), "ruminating-lying"),
    ],
)
def test_strict_mapping(source, expected):
    mapped = map_cbvd5_labels(source, tier="strict")
    assert mapped.name == expected
    assert mapped.mapping_tier == "strict"
```

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_cbvd5_dataset.py -q`

Expected: import failure for `cbvd5`.

- [x] **Step 3: Implement canonical records and parser adapters**

Define `SourceAnnotation`, `MappedAnnotation`, `ExcludedAnnotation`, and an adapter matching the official annotation/metadata sample verified in Task 10. Keep input-specific column names inside the adapter and expose one canonical iterator. Implement both `strict` and `extended` mapping tables without changing `cvb_labels.py`.

- [x] **Step 4: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_cbvd5_dataset.py -q`

Expected: all tests pass.

Commit: `feat: parse and align CBVD-5 behavior labels`

### Task 4: Source groups, deterministic sampling, and clip manifests

**Files:**
- Create: `delivery_tests/test_external_behavior_clips.py`
- Create: `cattle_health_app/behavior/external_clips.py`

- [x] **Step 1: Write failing provenance and leakage tests**

Verify stable IDs, same source video/camera/time block produces the same group, deterministic class caps, no group crosses requested splits, and every derived clip has a source path, start/end time, crop track, mapping tier, transformation list, and output hash.

```python
def test_split_groups_never_cross_boundaries(records):
    split = assign_groups(records, seed=20260823, ratios=(0.0, 0.0, 1.0))
    owners = {}
    for item in split:
        assert owners.setdefault(item.source_group_id, item.split) == item.split
```

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_external_behavior_clips.py -q`

- [x] **Step 3: Implement manifest creation**

Use SHA-256 identifiers derived from source dataset/version/video/camera/time/track. Default external zero-shot split is `test`; adaptation mode must receive explicit group ratios. Call existing frame/crop utilities where compatible, but write a separate manifest containing source provenance rather than changing the CVB index format.

- [x] **Step 4: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_external_behavior_clips.py -q`

Commit: `feat: build leakage-safe external clip manifests`

### Task 5: Quality and temporal-consistency evidence

**Files:**
- Create: `delivery_tests/test_behavior_video_quality.py`
- Create: `cattle_health_app/behavior/quality.py`

- [x] **Step 1: Write failing feature tests**

Generate synthetic images and tracks in memory. Assert black frames have high dark ratio, constant frames have lower Laplacian variance than checkerboards, boundary-touching boxes have positive truncation, missing frame indices reduce continuity, and unstable probability sequences have lower agreement.

```python
def test_blur_score_separates_flat_and_textured_frames():
    flat = np.full((64, 64, 3), 128, np.uint8)
    textured = checkerboard(64)
    assert frame_quality(flat).laplacian_variance < frame_quality(textured).laplacian_variance
```

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_behavior_video_quality.py -q`

- [x] **Step 3: Implement deterministic quality records**

Define `FrameQuality`, `TrackQuality`, and `WindowQuality`. Use normalized, resolution-independent values where possible. Implement no learned threshold here; this module only measures evidence.

- [x] **Step 4: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_behavior_video_quality.py -q`

Commit: `feat: measure behavior video quality evidence`

### Task 6: Frozen cross-domain protocol and quality-aware gate

**Files:**
- Create: `delivery_tests/test_cross_domain_behavior_experiment.py`
- Create: `cattle_health_app/behavior/cross_domain_experiment.py`
- Modify: `cattle_health_app/behavior/uncertainty.py`

- [x] **Step 1: Write failing protocol tests**

Use deterministic logits and quality rows. Verify external labels cannot be supplied to gate fitting, checkpoint/calibration hashes must match, strict and extended rows remain separate, abstention metrics match hand calculations, and a fitted gate serializes its training domain as `cvb_validation`.

```python
def test_gate_fit_rejects_external_training_domain():
    with pytest.raises(ProtocolViolation, match="cvb_validation"):
        fit_quality_gate(rows, training_domain="cbvd5_test")


def test_frozen_protocol_rejects_calibration_hash_mismatch(tmp_path):
    with pytest.raises(ProtocolViolation, match="checkpoint_sha256"):
        load_frozen_protocol(checkpoint, incompatible_calibration(tmp_path))
```

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_cross_domain_behavior_experiment.py -q`

- [x] **Step 3: Implement experiment records and metric variants**

Reuse existing calibration and metric functions. Add `CrossDomainProtocol`, `ExternalPrediction`, `QualityGate`, and `evaluate_variants`. Variants are exactly `uncalibrated`, `calibrated`, `calibrated_fixed_rejection`, and `calibrated_quality_rejection`. Preserve raw 12-class probabilities for audit.

- [x] **Step 4: Implement a simple interpretable gate**

Fit standardization and logistic regression only on CVB validation rows, with target `raw prediction is correct and health-eligible`. Choose its acceptance threshold using the existing minimum eligible coverage constraint and deterministic tie-breaking. Store feature order, means, scales, coefficients, intercept, threshold, seed, training domain, checkpoint hash, and input manifest hash.

- [x] **Step 5: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_cross_domain_behavior_experiment.py delivery_tests/test_behavior_uncertainty.py -q`

Commit: `feat: evaluate quality-aware selective behavior recognition`

### Task 7: Deterministic controlled degradations

**Files:**
- Create: `delivery_tests/test_behavior_degradations.py`
- Create: `cattle_health_app/behavior/degradations.py`

- [x] **Step 1: Write failing degradation tests**

Verify level zero returns identical content, equal seeds return identical occlusions/frame drops, increasing blur levels do not increase Laplacian variance, dimensions and frame count contracts are explicit, and input arrays are not modified.

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_behavior_degradations.py -q`

- [x] **Step 3: Implement six named degradations**

Implement `blur`, `low_light`, `occlusion`, `downsample`, `frame_drop`, and `compression`. Each returns frames plus a serializable `TransformationRecord` containing name, level, parameters, and seed.

- [x] **Step 4: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_behavior_degradations.py -q`

Commit: `feat: add reproducible behavior video stress tests`

### Task 8: Reproducible preparation and experiment CLIs

**Files:**
- Create: `delivery_tests/test_external_behavior_cli.py`
- Create: `scripts/prepare_external_behavior_data.py`
- Create: `scripts/run_cross_domain_behavior_experiment.py`

- [x] **Step 1: Write failing CLI tests**

Call `main(argv)` against temporary fixtures. Assert `inspect` performs no download, `acquire` refuses an unverified license, `prepare` writes manifests and exclusions, and `run --dry-run` validates all frozen hashes without loading PyTorch weights.

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_external_behavior_cli.py -q`

- [x] **Step 3: Implement preparation commands**

Support:

```text
prepare_external_behavior_data.py inspect --dataset cbvd5
prepare_external_behavior_data.py acquire --dataset cbvd5 --file videos/videos
prepare_external_behavior_data.py prepare --dataset cbvd5 --tier strict
```

`inspect` prints license state, declared/remote size, remaining budget, destination, and planned operations. `acquire` requires `license_status=verified`. `prepare` never downloads implicitly.

- [x] **Step 4: Implement experiment command**

Support:

```text
run_cross_domain_behavior_experiment.py --manifest <csv> --output <dir> --seed 20260823
run_cross_domain_behavior_experiment.py --manifest <csv> --output <dir> --stress-levels 0,1,2,3
```

Write `protocol.json` before inference and refuse an existing output directory whose protocol differs. Allow `--resume` only when hashes match.

- [x] **Step 5: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_external_behavior_cli.py -q`

Commit: `feat: add external behavior experiment commands`

### Task 9: Paper-ready reporting

**Files:**
- Create: `delivery_tests/test_cross_domain_behavior_reporting.py`
- Create: `cattle_health_app/behavior/cross_domain_reporting.py`
- Create: `docs/experiments/2026-08-23-cross-domain-behavior-results.md`

- [x] **Step 1: Write failing report tests**

Use a five-row fixture and assert stable CSV column order, separate strict/extended tables, correct best-variant selection without test-time tuning, risk-coverage points, degradation grouping, escaped Markdown, and valid PNG files.

- [x] **Step 2: Run tests and verify RED**

Run: `python -m pytest delivery_tests/test_cross_domain_behavior_reporting.py -q`

- [x] **Step 3: Implement structured outputs**

Generate `predictions.csv`, `metrics.json`, `protocol_comparison.csv`, `per_class_metrics.csv`, `risk_coverage.csv`, `stress_metrics.csv`, `confusion_matrix.png`, `risk_coverage.png`, `stress_curves.png`, and `summary.md`. The report must label unsupported claims and show external sample counts beside every metric.

- [x] **Step 4: Add result-document template with honest states**

The committed document supports `not_run`, `blocked`, and `complete`. Before real execution it says no external result exists; after execution it records hashes, commands, tables, limitations, and whether the quality gate improved risk at comparable coverage.

- [x] **Step 5: Verify GREEN and commit**

Run: `python -m pytest delivery_tests/test_cross_domain_behavior_reporting.py -q`

Commit: `feat: report cross-domain behavior robustness results`

### Task 10: Inspect official data metadata and update the plan before parser implementation or media download

**Files:**
- Modify: `data/external/registry.json`
- Modify: `docs/data/2026-08-23-public-cattle-video-data-record.md`
- Modify if facts changed: `docs/superpowers/specs/2026-08-23-cross-domain-cattle-behavior-robustness-design.md`
- Modify if facts changed: `docs/superpowers/plans/2026-08-23-cross-domain-cattle-behavior-robustness.md`

- [x] **Step 1: Run metadata-only inspection**

Use the official Kaggle API/CLI or public dataset page to list files, sizes, versions, and license without downloading media. After the license gate passes, acquire only the smallest official annotation/metadata file needed to verify the parser schema; record its size and hash against the same `5 GiB` budget. Do not store credentials in the repository.

- [x] **Step 2: Apply the acquisition gate**

Proceed with CBVD-5 only if the dataset license permits this non-commercial research use, required video and annotation files can be acquired through the official mechanism, and planned bytes do not exceed `5 GiB`. Otherwise record `blocked_license`, `blocked_access`, or `blocked_budget` and inspect MmCows under the same rules.

- [x] **Step 3: Record any plan change before continuing**

Add a dated change entry with old assumption, observed fact, impact, chosen fallback, and unchanged scientific constraints. Update the active Goal/plan status in the same turn.

- [x] **Step 4: Commit the verified metadata**

Commit: `docs: verify external cattle dataset acquisition metadata`

### Task 11: Acquire, prepare, and audit the real external subset

**Files:**
- Create ignored media under: `data/external/<dataset>/archives/`
- Create ignored extracted data under: `data/external/<dataset>/raw/`
- Create tracked manifests under: `data/external/<dataset>/manifests/`
- Modify: `docs/data/2026-08-23-public-cattle-video-data-record.md`

- [x] **Step 1: Run `inspect` and save the console summary in the ledger**

- [x] **Step 2: Acquire only approved files**

Stop automatically at the byte budget. Record source URL, ETag/version when exposed, local size, and SHA-256.

- [x] **Step 3: Extract and inventory non-destructively**

Keep archives. Write file inventory before parsing. Never rewrite original media.

- [x] **Step 4: Generate strict and extended virtual-clip manifests**

Write `source_videos.csv`, `evaluation_clips_strict.csv`, `evaluation_clips_extended.csv`, `excluded_samples.csv`, and `manifest_summary.json`. Clip rows reference immutable source videos and carry deterministic time-window/crop transformations instead of duplicating MP4 media; verify the source SHA-256 before decoding.

- [x] **Step 5: Audit samples visually and structurally**

Inspect at least 10 deterministic samples per mapped class when available. Record annotation/video mismatch, crop quality, behavior visibility, and exclusions. Do not relabel ambiguous samples by model prediction.

- [x] **Step 6: Validate and commit manifests/ledger**

Run all focused data tests and a manifest validation command. Commit only manifests, summaries, hashes, and documentation.

Commit: `data: register external cattle behavior benchmark subset`

### Task 12: Run frozen baseline, quality gate, and stress experiments

**Files:**
- Create ignored caches under: `outputs/cross_domain/cvb_to_cbvd5/`
- Track compact summaries/figures according to repository policy
- Modify: `docs/experiments/2026-08-23-cross-domain-behavior-results.md`
- Modify: `docs/data/2026-08-23-public-cattle-video-data-record.md`

- [x] **Step 1: Run dry-run protocol validation**

Verify checkpoint SHA-256, calibration/checkpoint binding, manifest hash, class mapping, output location, CUDA/CPU selection, and available disk space.

- [x] **Step 2: Run zero-shot strict and extended baselines once**

Do not change thresholds after seeing results. Preserve per-sample logits, quality evidence, and inference timing. The immutable protocol fingerprint must remain identical across dry-run, formal execution, and `--resume`; mutable status belongs in `preflight.json`/`run_state.json`.

- [x] **Step 3: Apply the frozen quality policy without external-label fitting**

Use the learned Logistic gate only if CVB validation video-quality rows with a verified manifest hash are present. In the current verified workspace they are absent, so write a `predeclared_heuristic` gate artifact with absolute image/track bounds fixed before external metrics are read, apply it without fitting, and record the missing-CVB-quality limitation. Never fit or retune from CBVD-5 labels.

- [x] **Step 4: Run controlled degradations**

Use the same selected source clips and fixed seed for all variants and levels. Persist the selected stress subset hash. Bind each stress cache to degradation name, severity, subset hash, and recorded transformations; reject copied or swapped condition caches.

- [x] **Step 5: Generate reports and check numerical invariants**

Confirm counts reconcile across prediction/metric files, coverage is within `[0,1]`, confusion-matrix totals match eligible samples, and calibration does not change argmax predictions. Report tier-aware Macro-F1 plus NLL, ECE, Brier score, per-class precision/recall/F1, and inference timing.

- [x] **Step 6: Evaluate the few-shot Go/No-Go gate**

Start a separate adaptation plan only when strict zero-shot Macro-F1 is below `0.30` and every included class has at least four independent source groups after reserving a final test group. Otherwise write the exact skip reason. No adaptation code is added inside this plan.

- [x] **Step 7: Commit compact results**

Commit: `exp: evaluate cross-domain cattle behavior robustness`

### Task 13: Defense-facing API and results view

**Files:**
- Create: `delivery_tests/test_cross_domain_results_api.py`
- Modify: `cattle_health_app/api.py`
- Modify: `web/src/api.ts`
- Create: `web/src/CrossDomainResults.test.tsx`
- Create: `web/src/CrossDomainResults.tsx`
- Modify: `web/src/RecognitionStudio.tsx`
- Modify: `web/src/styles.css`

- [x] **Step 1: Write failing API contract tests**

Assert the endpoint returns `not_run` when no summary exists, validates the committed schema when complete, and never serves arbitrary paths from result JSON.

- [x] **Step 2: Run API test and verify RED**

Run: `python -m pytest delivery_tests/test_cross_domain_results_api.py -q`

- [x] **Step 3: Implement read-only summary endpoint**

Expose only status, dataset/version, sample count, frozen model hash prefix, variant metrics, limitations, and application-relative figure URLs from the fixed output root.

- [x] **Step 4: Write failing React tests**

Assert `not_run`, `blocked`, and `complete` states; strict/extended labels; quality rejection reason; research-only disclaimer; and figure alternative text.

- [x] **Step 5: Run frontend test and verify RED**

Run: `npm test -- --run src/CrossDomainResults.test.tsx`

- [x] **Step 6: Implement the minimal results component**

Display dataset provenance, domain-shift comparison, coverage/risk, quality evidence, and limitations. Do not add live VLM controls or claims of disease diagnosis.

- [x] **Step 7: Verify GREEN and commit**

Run API and frontend focused tests.

Commit: `feat: present cross-domain robustness evidence`

### Task 14: Full verification, review, and delivery

**Files:**
- Modify: `README_BEHAVIOR_DATA.md`
- Modify: `docs/data/2026-08-23-public-cattle-video-data-record.md`
- Modify: `docs/experiments/2026-08-23-cross-domain-behavior-results.md`

- [x] **Step 1: Run all Python tests**

Run: `python -m pytest -q`

Expected: no failures; environment-dependent tests may only skip for documented existing reasons.

Final actual from the required in-project Unicode path after executing the supplemental remediation and deletion-safety review fix: 541 passed, 4 skipped, 0 failed in 37.10 seconds. The earlier 37 failures and their root causes remain preserved in the dated change log. No external ASCII test worktree was created; all implementation, test temporary files, data and outputs remained below `F:\new大创`.

- [x] **Step 2: Run frontend tests and build**

Run from `web`: `npm test -- --run`

Run from `web`: `npm run build`

Expected: all tests pass and Vite production build succeeds.

- [x] **Step 3: Run delivery preflight and one small end-to-end experiment**

Verify the API, existing upload pipeline, behavior result rendering, external result endpoint, and downloadable experiment artifacts.

- [x] **Step 4: Perform code and scientific-claim review**

Check path containment, archive extraction, untrusted CSV/JSON handling, hash enforcement, leakage, test-time threshold tuning, mapping boundaries, metric denominators, and claims unsupported by sample count.

- [x] **Step 5: Verify repository scope and provenance**

Confirm every modified file is below `F:\new大创`, no credentials or large raw media are tracked, the ledger matches actual hashes/paths, and the Git worktree is clean except intended changes.

- [x] **Step 6: Commit final documentation**

Commit: `docs: finalize cross-domain behavior experiment delivery`

- [x] **Step 7: Complete in-project Unicode verification remediation**

Execute `docs/superpowers/plans/2026-08-24-unicode-in-project-verification.md`, obtain a failure-free full Python run from an in-project temporary root, and then repeat final integration review. Do not use an external ASCII worktree.

Actual: supplemental remediation completed with 541 passed, 4 skipped, 0 failed; cross-domain 76/76, frontend 16/16, production build and delivery preflight passed. Final review closed the protected-root alias HIGH and approved integration with no HIGH/MEDIUM blockers.

- [ ] **Step 8: Complete post-merge Windows directory publication hardening**

Execute supplemental Task 5, obtain a failure-free full Python run from both the experiment worktree and merged main directory, repeat final review, and preserve the frozen experiment artifacts.

## Deferred final roadmap: VLM, multimodality, and embodied intelligence

This roadmap is deliberately outside the implementation tasks above. After Tasks 1–14 are complete, create a separate reviewed spec for: selective VLM review of rejected clips; video temporal grounding and evidence explanations; RGB/thermal/environment/history fusion; and eventually human-approved PTZ camera or inspection-robot actions. No VLM dependency, checkpoint, API call, UI control, or embodied-device action is added by this plan.
